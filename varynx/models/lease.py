"""Capability lease models.

Satisfies: REQ-010
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeaseState(str, Enum):
    """Four-state lifecycle for Capability_Leases (REQ-010.1)."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class CapabilityLease(BaseModel):
    """Time-bounded, revocable authorization record for an agent capability.

    Satisfies: REQ-010
    """

    model_config = ConfigDict(strict=True)

    lease_id: UUID
    agent_id: str
    session_id: UUID
    capability: str
    resource_scope: dict[str, Any] = Field(default_factory=dict)
    """Resource patterns, action types, and constraints."""

    activation_timestamp: datetime
    expiry_timestamp: datetime | None = None
    """Immutable after activation (REQ-010.9)."""

    issuing_principal: str
    issuing_policy_id: str
    state: LeaseState = LeaseState.ACTIVE
    state_history: list[dict[str, Any]] = Field(default_factory=list)
    """Ordered log of state transitions with timestamp and reason."""


class LeaseEvaluation(BaseModel):
    """Result of evaluating whether an event is covered by an active lease.

    Satisfies: REQ-010
    """

    model_config = ConfigDict(strict=True)

    lease_id: UUID | None = None
    is_active: bool
    capability_covered: bool
    reason: str
    """Human-readable explanation of the evaluation result."""
