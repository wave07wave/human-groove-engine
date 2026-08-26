from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATABASE_PATH, SCHEMA_VERSION
from app.models.api import PreferenceRequest
from app.models.groove import GrooveIntent
from app.models.pattern import GroovePattern


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
                    created_at TEXT NOT NULL, schema_version TEXT NOT NULL
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
            """)

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

    def save_preference(self, request: PreferenceRequest) -> None:
        features_a = (
            request.candidate_a.analysis.measured_dna.model_dump()
            if request.candidate_a.analysis
            else {}
        )
        features_b = (
            request.candidate_b.analysis.measured_dna.model_dump()
            if request.candidate_b.analysis
            else {}
        )
        delta = {key: features_a[key] - features_b[key] for key in features_a}
        with self.connect() as db:
            db.execute(
                "INSERT INTO preferences(candidate_a,candidate_b,selected,display_order,"
                "feature_delta,created_at,schema_version) VALUES(?,?,?,?,?,?,?)",
                (
                    request.candidate_a.pattern_id,
                    request.candidate_b.pattern_id,
                    request.selected,
                    json.dumps(request.display_order),
                    json.dumps(delta),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def preference_summary(self) -> dict:
        with self.connect() as db:
            rows = db.execute("SELECT selected, feature_delta FROM preferences").fetchall()
        weights: dict[str, float] = {}
        learning_rate, regularization = 0.08, 0.05
        for row in rows:
            sign = 1 if row["selected"] == "A" else -1
            for key, delta in json.loads(row["feature_delta"]).items():
                weights[key] = (
                    weights.get(key, 0) * (1 - regularization) + learning_rate * sign * delta
                )
        return {
            "comparisons": len(rows),
            "personal_weight": min(0.8, len(rows) / 25),
            "feature_weights": weights,
            "schema_version": SCHEMA_VERSION,
        }

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
