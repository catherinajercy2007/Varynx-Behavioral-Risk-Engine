"""Behavioral evidence models.

Satisfies: REQ-003, REQ-004
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnomalyClass(str, Enum):
    """Six behavioral anomaly classes detected by the evidence engine.

    Satisfies: REQ-004, design.md Section 8.1
    """

    CAPABILITY_ESCALATION = "CAPABILITY_ESCALATION"
    """Agent attempted an action outside its declared capability scope (REQ-002.4)."""

    RESOURCE_ANOMALY = "RESOURCE_ANOMALY"
    """Resource access pattern exceeds spread threshold within time window (REQ-004.3)."""

    ACTION_FREQUENCY = "ACTION_FREQUENCY"
    """Action rate exceeds configurable threshold within sliding window."""

    AUTHORIZATION_BYPASS_ATTEMPT = "AUTHORIZATION_BYPASS_ATTEMPT"
    """Three or more authorization denials within configurable window (REQ-004.2)."""

    CONTEXT_DEVIATION = "CONTEXT_DEVIATION"
    """Agent actions correlate to two or more distinct identities or task contexts (REQ-004.4)."""

    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"
    """Actions at statistically unusual times relative to agent historical pattern."""


class EvidenceRecord(BaseModel):
    """Immutable derived signal from a Behavioral_Event.

    Satisfies: REQ-003.1 through REQ-003.6
    """

    model_config = ConfigDict(strict=True)

    evidence_id: UUID
    event_id: UUID
    """Source Behavioral_Event identifier."""

    session_id: UUID
    agent_id: str
    correlation_id: UUID
    """Shared with source Behavioral_Event for end-to-end traceability (REQ-003.2)."""

    anomaly_class: AnomalyClass
    score: float = Field(ge=0.0, le=1.0)
    """Anomaly severity score. Invariant: always in [0.0, 1.0] (REQ-005.2)."""

    weight: float = Field(ge=0.0, le=1.0)
    """Detector weight for composite score calculation."""

    detector_id: str
    """Identifies which detector produced this record (REQ-003.3)."""

    contributing_signals: list[str] = Field(default_factory=list)
    """Signal keys from AgentActionEvent that contributed to this record."""

    provenance: dict[str, Any] = Field(default_factory=dict)
    """Full derivation record: method, params, inputs used (REQ-003.3)."""

    timestamp: datetime
    is_simulated: bool

    content_hash: str
    """SHA-256 of this record's content for tamper detection (REQ-003.6)."""

    derivation_status: str = "COMPLETE"
    """'COMPLETE' | 'EVIDENCE_DERIVATION_INCOMPLETE'. Incomplete records excluded from scoring."""


class EvidenceBundle(BaseModel):
    """Correlated collection of EvidenceRecords for a single event processing cycle.

    Satisfies: REQ-003, REQ-004
    """

    model_config = ConfigDict(strict=True)

    bundle_id: UUID
    session_id: UUID
    agent_id: str
    correlation_id: UUID
    records: list[EvidenceRecord] = Field(default_factory=list)
    composite_score: float = Field(ge=0.0, le=1.0)
    """Normalized composite anomaly score across all triggered detectors."""

    correlation_window_seconds: float
    timestamp: datetime
    is_simulated: bool
