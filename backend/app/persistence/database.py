from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.analysis.listener import analyze_pattern
from app.config import DATABASE_PATH, SCHEMA_VERSION
from app.models.api import PreferenceRequest
from app.models.evaluation import (
    EmbodiedEvaluationRequest,
    EmbodiedEvaluationSummary,
    EmbodiedOperatorSummary,
    MotorTempoProfile,
)
from app.models.groove import GrooveIntent
from app.models.pattern import GroovePattern
from app.models.preference import GroovePreferenceRange, GroovePreferenceSummary
from app.preference import PREFERENCE_FEATURES, preference_features
from app.preference_scope import GLOBAL_PREFERENCE_SCOPE, normalize_preference_scope
from app.preference_scoring import PreferenceEvidencePair, discriminative_range_evidence


class GrooveDatabase:
    def __init__(self, path: Path = DATABASE_PATH):
        self.path = path
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY, candidate_a TEXT NOT NULL, candidate_b TEXT NOT NULL,
                    selected TEXT NOT NULL, display_order TEXT NOT NULL,
                    feature_delta TEXT NOT NULL,
                    created_at TEXT NOT NULL, schema_version TEXT NOT NULL,
                    comparison_id TEXT, decision_time_ms INTEGER,
                    features_a TEXT, features_b TEXT,
                    profile_scope TEXT NOT NULL DEFAULT '__global__'
                );
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY, pattern_id TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS saved_patterns (
                    pattern_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_presets (
                    name TEXT PRIMARY KEY, intent TEXT NOT NULL, updated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS blind_evaluations (
                    session_id TEXT PRIMARY KEY,
                    participant_group TEXT NOT NULL,
                    left_variant TEXT NOT NULL,
                    right_variant TEXT NOT NULL,
                    left_pattern TEXT NOT NULL,
                    right_pattern TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    selected TEXT,
                    decision_time_ms INTEGER,
                    saved_choice TEXT,
                    responded_at TEXT,
                    study_run_id TEXT,
                    trial_index INTEGER,
                    stimulus_key TEXT,
                    study_config_key TEXT,
                    schema_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_blind_evaluations_response
                    ON blind_evaluations(responded_at, participant_group);
                CREATE TABLE IF NOT EXISTS embodied_evaluations (
                    id INTEGER PRIMARY KEY,
                    anonymous_session_id TEXT NOT NULL,
                    pattern_id TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    operator_arm TEXT NOT NULL,
                    meter TEXT NOT NULL,
                    bpm REAL NOT NULL,
                    style TEXT NOT NULL,
                    sound_profile TEXT NOT NULL,
                    urge_to_move INTEGER NOT NULL,
                    pleasure INTEGER NOT NULL,
                    beat_clarity INTEGER NOT NULL,
                    familiarity INTEGER,
                    style_liking INTEGER,
                    tap_observation TEXT,
                    motion_observation TEXT,
                    listening_context TEXT NOT NULL,
                    posture TEXT NOT NULL,
                    motion_consent INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_embodied_evaluations_pattern
                    ON embodied_evaluations(pattern_id, created_at);
                CREATE TABLE IF NOT EXISTS motor_tempo_profiles (
                    anonymous_session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(preferences)")}
            if "features_a" not in columns:
                db.execute("ALTER TABLE preferences ADD COLUMN features_a TEXT")
            if "features_b" not in columns:
                db.execute("ALTER TABLE preferences ADD COLUMN features_b TEXT")
            if "comparison_id" not in columns:
                db.execute("ALTER TABLE preferences ADD COLUMN comparison_id TEXT")
            if "decision_time_ms" not in columns:
                db.execute("ALTER TABLE preferences ADD COLUMN decision_time_ms INTEGER")
            if "profile_scope" not in columns:
                db.execute(
                    "ALTER TABLE preferences ADD COLUMN profile_scope TEXT NOT NULL "
                    "DEFAULT '__global__'"
                )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_preferences_comparison_id "
                "ON preferences(comparison_id) WHERE comparison_id IS NOT NULL"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_preferences_scope ON preferences(profile_scope,id)"
            )
            self._backfill_preference_scopes(db)
            evaluation_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(blind_evaluations)")
            }
            for column, definition in (
                ("study_run_id", "TEXT"),
                ("trial_index", "INTEGER"),
                ("stimulus_key", "TEXT"),
                ("study_config_key", "TEXT"),
            ):
                if column not in evaluation_columns:
                    db.execute(f"ALTER TABLE blind_evaluations ADD COLUMN {column} {definition}")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_blind_study_trial "
                "ON blind_evaluations(study_run_id,trial_index)"
            )

    @staticmethod
    def _backfill_preference_scopes(db: sqlite3.Connection) -> None:
        rows = db.execute(
            "SELECT id,candidate_a,candidate_b,created_at FROM preferences WHERE profile_scope=?",
            (GLOBAL_PREFERENCE_SCOPE,),
        ).fetchall()
        for row in rows:
            scopes: list[str] = []
            for pattern_id in (row["candidate_a"], row["candidate_b"]):
                generation = db.execute(
                    "SELECT payload FROM generations WHERE pattern_id=? AND created_at<=? "
                    "ORDER BY created_at DESC,id DESC LIMIT 1",
                    (pattern_id, row["created_at"]),
                ).fetchone()
                if generation is None:
                    generation = db.execute(
                        "SELECT payload FROM generations WHERE pattern_id=? "
                        "ORDER BY created_at DESC,id DESC LIMIT 1",
                        (pattern_id,),
                    ).fetchone()
                if generation is None:
                    scopes = []
                    break
                try:
                    pattern = GroovePattern.model_validate_json(generation["payload"])
                except ValueError:
                    scopes = []
                    break
                scopes.append(normalize_preference_scope(pattern.metadata.style))
            if len(scopes) == 2 and scopes[0] == scopes[1]:
                db.execute(
                    "UPDATE preferences SET profile_scope=? WHERE id=?",
                    (scopes[0], row["id"]),
                )

    def save_generation(self, pattern: GroovePattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO generations(pattern_id,payload,created_at,schema_version) "
                "VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def save_pattern(self, pattern: GroovePattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO saved_patterns VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def save_preference(self, request: PreferenceRequest) -> bool:
        # Client analysis is presentation data and may be stale after an edit. Recompute the
        # structural measurements before allowing a choice to influence the personal model.
        candidate_a = request.candidate_a.model_copy(deep=True)
        candidate_b = request.candidate_b.model_copy(deep=True)
        candidate_a.analysis = analyze_pattern(candidate_a, include_render=False)
        candidate_b.analysis = analyze_pattern(candidate_b, include_render=False)
        features_a = preference_features(candidate_a)
        features_b = preference_features(candidate_b)
        delta = {
            key: features_a[key] - features_b[key] for key in features_a.keys() & features_b.keys()
        }
        display_order = json.dumps(request.display_order)
        profile_scope = normalize_preference_scope(request.candidate_a.metadata.style)
        submitted = (
            request.candidate_a.pattern_id,
            request.candidate_b.pattern_id,
            request.selected,
            display_order,
            request.decision_time_ms,
            profile_scope,
        )
        with self.connect() as db:
            existing = db.execute(
                "SELECT candidate_a,candidate_b,selected,display_order,decision_time_ms,"
                "profile_scope "
                "FROM preferences WHERE comparison_id=?",
                (request.comparison_id,),
            ).fetchone()
            if existing is not None:
                stored = tuple(existing)
                if stored == submitted:
                    return False
                raise ValueError("comparison ID has already been used")
            try:
                db.execute(
                    "INSERT INTO preferences(candidate_a,candidate_b,selected,display_order,"
                    "feature_delta,created_at,schema_version,features_a,features_b,"
                    "comparison_id,decision_time_ms,profile_scope) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        request.candidate_a.pattern_id,
                        request.candidate_b.pattern_id,
                        request.selected,
                        display_order,
                        json.dumps(delta),
                        datetime.now(UTC).isoformat(),
                        SCHEMA_VERSION,
                        json.dumps(features_a),
                        json.dumps(features_b),
                        request.comparison_id,
                        request.decision_time_ms,
                        profile_scope,
                    ),
                )
            except sqlite3.IntegrityError as error:
                existing = db.execute(
                    "SELECT candidate_a,candidate_b,selected,display_order,decision_time_ms,"
                    "profile_scope "
                    "FROM preferences WHERE comparison_id=?",
                    (request.comparison_id,),
                ).fetchone()
                if existing is not None and tuple(existing) == submitted:
                    return False
                raise ValueError("comparison ID has already been used") from error
        return True

    def preference_summary(self, profile_scope: str | None = None) -> GroovePreferenceSummary:
        with self.connect() as db:
            if profile_scope is None:
                rows = db.execute(
                    "SELECT selected,feature_delta,features_a,features_b "
                    "FROM preferences ORDER BY id"
                ).fetchall()
            else:
                profile_scope = normalize_preference_scope(profile_scope)
                rows = db.execute(
                    "SELECT selected,feature_delta,features_a,features_b "
                    "FROM preferences WHERE profile_scope=? ORDER BY id",
                    (profile_scope,),
                ).fetchall()
        weights = {key: 0.0 for key in PREFERENCE_FEATURES}
        selected_vectors: dict[tuple[float, ...], dict[str, float]] = {}
        delta_occurrences: dict[tuple[float, ...], int] = {}
        decisive_occurrences: dict[tuple[float, ...], int] = {}
        decisive_pairs: list[PreferenceEvidencePair] = []
        regularization = 0.05
        for index, row in enumerate(rows):
            delta = json.loads(row["feature_delta"] or "{}")
            signature = tuple(
                round(abs(float(delta.get(key, 0))), 3) for key in PREFERENCE_FEATURES
            )
            occurrence = delta_occurrences.get(signature, 0) + 1
            delta_occurrences[signature] = occurrence
            repeat_weight = 1 / math.sqrt(occurrence)
            label = {"A": 1.0, "B": 0.0, "tie": 0.5}[row["selected"]]
            sample_weight = repeat_weight * (0.35 if row["selected"] == "tie" else 1)
            logit = sum(weights.get(key, 0) * float(value) for key, value in delta.items())
            probability = 1 / (1 + math.exp(-max(-30, min(30, logit))))
            learning_rate = 0.24 * sample_weight / math.sqrt(index + 1)
            for key in PREFERENCE_FEATURES:
                value = float(delta.get(key, 0))
                gradient = (label - probability) * value - regularization * weights[key]
                weights[key] += learning_rate * gradient
            left = json.loads(row["features_a"] or "{}")
            right = json.loads(row["features_b"] or "{}")
            chosen = left if row["selected"] == "A" else right if row["selected"] == "B" else {}
            if row["selected"] != "tie":
                decisive_occurrences[signature] = decisive_occurrences.get(signature, 0) + 1
                rejected = right if row["selected"] == "A" else left
                decisive_pairs.append((chosen, rejected, repeat_weight))
            if chosen:
                vector_key = tuple(
                    round(float(chosen.get(key, 0)), 3) for key in PREFERENCE_FEATURES
                )
                selected_vectors[vector_key] = chosen

        ranges: dict[str, GroovePreferenceRange] = {}
        for key in PREFERENCE_FEATURES:
            values = [float(vector[key]) for vector in selected_vectors.values() if key in vector]
            if not values:
                continue
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            deviation = math.sqrt(variance)
            uncertainty = min(1.0, 1 / math.sqrt(len(values)) + deviation * 0.35)
            radius = max(0.06, 1.5 * deviation + uncertainty * 0.08)
            ranges[key] = GroovePreferenceRange(
                mean=max(0, min(1, mean)),
                low=max(0, mean - radius),
                high=min(1, mean + radius),
                uncertainty=uncertainty,
                observations=len(values),
                evidence=discriminative_range_evidence(
                    key,
                    mean=mean,
                    low=max(0, mean - radius),
                    high=min(1, mean + radius),
                    pairs=decisive_pairs,
                ),
            )
        decisive = sum(row["selected"] != "tie" for row in rows)
        ties = len(rows) - decisive
        effective = sum(math.sqrt(count) for count in decisive_occurrences.values())
        confidence = min(1.0, effective / 25)
        return GroovePreferenceSummary(
            comparisons=len(rows),
            decisive_comparisons=decisive,
            ties=ties,
            effective_comparisons=effective,
            learning_confidence=confidence,
            personal_weight=0.8 * confidence,
            feature_weights={key: value for key, value in weights.items() if abs(value) > 1e-9},
            preferred_ranges=ranges,
            profile_scope=profile_scope,
        )

    def save_preset(self, name: str, intent: GrooveIntent) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO user_presets VALUES(?,?,?,?)",
                (name, intent.model_dump_json(), datetime.now(UTC).isoformat(), SCHEMA_VERSION),
            )

    def user_presets(self) -> dict[str, GrooveIntent]:
        with self.connect() as db:
            rows = db.execute("SELECT name,intent FROM user_presets ORDER BY name").fetchall()
        return {row["name"]: GrooveIntent.model_validate_json(row["intent"]) for row in rows}

    def create_blind_evaluation(
        self,
        *,
        session_id: str,
        participant_group: str,
        left_variant: str,
        right_variant: str,
        left_pattern: GroovePattern,
        right_pattern: GroovePattern,
        started_at: datetime,
        study_run_id: str,
        trial_index: int,
        stimulus_key: str,
        study_config_key: str,
    ) -> None:
        with self.connect() as db:
            existing_trials = db.execute(
                "SELECT participant_group,trial_index,stimulus_key,study_config_key "
                "FROM blind_evaluations WHERE study_run_id=?",
                (study_run_id,),
            ).fetchall()
            if any(row["trial_index"] == trial_index for row in existing_trials):
                raise ValueError("this study trial has already been created")
            if any(row["participant_group"] != participant_group for row in existing_trials):
                raise ValueError("participant group cannot change inside a study block")
            if any(
                row["study_config_key"] and row["study_config_key"] != study_config_key
                for row in existing_trials
            ):
                raise ValueError("generation settings cannot change inside a study block")
            anchor = next((row for row in existing_trials if row["trial_index"] == 0), None)
            if trial_index > 0 and anchor is None:
                raise ValueError("the first study trial must be created before later trials")
            if trial_index == 5 and anchor["stimulus_key"] != stimulus_key:
                raise ValueError("the final study trial must repeat the first stimulus")
            if trial_index < 5 and any(
                row["stimulus_key"] == stimulus_key for row in existing_trials
            ):
                raise ValueError("study trials one through five must use distinct stimuli")
            try:
                db.execute(
                    "INSERT INTO blind_evaluations("
                    "session_id,participant_group,left_variant,right_variant,left_pattern,"
                    "right_pattern,started_at,study_run_id,trial_index,stimulus_key,"
                    "study_config_key,schema_version) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        session_id,
                        participant_group,
                        left_variant,
                        right_variant,
                        left_pattern.model_dump_json(),
                        right_pattern.model_dump_json(),
                        started_at.isoformat(),
                        study_run_id,
                        trial_index,
                        stimulus_key,
                        study_config_key,
                        SCHEMA_VERSION,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("this study trial has already been created") from error

    def blind_evaluation(self, session_id: str) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute(
                "SELECT * FROM blind_evaluations WHERE session_id=?", (session_id,)
            ).fetchone()

    def answer_blind_evaluation(
        self,
        *,
        session_id: str,
        selected: str,
        decision_time_ms: int,
        saved_choice: str,
    ) -> sqlite3.Row:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM blind_evaluations WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            if row["responded_at"] is not None:
                raise RuntimeError("this listening session has already been answered")
            db.execute(
                "UPDATE blind_evaluations SET selected=?,decision_time_ms=?,saved_choice=?,"
                "responded_at=? WHERE session_id=? AND responded_at IS NULL",
                (
                    selected,
                    decision_time_ms,
                    saved_choice,
                    datetime.now(UTC).isoformat(),
                    session_id,
                ),
            )
            return row

    def completed_blind_evaluations(self) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute(
                "SELECT participant_group,left_variant,right_variant,selected,"
                "decision_time_ms,saved_choice,study_run_id,trial_index,stimulus_key "
                "FROM blind_evaluations "
                "WHERE responded_at IS NOT NULL ORDER BY responded_at"
            ).fetchall()

    def save_motor_tempo_profile(
        self, anonymous_session_id: str, profile: MotorTempoProfile
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO motor_tempo_profiles VALUES(?,?,?,?)",
                (
                    anonymous_session_id,
                    profile.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    "embodied-1.0",
                ),
            )

    def motor_tempo_profile(self, anonymous_session_id: str | None) -> MotorTempoProfile | None:
        if not anonymous_session_id:
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM motor_tempo_profiles WHERE anonymous_session_id=?",
                (anonymous_session_id,),
            ).fetchone()
        return MotorTempoProfile.model_validate_json(row["payload"]) if row else None

    def save_embodied_evaluation(self, request: EmbodiedEvaluationRequest) -> None:
        pattern = request.pattern
        with self.connect() as db:
            db.execute(
                "INSERT INTO embodied_evaluations("
                "anonymous_session_id,pattern_id,engine_version,operator_arm,meter,bpm,"
                "style,sound_profile,urge_to_move,pleasure,beat_clarity,familiarity,"
                "style_liking,tap_observation,motion_observation,listening_context,"
                "posture,motion_consent,created_at,schema_version) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request.anonymous_session_id,
                    pattern.pattern_id,
                    pattern.metadata.engine_version,
                    pattern.metadata.embodied_operator_arm,
                    f"{pattern.meter.numerator}/{pattern.meter.denominator}",
                    pattern.bpm,
                    pattern.metadata.style,
                    pattern.metadata.render_profile,
                    request.urge_to_move,
                    request.pleasure,
                    request.beat_clarity,
                    request.familiarity,
                    request.style_liking,
                    request.tap_observation.model_dump_json() if request.tap_observation else None,
                    request.motion_observation.model_dump_json()
                    if request.motion_observation
                    else None,
                    request.listening_context,
                    request.posture,
                    int(request.motion_consent),
                    datetime.now(UTC).isoformat(),
                    "embodied-1.0",
                ),
            )

    def embodied_operator_scores(
        self, anonymous_session_id: str | None, style: str, meter: str
    ) -> dict[str, float]:
        """Conservative personal feedback prior, shrunk to neutral when sparse."""
        if not anonymous_session_id:
            return {}
        with self.connect() as db:
            rows = db.execute(
                "SELECT operator_arm,urge_to_move,pleasure FROM embodied_evaluations "
                "WHERE anonymous_session_id=? AND style=? AND meter=?",
                (anonymous_session_id, style, meter),
            ).fetchall()
        grouped: dict[str, list[float]] = {}
        for row in rows:
            grouped.setdefault(row["operator_arm"], []).append(
                (row["urge_to_move"] + row["pleasure"]) / 200
            )
        # Two neutral pseudo-observations keep a single reaction from hard-locking search.
        return {arm: (sum(values) + 1.0) / (len(values) + 2) for arm, values in grouped.items()}

    def embodied_evaluation_summary(
        self, anonymous_session_id: str | None
    ) -> EmbodiedEvaluationSummary:
        if not anonymous_session_id:
            return EmbodiedEvaluationSummary(total_evaluations=0, operator_arms=[])
        with self.connect() as db:
            rows = db.execute(
                "SELECT operator_arm,COUNT(*) AS evaluations,"
                "AVG(urge_to_move) AS urge,AVG(pleasure) AS pleasure,"
                "AVG(beat_clarity) AS clarity "
                "FROM embodied_evaluations WHERE anonymous_session_id=? "
                "GROUP BY operator_arm ORDER BY evaluations DESC, operator_arm",
                (anonymous_session_id,),
            ).fetchall()
        arms = [
            EmbodiedOperatorSummary(
                operator_arm=row["operator_arm"],
                evaluations=row["evaluations"],
                average_urge_to_move=round(row["urge"], 1),
                average_pleasure=round(row["pleasure"], 1),
                average_beat_clarity=round(row["clarity"], 1),
            )
            for row in rows
        ]
        total = sum(arm.evaluations for arm in arms)
        return EmbodiedEvaluationSummary(
            total_evaluations=total,
            operator_arms=arms,
            sufficient_for_personal_comparison=any(arm.evaluations >= 8 for arm in arms),
        )
