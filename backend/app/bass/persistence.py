from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATABASE_PATH, SCHEMA_VERSION

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
                    schema_version TEXT NOT NULL
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
                "SELECT payload,created_at,schema_version FROM bass_generations "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BassGenerationRecord(
                pattern_id=(pattern := BassPattern.model_validate_json(row["payload"])).pattern_id,
                name=pattern.name,
                created_at=row["created_at"],
                schema_version=row["schema_version"],
            )
            for row in rows
        ]

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
                "SELECT candidate_a,candidate_b,selected,display_order,created_at,schema_version "
                "FROM bass_preferences ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BassPreferenceRecord(
                candidate_a=row["candidate_a"],
                candidate_b=row["candidate_b"],
                selected=row["selected"],
                display_order=json.loads(row["display_order"]),
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

    def save_preference(self, request: BassPreferenceRequest) -> None:
        left = preference_features(request.candidate_a)
        right = preference_features(request.candidate_b)
        delta = {key: left[key] - right[key] for key in left.keys() & right.keys()}
        with self.connect() as db:
            db.execute(
                "INSERT INTO bass_preferences(candidate_a,candidate_b,selected,display_order,"
                "feature_delta,created_at,schema_version,features_a,features_b) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    request.candidate_a.pattern_id,
                    request.candidate_b.pattern_id,
                    request.selected,
                    json.dumps(request.display_order),
                    json.dumps(delta),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                    json.dumps(left),
                    json.dumps(right),
                ),
            )

    def preference_summary(self) -> BassPreferenceSummary:
        with self.connect() as db:
            rows = db.execute(
                "SELECT selected,feature_delta,features_a,features_b "
                "FROM bass_preferences ORDER BY id"
            ).fetchall()
        weights = {key: 0.0 for key in PREFERENCE_FEATURES}
        selected_vectors: list[dict[str, float]] = []
        regularization = 0.05
        for index, row in enumerate(rows):
            delta = json.loads(row["feature_delta"] or "{}")
            label = 1.0 if row["selected"] == "A" else 0.0
            logit = sum(weights.get(key, 0) * float(value) for key, value in delta.items())
            probability = 1 / (1 + math.exp(-max(-30, min(30, logit))))
            learning_rate = 0.24 / math.sqrt(index + 1)
            for key in PREFERENCE_FEATURES:
                value = float(delta.get(key, 0))
                gradient = (label - probability) * value - regularization * weights[key]
                weights[key] += learning_rate * gradient
            left = json.loads(row["features_a"] or "{}")
            right = json.loads(row["features_b"] or "{}")
            chosen = left if row["selected"] == "A" else right
            if chosen:
                selected_vectors.append(chosen)

        ranges: dict[str, PreferenceRange] = {}
        for key in PREFERENCE_FEATURES:
            values = [float(vector[key]) for vector in selected_vectors if key in vector]
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
            )
        return BassPreferenceSummary(
            comparisons=len(rows),
            personal_weight=min(0.8, len(rows) / 25),
            feature_weights={key: value for key, value in weights.items() if abs(value) > 1e-9},
            preferred_ranges=ranges,
        )
