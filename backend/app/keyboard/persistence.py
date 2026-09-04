from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATABASE_PATH, SCHEMA_VERSION

from .models import KeyboardGenerationRecord, KeyboardPattern


class KeyboardDatabase:
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
                CREATE TABLE IF NOT EXISTS keyboard_generations (
                    id INTEGER PRIMARY KEY, pattern_id TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS keyboard_saved_patterns (
                    pattern_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL, schema_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_keyboard_generations_pattern
                    ON keyboard_generations(pattern_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_keyboard_generations_created
                    ON keyboard_generations(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_keyboard_saved_patterns_updated
                    ON keyboard_saved_patterns(updated_at DESC);
            """)

    def save_generation(self, pattern: KeyboardPattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO keyboard_generations(pattern_id,payload,created_at,schema_version) "
                "VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def generation_history(self, limit: int = 50) -> list[KeyboardGenerationRecord]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,payload,created_at,schema_version FROM keyboard_generations "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        records = []
        for row in rows:
            pattern = KeyboardPattern.model_validate_json(row["payload"])
            records.append(
                KeyboardGenerationRecord(
                    generation_id=row["id"],
                    pattern_id=pattern.pattern_id,
                    name=pattern.name,
                    style=pattern.metadata.detroit_keyboard.mode,
                    created_at=row["created_at"],
                    schema_version=row["schema_version"],
                )
            )
        return records

    def generation_record_pattern(self, generation_id: int) -> KeyboardPattern | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM keyboard_generations WHERE id=?", (generation_id,)
            ).fetchone()
        return KeyboardPattern.model_validate_json(row["payload"]) if row else None

    def save_pattern(self, pattern: KeyboardPattern) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO keyboard_saved_patterns "
                "(pattern_id,payload,updated_at,schema_version) VALUES(?,?,?,?)",
                (
                    pattern.pattern_id,
                    pattern.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                    SCHEMA_VERSION,
                ),
            )

    def saved_patterns(self) -> list[KeyboardPattern]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM keyboard_saved_patterns ORDER BY updated_at DESC"
            ).fetchall()
        return [KeyboardPattern.model_validate_json(row["payload"]) for row in rows]

    def delete_pattern(self, pattern_id: str) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "DELETE FROM keyboard_saved_patterns WHERE pattern_id=?", (pattern_id,)
            )
        return cursor.rowcount > 0
