from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATABASE_PATH, SCHEMA_VERSION
from app.preference_scope import GLOBAL_PREFERENCE_SCOPE, normalize_preference_scope
from app.preference_scoring import PreferenceEvidencePair, discriminative_range_evidence

from .analysis import analyze_bass_pattern
from .models import (
    BassGenerationRecord,
    BassIntent,
    BassPattern,
    BassPreferenceRecord,
    BassPreferenceRequest,
    BassPreferenceSummary,
    PreferenceRange,
)
from .preference import PREFERENCE_FEATURES, preference_features


class BassDatabase:
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
                CREATE TABLE IF NOT EXISTS bass_generations (
                    id INTEGER PRIMARY KEY, pattern_id TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bass_user_presets (
                    name TEXT PRIMARY KEY, intent TEXT NOT NULL, updated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bass_saved_patterns (
                    pattern_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bass_preferences (
                    id INTEGER PRIMARY KEY, candidate_a TEXT NOT NULL, candidate_b TEXT NOT NULL,
                    selected TEXT NOT NULL, display_order TEXT NOT NULL,
                    feature_delta TEXT NOT NULL, created_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    comparison_id TEXT, decision_time_ms INTEGER,
                    features_a TEXT, features_b TEXT,
                    profile_scope TEXT NOT NULL DEFAULT '__global__'
                );
                CREATE INDEX IF NOT EXISTS idx_bass_generations_pattern
                    ON bass_generations(pattern_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_bass_generations_created
                    ON bass_generations(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_bass_preferences_created
                    ON bass_preferences(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_bass_saved_patterns_updated
                    ON bass_saved_patterns(updated_at DESC);
            """)
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(bass_preferences)").fetchall()
            }
            if "features_a" not in columns:
                db.execute("ALTER TABLE bass_preferences ADD COLUMN features_a TEXT")
            if "features_b" not in columns:
                db.execute("ALTER TABLE bass_preferences ADD COLUMN features_b TEXT")
            if "comparison_id" not in columns:
                db.execute("ALTER TABLE bass_preferences ADD COLUMN comparison_id TEXT")
            if "decision_time_ms" not in columns:
                db.execute("ALTER TABLE bass_preferences ADD COLUMN decision_time_ms INTEGER")
            if "profile_scope" not in columns:
                db.execute(
                    "ALTER TABLE bass_preferences ADD COLUMN profile_scope TEXT NOT NULL "
                    "DEFAULT '__global__'"
                )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_bass_preferences_comparison_id "
                "ON bass_preferences(comparison_id) WHERE comparison_id IS NOT NULL"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bass_preferences_scope "
                "ON bass_preferences(profile_scope,id)"
            )
            self._backfill_preference_scopes(db)

    @staticmethod
    def _backfill_preference_scopes(db: sqlite3.Connection) -> None:
        rows = db.execute(
            "SELECT id,candidate_a,candidate_b,created_at FROM bass_preferences "
            "WHERE profile_scope=?",
            (GLOBAL_PREFERENCE_SCOPE,),
        ).fetchall()
        for row in rows:
            scopes: list[str] = []
            for pattern_id in (row["candidate_a"], row["candidate_b"]):
                generation = db.execute(
                    "SELECT payload FROM bass_generations WHERE pattern_id=? AND created_at<=? "
                    "ORDER BY created_at DESC,id DESC LIMIT 1",
                    (pattern_id, row["created_at"]),
                ).fetchone()
                if generation is None:
                    generation = db.execute(
                        "SELECT payload FROM bass_generations WHERE pattern_id=? "
                        "ORDER BY created_at DESC,id DESC LIMIT 1",
                        (pattern_id,),
                    ).fetchone()
                if generation is None:
                    scopes = []
                    break
                try:
                    pattern = BassPattern.model_validate_json(generation["payload"])
                except ValueError:
                    scopes = []
                    break
                scopes.append(normalize_preference_scope(pattern.metadata.preset))
            if len(scopes) == 2 and scopes[0] == scopes[1]:
                db.execute(
                    "UPDATE bass_preferences SET profile_scope=? WHERE id=?",
                    (scopes[0], row["id"]),
                )

    def save_generation(self, pattern: BassPattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO bass_generations(pattern_id,payload,created_at,schema_version) "
                "VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def save_pattern(self, pattern: BassPattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO bass_saved_patterns "
                "(pattern_id,payload,updated_at,schema_version) VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def saved_patterns(self) -> list[BassPattern]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM bass_saved_patterns ORDER BY updated_at DESC"
            ).fetchall()
        return [BassPattern.model_validate_json(row["payload"]) for row in rows]

    def delete_pattern(self, pattern_id: str) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "DELETE FROM bass_saved_patterns WHERE pattern_id=?", (pattern_id,)
            )
        return cursor.rowcount > 0

    def generation_history(self, limit: int = 50) -> list[BassGenerationRecord]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,payload,created_at,schema_version FROM bass_generations "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BassGenerationRecord(
                generation_id=row["id"],
                pattern_id=(pattern := BassPattern.model_validate_json(row["payload"])).pattern_id,
                name=pattern.name,
                created_at=row["created_at"],
                schema_version=row["schema_version"],
            )
            for row in rows
        ]

    def generation_record_pattern(self, generation_id: int) -> BassPattern | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM bass_generations WHERE id=?", (generation_id,)
            ).fetchone()
        return BassPattern.model_validate_json(row["payload"]) if row else None

    def generation_pattern(self, pattern_id: str) -> BassPattern | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM bass_generations WHERE pattern_id=? ORDER BY id DESC LIMIT 1",
                (pattern_id,),
            ).fetchone()
        return BassPattern.model_validate_json(row["payload"]) if row else None

    def preference_history(self, limit: int = 50) -> list[BassPreferenceRecord]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT candidate_a,candidate_b,selected,display_order,comparison_id,"
                "decision_time_ms,profile_scope,created_at,schema_version "
                "FROM bass_preferences ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BassPreferenceRecord(
                candidate_a=row["candidate_a"],
                candidate_b=row["candidate_b"],
                selected=row["selected"],
                display_order=json.loads(row["display_order"]),
                comparison_id=row["comparison_id"],
                decision_time_ms=row["decision_time_ms"],
                profile_scope=row["profile_scope"],
                created_at=row["created_at"],
                schema_version=row["schema_version"],
            )
            for row in rows
        ]

    def save_preset(self, name: str, intent: BassIntent) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO bass_user_presets VALUES(?,?,?,?)",
                (
                    name,
                    intent.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def user_presets(self) -> dict[str, BassIntent]:
        with self.connect() as db:
            rows = db.execute("SELECT name,intent FROM bass_user_presets ORDER BY name").fetchall()
        return {row["name"]: BassIntent.model_validate_json(row["intent"]) for row in rows}

    def save_preference(self, request: BassPreferenceRequest) -> bool:
        # Never trust analysis sent by the browser: edits may leave it stale or manipulated.
        candidate_a = request.candidate_a.model_copy(deep=True)
        candidate_b = request.candidate_b.model_copy(deep=True)
        candidate_a.analysis = analyze_bass_pattern(candidate_a)
        candidate_b.analysis = analyze_bass_pattern(candidate_b)
        left = preference_features(candidate_a)
        right = preference_features(candidate_b)
        delta = {key: left[key] - right[key] for key in left.keys() & right.keys()}
        display_order = json.dumps(request.display_order)
        profile_scope = normalize_preference_scope(request.candidate_a.metadata.preset)
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
                "profile_scope FROM bass_preferences WHERE comparison_id=?",
                (request.comparison_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) == submitted:
                    return False
                raise ValueError("comparison ID has already been used")
            try:
                db.execute(
                    "INSERT INTO bass_preferences(candidate_a,candidate_b,selected,display_order,"
                    "feature_delta,created_at,schema_version,features_a,features_b,comparison_id,"
                    "decision_time_ms,profile_scope) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        request.candidate_a.pattern_id,
                        request.candidate_b.pattern_id,
                        request.selected,
                        display_order,
                        json.dumps(delta),
                        datetime.now(UTC).isoformat(),
                        SCHEMA_VERSION,
                        json.dumps(left),
                        json.dumps(right),
                        request.comparison_id,
                        request.decision_time_ms,
                        profile_scope,
                    ),
                )
            except sqlite3.IntegrityError as error:
                existing = db.execute(
                    "SELECT candidate_a,candidate_b,selected,display_order,decision_time_ms,"
                    "profile_scope FROM bass_preferences WHERE comparison_id=?",
                    (request.comparison_id,),
                ).fetchone()
                if existing is not None and tuple(existing) == submitted:
                    return False
                raise ValueError("comparison ID has already been used") from error
        return True

    def preference_summary(self, profile_scope: str | None = None) -> BassPreferenceSummary:
        with self.connect() as db:
            if profile_scope is None:
                rows = db.execute(
                    "SELECT selected,feature_delta,features_a,features_b "
                    "FROM bass_preferences ORDER BY id"
                ).fetchall()
            else:
                profile_scope = normalize_preference_scope(profile_scope)
                rows = db.execute(
                    "SELECT selected,feature_delta,features_a,features_b "
                    "FROM bass_preferences WHERE profile_scope=? ORDER BY id",
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

        ranges: dict[str, PreferenceRange] = {}
        for key in PREFERENCE_FEATURES:
            values = [
                float(vector[key]) for vector in selected_vectors.values() if key in vector
            ]
            if not values:
                continue
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            deviation = math.sqrt(variance)
            uncertainty = min(1.0, 1 / math.sqrt(len(values)) + deviation * 0.35)
            radius = max(0.06, 1.5 * deviation + uncertainty * 0.08)
            ranges[key] = PreferenceRange(
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
        return BassPreferenceSummary(
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
