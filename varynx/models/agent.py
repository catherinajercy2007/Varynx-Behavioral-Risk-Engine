"""Agent and session models.

Satisfies: REQ-002, REQ-006
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRecord(BaseModel):
    """Persistent identity and authorization context for an agent.

    Satisfies: REQ-002.1, REQ-002.2
    """

    model_config = ConfigDict(strict=True)

    agent_id: str
    """Stable, immutable identifier. Must not change after creation (REQ-002.5)."""

    owning_principal: str
    """The owning principal identity. Immutable after creation (REQ-002.5)."""

    declared_capability_scope: list[str] = Field(default_factory=list)
    """Capability types the agent is declared to perform."""

    authorized_resource_scope: list[str] = Field(default_factory=list)
    """Resource patterns the agent is authorized to access."""

    registered_at: datetime
    """Timestamp of first observation / explicit registration."""

    scope_escalation_count: int = 0
    """Number of scope escalation events detected (REQ-002.3)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Extension point for framework-specific metadata."""


class SessionRecord(BaseModel):
    """Current session state for an agent.

    Satisfies: REQ-002, REQ-006
    """

    model_config = ConfigDict(strict=True)

    session_id: UUID
    agent_id: str
    started_at: datetime
    last_event_at: datetime | None = None
    ended_at: datetime | None = None
    current_trust: float = Field(default=0.7, ge=0.0, le=1.0)
    trust_level: str = "ELEVATED"
    state: str = "ACTIVE"
    resource_spread: dict[str, Any] = Field(default_factory=dict)
    """Distinct resource domains accessed this session and lifetime."""

    capability_spread: dict[str, Any] = Field(default_factory=dict)
    """Distinct capability types exercised this session and lifetime."""


class SessionContext(BaseModel):
    """Combined agent and session context for pipeline processing.

    Produced by the Identity & Session Registry.
    Satisfies: REQ-002, REQ-006
    """

    model_config = ConfigDict(strict=True)

    agent_record: AgentRecord
    session_record: SessionRecord
    active_lease_ids: list[UUID] = Field(default_factory=list)
    """IDs of ACTIVE Capability_Leases for this agent."""

    scope_escalation_detected: bool = False
    capability_escalation_detected: bool = False
