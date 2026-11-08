"""Identity and Session Registry.

Maintains Agent_Context records per distinct agent_id; creates records on first
observation; detects and flags scope escalation and capability escalation;
manages session lifecycle; tracks resource and capability spread.

Satisfies: REQ-002, REQ-006
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from varynx.engine.record_store import SQLiteRecordStore
from varynx.engine.resource_scope import resource_is_within_scope
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

    def __init__(self, persistence_path: str | Path | None = None) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._sessions: dict[UUID, SessionRecord] = {}
        self._agent_store = None
        self._session_store = None
        if persistence_path is not None:
            root = Path(persistence_path)
            root.mkdir(parents=True, exist_ok=True)
            database = root / "identity.sqlite3"
            self._agent_store = SQLiteRecordStore(database, "agents")
            self._session_store = SQLiteRecordStore(database, "sessions")
            self._agents = {
                key: AgentRecord.model_validate_json(value)
                for key, value in self._agent_store.load_all().items()
            }
            self._sessions = {
                UUID(key): SessionRecord.model_validate_json(value)
                for key, value in self._session_store.load_all().items()
            }

    def _save_agent(self, agent: AgentRecord) -> None:
        self._agents[agent.agent_id] = agent
        if self._agent_store is not None:
            self._agent_store.put(agent.agent_id, agent.model_dump_json())

    def _save_session(self, session: SessionRecord) -> None:
        self._sessions[session.session_id] = session
        if self._session_store is not None:
            self._session_store.put(str(session.session_id), session.model_dump_json())

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        return self._agents.get(agent_id)

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def create_session(self, session: SessionRecord) -> SessionRecord:
        existing = self._sessions.get(session.session_id)
        if existing is not None:
            if existing.agent_id != session.agent_id:
                raise SessionRegistryError(
                    f"Session {session_id} is owned by agent {session.agent_id!r}, not {event.agent_id!r} (session ownership violation)"
                )
            raise SessionRegistryError("Session already exists")
        if session.agent_id not in self._agents:
            raise SessionRegistryError("Agent must be registered before session creation")
        self._save_session(session)
        return session

    def terminate_session(self, session_id: UUID) -> SessionRecord:
        session = self.get_session(session_id)
        if session is None:
            raise SessionRegistryError("Session not found")
        if session.state == "TERMINATED":
            return session
        updated = SessionRecord.model_validate(
            {**session.model_dump(), "state": "TERMINATED", "ended_at": self._now()},
            strict=False,
        )
        return self._save_session_result(updated)

    def _save_session_result(self, session: SessionRecord) -> SessionRecord:
        self._save_session(session)
        return session

    def close(self) -> None:
        for store in (self._agent_store, self._session_store):
            if store is not None:
                store.close()

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
            self._save_agent(AgentRecord(
                agent_id=agent_id,
                owning_principal="unknown",  # Set by explicit registration in production
                declared_capability_scope=[],
                authorized_resource_scope=[],
                registered_at=self._now(),
            ))
        return self._agents[agent_id]

    def get_or_create_session(self, event: ValidatedEvent) -> SessionRecord:
        """Retrieve or create a SessionRecord for the event's session_id."""
        session_id = event.session_id
        if session_id not in self._sessions:
            self._save_session(SessionRecord(
                session_id=session_id,
                agent_id=event.agent_id,
                started_at=event.timestamp,
                last_event_at=event.timestamp,
            ))
        else:
            session = self._sessions[session_id]
            # Security: reject if session belongs to a different agent
            # This prevents cross-agent session reuse (REQ-002 session ownership).
            if session.agent_id != event.agent_id:
                raise SessionRegistryError(
                    f"Session {session_id} is owned by "
                    f"{session.agent_id!r}, not {event.agent_id!r}."
                    " Session ownership violation."
                )
            # Update last_event_at
            self._save_session(SessionRecord.model_validate(
                {**session.model_dump(), "last_event_at": event.timestamp},
                strict=False,
            ))
        return self._sessions[session_id]

    def _detect_scope_escalation(
        self, agent: AgentRecord, event: ValidatedEvent
    ) -> bool:
        """Flag SCOPE_ESCALATION_DETECTED if resource is outside authorized scope.

        REQ-002.3: Increment escalation counter on scope escalation.
        Fail-closed: empty authorized_resource_scope triggers escalation.
        Uses delimiter-aware matching (no unsafe startswith).
        """
        # Empty authorized scope = no authorized resources = escalation
        if not agent.authorized_resource_scope:
            return True
        return not resource_is_within_scope(
            event.target_resource, agent.authorized_resource_scope
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
            self._save_agent(updated_agent)
            agent = updated_agent

        updated_session = self._update_spread(session, event)
        self._save_session(updated_session)

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
        existing = self._agents.get(agent_id)
        if existing is not None:
            if existing.owning_principal != owning_principal:
                raise SessionRegistryError(
                    "Agent identity conflict: owning_principal is immutable"
                )
            agent = AgentRecord.model_validate(
                {
                    **existing.model_dump(),
                    "declared_capability_scope": declared_capability_scope,
                    "authorized_resource_scope": authorized_resource_scope,
                },
                strict=False,
            )
        else:
            agent = AgentRecord(
                agent_id=agent_id,
                owning_principal=owning_principal,
                declared_capability_scope=declared_capability_scope,
                authorized_resource_scope=authorized_resource_scope,
                registered_at=self._now(),
            )
        self._save_agent(agent)
        return agent
