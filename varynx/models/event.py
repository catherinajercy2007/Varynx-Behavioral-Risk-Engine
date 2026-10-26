"""Event models — primary ingestion boundary for Varynx.

Satisfies: REQ-001, REQ-002, REQ-023
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """The category of operation an agent is performing."""

    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    DELETE = "DELETE"
    NETWORK_CALL = "NETWORK_CALL"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    TOOL_INVOCATION = "TOOL_INVOCATION"
    DELEGATION = "DELEGATION"


class AuthorizationResult(str, Enum):
    """Authorization outcome as reported by the agent runtime."""

    ALLOWED = "allowed"
    DENIED = "denied"
    PENDING = "pending"


class AgentActionEvent(BaseModel):
    """Primary ingestion boundary for Varynx.

    Represents a single discrete operation attempted by an autonomous AI agent.
    Satisfies: REQ-001.1, REQ-023.3
    """

    model_config = ConfigDict(strict=True)

    agent_id: str
    """Stable identity of the agent. Maps to Agent_Context record."""

    session_id: UUID
    """Session grouping identifier. Created by the API_Consumer."""

    timestamp: datetime
    """UTC timestamp of the action. Must be within ±300/60 seconds of system clock."""

    task_id: str | None = None
    """Optional task context identifier for cross-context correlation analysis."""

    action_type: ActionType
    """The category of operation the agent is performing."""

    capability_requested: str
    """The specific capability the agent claims to be exercising."""

    target_resource: str
    """The resource the action targets. Used for scope evaluation and spread tracking."""

    execution_context: dict[str, Any] = Field(default_factory=dict)
    """Free-form context bag. May include tool arguments, environment metadata, etc."""

    authorization_result: AuthorizationResult
    """The authorization outcome for this action as reported by the agent runtime."""

    behavioral_signals: dict[str, float] = Field(default_factory=dict)
    """Optional numeric signals from the agent runtime."""

    trust_signal: float | None = Field(default=None, ge=0.0, le=1.0)
    """Optional trust hint from the agent framework. Range [0.0, 1.0]."""

    is_simulated: bool
    """REQUIRED. True for all events produced by the SimulatedEventAdapter or scenario files.

    Simulated and non-simulated events must never be mixed in the same evaluation
    metric computation (REQ-027.12).
    """


class ValidatedEvent(BaseModel):
    """An AgentActionEvent that has passed ingestion validation.

    Adds system-assigned event_id and correlation_id.
    Satisfies: REQ-001.1, REQ-001.5
    """

    model_config = ConfigDict(strict=True)

    event_id: UUID
    """System-assigned unique identifier for this event."""

    correlation_id: UUID
    """System-assigned correlation identifier. Propagated through the full pipeline."""

    agent_id: str
    session_id: UUID
    timestamp: datetime
    task_id: str | None = None
    action_type: ActionType
    capability_requested: str
    target_resource: str
    execution_context: dict[str, Any] = Field(default_factory=dict)
    authorization_result: AuthorizationResult
    behavioral_signals: dict[str, float] = Field(default_factory=dict)
    trust_signal: float | None = Field(default=None, ge=0.0, le=1.0)
    is_simulated: bool

    @classmethod
    def from_event(
        cls,
        event: AgentActionEvent,
        event_id: UUID,
        correlation_id: UUID,
    ) -> ValidatedEvent:
        """Create a ValidatedEvent from an accepted AgentActionEvent."""
        return cls(
            event_id=event_id,
            correlation_id=correlation_id,
            agent_id=event.agent_id,
            session_id=event.session_id,
            timestamp=event.timestamp,
            task_id=event.task_id,
            action_type=event.action_type,
            capability_requested=event.capability_requested,
            target_resource=event.target_resource,
            execution_context=event.execution_context,
            authorization_result=event.authorization_result,
            behavioral_signals=event.behavioral_signals,
            trust_signal=event.trust_signal,
            is_simulated=event.is_simulated,
        )
