"""Dynamic trust models.

Satisfies: REQ-005, REQ-021
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrustLevel(str, Enum):
    """Five trust level bands based on Behavioral_Trust_Score ranges.

    Thresholds are configurable defaults requiring empirical calibration (REQ-005.3).
    """

    HIGH = "HIGH"
    """Score range: [0.85, 1.00]. Agent behavior consistent with declared intent."""

    ELEVATED = "ELEVATED"
    """Score range: [0.65, 0.85). Acceptable behavioral patterns with minor signals."""

    GUARDED = "GUARDED"
    """Score range: [0.40, 0.65). Notable anomalies detected; monitoring recommended."""

    LOW = "LOW"
    """Score range: [0.20, 0.40). Significant behavioral anomalies; restriction warranted."""

    CRITICAL = "CRITICAL"
    """Score range: [0.00, 0.20). Severe behavioral anomalies; suspension/termination."""


class TrustHistoryEntry(BaseModel):
    """Single trust score update record.

    Satisfies: REQ-005.6
    """

    model_config = ConfigDict(strict=True)

    entry_id: UUID
    timestamp: datetime
    prior_score: float
    delta: float
    new_score: float
    contributing_evidence_ids: list[UUID] = Field(default_factory=list)
    excluded_incomplete_count: int = 0
    """Count of EVIDENCE_DERIVATION_INCOMPLETE records excluded from this update."""


class TrustState(BaseModel):
    """Per-agent dynamic trust state.

    Satisfies: REQ-005
    """

    model_config = ConfigDict(strict=True)

    session_id: UUID
    agent_id: str
    current_score: float = Field(ge=0.0, le=1.0, default=0.7)
    """Behavioral_Trust_Score. Always clamped to [0.0, 1.0] (REQ-005.2)."""

    level: TrustLevel = TrustLevel.ELEVATED
    history: list[TrustHistoryEntry] = Field(default_factory=list)
    last_updated: datetime
    session_age_seconds: float = 0.0
