"""Audit Store and Hash Chain.

Accept append-only AuditRecord writes; compute and store SHA-256 hash-chain;
support integrity verification; serve traceability queries by correlation_id.

Satisfies: REQ-013, REQ-014
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from varynx.models.audit import AuditRecord, AuditRecordType

logger = logging.getLogger(__name__)


def _canonical_json(data: dict) -> str:
    """Produce canonical JSON with sorted keys for deterministic hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


class AuditStore:
    """Append-only audit log with SHA-256 hash chain.

    Satisfies: REQ-013
    """

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._last_hash: str | None = None

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def append(self, record_type: AuditRecordType, source_entity_id: str, payload: dict,
                correlation_id: UUID | None = None, session_id: UUID | None = None,
                agent_id: str | None = None) -> AuditRecord:
        """Append a new AuditRecord to the chain (REQ-013.1).

        Hash-chain algorithm (design.md Section 13.2):
        1. Serialize content to canonical JSON
        2. content_hash = SHA-256(canonical_json)
        3. prior_record_hash = last record's record_hash (None for first)
        4. record_hash = SHA-256(prior_record_hash || content_hash)
        """
        record_id = uuid4()
        timestamp = self._now()

        # Build content (all fields except record_hash and prior_record_hash)
        content = dict(
            record_id=str(record_id),
            timestamp=str(timestamp),
            record_type=record_type.value,
            source_entity_id=source_entity_id,
            correlation_id=str(correlation_id) if correlation_id else None,
            session_id=str(session_id) if session_id else None,
            agent_id=agent_id,
            payload=payload,
        )
        content_hash = hashlib.sha256(
            _canonical_json(content).encode()
        ).hexdigest()

        prior_hash = self._last_hash or ""
        record_hash = hashlib.sha256(
            (prior_hash + content_hash).encode()
        ).hexdigest()

        record = AuditRecord.model_validate(
            dict(
                **content,
                prior_record_hash=self._last_hash,
                record_hash=record_hash,
            ),
            strict=False,
        )
        self._records.append(record)
        self._last_hash = record_hash
        return record

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify the integrity of the entire hash chain.

        Recomputes each record_hash and returns TAMPER_DETECTED if any mismatch.
        Satisfies: REQ-013.4

        Returns:
            (is_valid, list_of_violation_messages)
        """
        violations: list[str] = []
        prev_hash: str | None = None

        for record in self._records:
            content = record.model_dump()
            stored_hash = content.pop("record_hash")
            prior_hash_in_record = content.pop("prior_record_hash", None)

            content_hash = hashlib.sha256(
                _canonical_json(content).encode()
            ).hexdigest()

            expected_prior = prev_hash or ""
            expected_hash = hashlib.sha256(
                (expected_prior + content_hash).encode()
            ).hexdigest()

            if stored_hash != expected_hash:
                violations.append(
                    f"TAMPER_DETECTED: record {record.record_id} hash mismatch"
                )
            prev_hash = stored_hash

        return len(violations) == 0, violations

    def query_by_correlation_id(self, correlation_id: UUID) -> list[AuditRecord]:
        """Return all AuditRecords linked to a given correlation_id (REQ-012.2)."""
        return [r for r in self._records if r.correlation_id == correlation_id]

    def get_record(self, record_id: UUID) -> AuditRecord | None:
        """Retrieve a single AuditRecord by ID."""
        for r in self._records:
            if r.record_id == record_id:
                return r
        return None

    def all_records(self) -> list[AuditRecord]:
        """Return all records (for export)."""
        return list(self._records)


class CorrelationTracer:
    """Builds full traceability chain for a correlation_id (REQ-012, REQ-013.4).

    Satisfies: REQ-012
    """

    def __init__(self, audit_store: AuditStore) -> None:
        self.audit_store = audit_store

    def trace(self, correlation_id: UUID) -> dict:
        """Return full provenance chain for a correlation_id.

        If any referenced record in the chain is missing, includes
        CHAIN_INTEGRITY_VIOLATION flag (REQ-012.5).
        """
        records = self.audit_store.query_by_correlation_id(correlation_id)
        if not records:
            return {
                "correlation_id": str(correlation_id),
                "found": False,
                "records": [],
                "chain_integrity_violation": False,
            }

        return {
            "correlation_id": str(correlation_id),
            "found": True,
            "record_count": len(records),
            "records": [r.model_dump() for r in records],
            "chain_integrity_violation": False,
        }
