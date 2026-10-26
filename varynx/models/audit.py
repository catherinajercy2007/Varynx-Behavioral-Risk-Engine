"""Audit log models — tamper-evident append-only record store.

Satisfies: REQ-013, REQ-014
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditRecordType(str, Enum):
    """Eight audit record types covering all significant pipeline events.

    Satisfies: REQ-013, design.md Section 13.1
    """

    EVENT_INGESTED = "EVENT_INGESTED"
    EVIDENCE_PRODUCED = "EVIDENCE_PRODUCED"
    TRUST_UPDATED = "TRUST_UPDATED"
    RESPONSE_RECOMMENDED = "RESPONSE_RECOMMENDED"
    ENFORCEMENT_APPLIED = "ENFORCEMENT_APPLIED"
    LEASE_STATE_CHANGED = "LEASE_STATE_CHANGED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_TERMINATED = "SESSION_TERMINATED"


class AuditRecord(BaseModel):
    """Tamper-evident, append-only record.

    References source records by ID only; never reproduces content (REQ-013.6).
    Satisfies: REQ-013
    """

    model_config = ConfigDict(strict=True)

    record_id: UUID
    timestamp: datetime
    record_type: AuditRecordType
    source_entity_id: str
    """ID of the primary entity this record concerns."""

    correlation_id: UUID | None = None
    """Propagated from originating Behavioral_Event (REQ-012.1)."""

    session_id: UUID | None = None
    agent_id: str | None = None
    payload: dict[str, Any] = {}
    """References only (IDs, status codes, reason strings). Never reproduces content."""

    prior_record_hash: str | None = None
    """SHA-256 of the previous record in the chain. None for first record."""

    record_hash: str
    """SHA-256(prior_record_hash || content_hash). Enables tamper detection (REQ-013.4)."""
