"""Predictive intelligence models — Security Trajectory.

Satisfies: REQ-021
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrendDirection(str, Enum):
    """Directional classification of an agent trust score trajectory."""

    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    RECOVERING = "RECOVERING"
    VOLATILE = "VOLATILE"


class TrajectoryProjection(BaseModel):
    """Forward-looking Security_Trajectory for an agent.

    All projected values are labeled PROJECTED and never stored as Evidence_Records.
    Satisfies: REQ-021
    """

    model_config = ConfigDict(strict=True)

    projection_id: UUID
    session_id: UUID
    agent_id: str
    trend: TrendDirection
    projected_trust_at_horizon: float = Field(ge=0.0, le=1.0)
    """Projected trust score at the configured horizon. Labeled PROJECTED (REQ-021.6)."""

    horizon_seconds: float
    confidence_interval: tuple[float, float]
    """(lower, upper) bounds at 95% confidence level."""

    early_warning: bool = False
    """True if projected score at horizon falls below warning threshold (REQ-021.5)."""

    warning_threshold: float
    is_projected: bool = True
    """ALWAYS True. All outputs labeled PROJECTED (REQ-021.6)."""

    is_stub: bool = True
    """True in Phase 1. Phase 2 implementation sets to False."""

    low_history_stub: bool = False
    """True when history < minimum required for trend analysis (REQ-021.2)."""

    computation_timestamp: datetime
