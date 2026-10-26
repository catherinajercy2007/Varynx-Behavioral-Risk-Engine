"""Identity and Session Registry.

Maintains Agent_Context records per distinct agent_id; creates records on first
observation; detects and flags scope escalation and capability escalation;
manages session lifecycle; tracks resource and capability spread.

Satisfies: REQ-002, REQ-006
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from varynx.models.agent import AgentRecord, SessionContext, SessionRecord
from varynx.models.event import ValidatedEvent


class SessionRegistryError(Exception):
    """Raised when session context cannot be resolved."""
    reason_code: str = "STORAGE_SUBSYSTEM_UNAVAILABLE"


class IdentitySessionRegistry:
    """In-memory Identity and Session Registry.

    Production deployment replaces with PostgreSQL-backed implementation.
    Satisfies: REQ-002, REQ-006
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._sessions: dict[UUID, SessionRecord] = {}

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def get_or_create_agent(self, event: ValidatedEvent) -> AgentRecord:
        """Retrieve or create an AgentRecord for the event's agent_id.

        REQ-002.1: Maintain a record per distinct agent_id.
        REQ-002.6: Create new record on first observation.
        REQ-002.5: agent_id and owning_principal are immutable after creation.
        """
        agent_id = event.agent_id
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentRecord(
                agent_id=agent_id,
                owning_principal="unknown",  # Set by explicit registration in production
                declared_capability_scope=[],
                authorized_resource_scope=[],
                registered_at=self._now(),
            )
        return self._agents[agent_id]

    def get_or_create_session(self, event: ValidatedEvent) -> SessionRecord:
        """Retrieve or create a SessionRecord for the event's session_id."""
        session_id = event.session_id
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionRecord(
                session_id=session_id,
                agent_id=event.agent_id,
                started_at=event.timestamp,
                last_event_at=event.timestamp,
            )
        else:
            session = self._sessions[session_id]
            # Update last_event_at
            self._sessions[session_id] = SessionRecord.model_validate(
                {**session.model_dump(), "last_event_at": event.timestamp},
                strict=False,
            )
        return self._sessions[session_id]

    def _detect_scope_escalation(
        self, agent: AgentRecord, event: ValidatedEvent
    ) -> bool:
        """Flag SCOPE_ESCALATION_DETECTED if resource is outside authorized scope.

        REQ-002.3: Increment escalation counter on scope escalation.
        """
        if not agent.authorized_resource_scope:
            return False  # No scope defined yet; no escalation to detect
        resource = event.target_resource
        return not any(
            resource.startswith(scope) for scope in agent.authorized_resource_scope
        )

    def _detect_capability_escalation(
        self, agent: AgentRecord, event: ValidatedEvent
    ) -> bool:
        """Flag CAPABILITY_ESCALATION_DETECTED if action outside declared capability scope.

        REQ-002.4: Detect when action_type is outside declared capability scope.
        """
        if not agent.declared_capability_scope:
            return False  # No scope defined; no escalation to detect
        return event.action_type.value not in agent.declared_capability_scope

    def _update_spread(
        self, session: SessionRecord, event: ValidatedEvent
    ) -> SessionRecord:
        """Update resource and capability spread tracking.

        REQ-006.1: Track distinct resource domains per agent lifetime.
        REQ-006.2: Track distinct capability types per agent lifetime.
        """
        spread = dict(session.model_dump())
        resource_spread: dict[str, bool] = dict(spread.get("resource_spread") or {})
        capability_spread: dict[str, bool] = dict(spread.get("capability_spread") or {})

        # Extract domain from resource path (simplified: use first path segment)
        parts = event.target_resource.strip("/").split("/")
        domain = parts[0] if parts else event.target_resource
        resource_spread[domain] = True
        capability_spread[event.action_type.value] = True

        spread["resource_spread"] = resource_spread
        spread["capability_spread"] = capability_spread
        return SessionRecord.model_validate(spread, strict=False)

    def process_event(self, event: ValidatedEvent) -> SessionContext:
        """Process a ValidatedEvent and return a SessionContext.

        Performs agent/session lookup, escalation detection, and spread tracking.
        Satisfies: REQ-002, REQ-006
        """
        agent = self.get_or_create_agent(event)
        session = self.get_or_create_session(event)

        scope_esc = self._detect_scope_escalation(agent, event)
        cap_esc = self._detect_capability_escalation(agent, event)

        if scope_esc:
            # Increment escalation counter (REQ-002.3)
            updated_agent = AgentRecord.model_validate(
                {
                    **agent.model_dump(),
                    "scope_escalation_count": agent.scope_escalation_count + 1,
                },
                strict=False,
            )
            self._agents[agent.agent_id] = updated_agent
            agent = updated_agent

        updated_session = self._update_spread(session, event)
        self._sessions[event.session_id] = updated_session

        return SessionContext(
            agent_record=agent,
            session_record=updated_session,
            active_lease_ids=[],
            scope_escalation_detected=scope_esc,
            capability_escalation_detected=cap_esc,
        )

    def register_agent(
        self,
        agent_id: str,
        owning_principal: str,
        declared_capability_scope: list[str],
        authorized_resource_scope: list[str],
    ) -> AgentRecord:
        """Explicitly register an agent with known scope.

        If agent already exists, updates scope (for testing/admin).
        Satisfies: REQ-002.2
        """
        agent = AgentRecord(
            agent_id=agent_id,
            owning_principal=owning_principal,
            declared_capability_scope=declared_capability_scope,
            authorized_resource_scope=authorized_resource_scope,
            registered_at=self._now(),
        )
        self._agents[agent_id] = agent
        return agent
