"""Small SQLite-backed JSON record store for identity and lease state.

Integrity hashes detect accidental/torn record modification. They are not
cryptographic authentication against an attacker able to rewrite the database.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from threading import RLock


class RecordIntegrityError(RuntimeError):
    """Raised when a persisted record fails its integrity check."""


class SQLiteRecordStore:
    def __init__(self, database_path: str | Path, table: str) -> None:
        if not table.replace("_", "").isalnum():
            raise ValueError("Invalid table name")
        self.database_path = str(database_path)
        self.table = table
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self.database_path, timeout=10.0, check_same_thread=False
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.execute(
            f"CREATE TABLE IF NOT EXISTS {self.table} ("
            "record_key TEXT PRIMARY KEY, payload TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.commit()

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def load_all(self) -> dict[str, str]:
        with self._lock:
            rows = self._connection.execute(
                f"SELECT record_key, payload, sha256 FROM {self.table}"
            ).fetchall()
            records: dict[str, str] = {}
            for key, payload, digest in rows:
                if self._digest(payload) != digest:
                    raise RecordIntegrityError(
                        f"Persisted {self.table} record failed integrity check: {key}"
                    )
                # Reject malformed JSON before exposing state to the engine.
                json.loads(payload)
                records[key] = payload
            return records

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                f"SELECT payload, sha256 FROM {self.table} WHERE record_key=?", (key,)
            ).fetchone()
            if row is None:
                return None
            payload, digest = row
            if self._digest(payload) != digest:
                raise RecordIntegrityError(
                    f"Persisted {self.table} record failed integrity check: {key}"
                )
            json.loads(payload)
            return payload

    def put(self, key: str, payload: str) -> None:
        json.loads(payload)
        digest = self._digest(payload)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    f"INSERT INTO {self.table} (record_key,payload,sha256) VALUES (?,?,?) "
                    "ON CONFLICT(record_key) DO UPDATE SET payload=excluded.payload, "
                    "sha256=excluded.sha256, updated_at=CURRENT_TIMESTAMP",
                    (key, payload, digest),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()
