
"""Audit Store and Hash Chain.

Accept append-only AuditRecord writes, compute and store SHA-256 hash-chain;
support integrity verification; serve traceability queries by correlation_id.

Satisfies: REQ-013, REQ-014
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from varynx.models.audit import AuditRecord, AuditRecordType


def _canonical_json(data: dict) -> str:
    """Produce deterministic JSON with sorted keys for hashing."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class AuditStore:
    """Append-only in-memory audit log with a SHA-256 hash chain.

    Each record hash is calculated as:

        SHA256(previous_record_hash + SHA256(canonical_record_content))

    The first record uses an empty string as its previous hash.
    """

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._last_hash: str | None = None

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def append(
        self,
        record_type: AuditRecordType,
        source_entity_id: str,
        payload: dict,
        correlation_id: UUID | None = None,
        session_id: UUID | None = None,
        agent_id: str | None = None,
    ) -> AuditRecord:
        """Append a record and link it to the preceding record."""
        record_id = uuid4()
        timestamp = self._now()

        # These are the fields covered by the content hash.
        content = {
            "record_id": str(record_id),
            "timestamp": str(timestamp),
            "record_type": record_type.value,
            "source_entity_id": source_entity_id,
            "correlation_id": (
                str(correlation_id) if correlation_id is not None else None
            ),
            "session_id": str(session_id) if session_id is not None else None,
            "agent_id": agent_id,
            "payload": payload,
        }

        content_hash = hashlib.sha256(
            _canonical_json(content).encode("utf-8")
        ).hexdigest()

        prior_hash = self._last_hash
        record_hash = hashlib.sha256(
            ((prior_hash or "") + content_hash).encode("utf-8")
        ).hexdigest()

        record = AuditRecord.model_validate(
            {
                **content,
                "prior_record_hash": prior_hash,
                "record_hash": record_hash,
            },
            strict=False,
        )

        self._records.append(record)
        self._last_hash = record_hash
        return record

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify every record hash and every previous-record link.

        Returns:
            A tuple containing the validity flag and any detected violations.
        """
        violations: list[str] = []
        previous_hash: str | None = None

        for record in self._records:
            # Verify the explicit link, including None for the first record.
            if record.prior_record_hash != previous_hash:
                violations.append(
                    "TAMPER_DETECTED: "
                    f"record {record.record_id} has an invalid "
                    "prior_record_hash"
                )

            # Rebuild exactly the content used by append().
            content = record.model_dump()
            stored_hash = content.pop("record_hash")
            content.pop("prior_record_hash")

            content_hash = hashlib.sha256(
                _canonical_json(content).encode("utf-8")
            ).hexdigest()

            expected_hash = hashlib.sha256(
                ((previous_hash or "") + content_hash).encode("utf-8")
            ).hexdigest()

            if stored_hash != expected_hash:
                violations.append(
                    "TAMPER_DETECTED: "
                    f"record {record.record_id} hash mismatch"
                )

            # Continue from the stored hash so subsequent link corruption
            # is also reported rather than silently repairing the chain.
            previous_hash = stored_hash

        return not violations, violations

    def query_by_correlation_id(
        self,
        correlation_id: UUID,
    ) -> list[AuditRecord]:
        """Return records associated with a correlation ID."""
        return [
            record
            for record in self._records
            if record.correlation_id == correlation_id
        ]

    def get_record(self, record_id: UUID) -> AuditRecord | None:
        """Retrieve a record by its unique ID."""
        return next(
            (
                record
                for record in self._records
                if record.record_id == record_id
            ),
            None,
        )

    def all_records(self) -> list[AuditRecord]:
        """Return a shallow copy of the stored records."""
        return list(self._records)


class CorrelationTracer:
    """Build provenance traces for a correlation ID."""

    def __init__(self, audit_store: AuditStore) -> None:
        self.audit_store = audit_store

    def trace(self, correlation_id: UUID) -> dict:
        """Return matching records and the audit-chain integrity status."""
        records = self.audit_store.query_by_correlation_id(correlation_id)

        if not records:
            return {
                "correlation_id": str(correlation_id),
                "found": False,
                "records": [],
                "chain_integrity_violation": False,
            }

        chain_valid, violations = self.audit_store.verify_chain()

        return {
            "correlation_id": str(correlation_id),
            "found": True,
            "record_count": len(records),
            "records": [record.model_dump() for record in records],
            "chain_integrity_violation": not chain_valid,
            "chain_integrity_violations": violations,
        }

class SQLiteAuditStore(AuditStore):
    """SQLite-backed append-only audit store with a persistent SHA-256 chain.

    The database serializes appends with BEGIN IMMEDIATE. Records are reloaded
    before each append so multiple store instances sharing one database use the
    latest chain head. SQLite durability is local to the configured database.
    """

    def __init__(self, database_path: str) -> None:
        import sqlite3
        from pathlib import Path
        from threading import RLock

        super().__init__()
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = RLock()
        self._connection = sqlite3.connect(
            self.database_path,
            timeout=30.0,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_records (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL UNIQUE,
                record_hash TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                expected_count INTEGER NOT NULL,
                expected_head_hash TEXT
            )
            """
        )
        self._connection.commit()
        with self._db_lock:
            self._refresh_records()
            state = self._connection.execute(
                "SELECT expected_count FROM audit_state WHERE singleton = 1"
            ).fetchone()
            if state is None and not self._records:
                self._connection.execute(
                    """
                    INSERT INTO audit_state
                        (singleton, expected_count, expected_head_hash)
                    VALUES (1, 0, NULL)
                    """
                )
                self._connection.commit()

    def _refresh_records(self) -> None:
        rows = self._connection.execute(
            """
            SELECT record_id, record_hash, record_json
            FROM audit_records ORDER BY sequence
            """
        ).fetchall()
        self._records = []
        self._storage_violations: list[str] = []
        for stored_id, stored_hash, record_json in rows:
            record = AuditRecord.model_validate_json(record_json)
            self._records.append(record)
            if stored_id != str(record.record_id):
                self._storage_violations.append(
                    f"AUDIT_STORAGE_METADATA_MISMATCH: record_id {stored_id}"
                )
            if stored_hash != record.record_hash:
                self._storage_violations.append(
                    f"AUDIT_STORAGE_METADATA_MISMATCH: record_hash {stored_id}"
                )
        self._last_hash = self._records[-1].record_hash if self._records else None

    def append(
        self,
        record_type: AuditRecordType,
        source_entity_id: str,
        payload: dict,
        correlation_id: UUID | None = None,
        session_id: UUID | None = None,
        agent_id: str | None = None,
    ) -> AuditRecord:
        """Atomically append and persist a hash-linked record."""
        with self._db_lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._refresh_records()
                chain_valid, chain_violations = super().verify_chain()
                checkpoint = self._connection.execute(
                    """
                    SELECT expected_count, expected_head_hash
                    FROM audit_state WHERE singleton = 1
                    """
                ).fetchone()
                checkpoint_valid = checkpoint == (len(self._records), self._last_hash)
                if self._storage_violations or not chain_valid or not checkpoint_valid:
                    raise RuntimeError(
                        "AUDIT_CHAIN_INVALID: refusing append to a corrupted audit log"
                    )
                record = super().append(
                    record_type=record_type,
                    source_entity_id=source_entity_id,
                    payload=payload,
                    correlation_id=correlation_id,
                    session_id=session_id,
                    agent_id=agent_id,
                )
                record_json = record.model_dump_json()
                self._connection.execute(
                    """
                    INSERT INTO audit_records
                        (record_id, record_hash, record_json)
                    VALUES (?, ?, ?)
                    """,
                    (str(record.record_id), record.record_hash, record_json),
                )
                self._connection.execute(
                    """
                    UPDATE audit_state
                    SET expected_count = expected_count + 1,
                        expected_head_hash = ?
                    WHERE singleton = 1
                    """,
                    (record.record_hash,),
                )
                self._connection.commit()
                return record
            except Exception:
                self._connection.rollback()
                self._refresh_records()
                raise

    def verify_chain(self) -> tuple[bool, list[str]]:
        with self._db_lock:
            self._refresh_records()
            valid, violations = super().verify_chain()
            violations.extend(self._storage_violations)
            state = self._connection.execute(
                """
                SELECT expected_count, expected_head_hash
                FROM audit_state WHERE singleton = 1
                """
            ).fetchone()
            if state is None:
                violations.append("TAMPER_DETECTED: audit checkpoint is missing")
            else:
                expected_count, expected_head_hash = state
                if expected_count != len(self._records):
                    violations.append(
                        "TAMPER_DETECTED: audit record count differs from checkpoint"
                    )
                if expected_head_hash != self._last_hash:
                    violations.append(
                        "TAMPER_DETECTED: audit head differs from checkpoint"
                    )
            return not violations, violations

    def query_by_correlation_id(self, correlation_id: UUID) -> list[AuditRecord]:
        with self._db_lock:
            self._refresh_records()
            return super().query_by_correlation_id(correlation_id)

    def get_record(self, record_id: UUID) -> AuditRecord | None:
        with self._db_lock:
            self._refresh_records()
            return super().get_record(record_id)

    def all_records(self) -> list[AuditRecord]:
        with self._db_lock:
            self._refresh_records()
            return super().all_records()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._db_lock:
            self._connection.close()
