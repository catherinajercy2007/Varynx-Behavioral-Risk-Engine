"""Regression tests: session ownership enforcement in IdentitySessionRegistry.

These tests verify REQ-002 session ownership invariants:
  - An event from Agent B must never reuse or modify a session belonging to Agent A.
  - A rejected event must not mutate Agent A session state.
  - Agent A legitimate events continue to work after a rejected cross-agent attempt.
"""
from __future__ import annotations

import os
import pytest
from datetime import UTC, datetime
from uuid import uuid4

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://session-ownership-test")

from varynx.engine.ingestion import IngestionLayer
from varynx.engine.registry import IdentitySessionRegistry, SessionRegistryError
from varynx.models.event import AgentActionEvent


def _make_event(agent_id: str, session_id, resource: str = "/data/x.csv") -> AgentActionEvent:
    return AgentActionEvent.model_validate({
        "agent_id": agent_id,
        "session_id": str(session_id),
        "timestamp": datetime.now(UTC).isoformat(),
        "action_type": "READ",
        "capability_requested": "read:files",
        "target_resource": resource,
        "authorization_result": "allowed",
        "is_simulated": True,
    }, strict=False)


def _make_reg()  -> tuple[IdentitySessionRegistry, IngestionLayer]:
    reg = IdentitySessionRegistry()
    reg.register_agent("agent-a", "team-a", ["READ"], ["/data"])
    reg.register_agent("agent-b", "team-b", ["READ"], ["/data"])
    return reg, IngestionLayer()


class TestSessionOwnership:
    """Session ownership enforcement: REQ-002."""

    def test_agent_a_can_use_own_session(self):
        """Agent A processes an event with its own session -- must succeed."""
        reg, il = _make_reg()
        sess_id = uuid4()
        ev = _make_event("agent-a", sess_id)
        v = il.validate(ev, skip_timestamp_check=True)
        ctx = reg.process_event(v)
        assert ctx.agent_record.agent_id == "agent-a"
        assert ctx.session_record.agent_id == "agent-a"
        assert ctx.session_record.session_id == sess_id

    def test_agent_b_cannot_use_agent_a_session(self):
        """Agent B event using Agent A session ID must be rejected with SessionRegistryError.

        This is the primary security regression: before the fix this was
        accepted and mutated Agent A session state.
        """
        reg, il = _make_reg()
        sess_id = uuid4()

        # Agent A creates the session
        ev_a = _make_event("agent-a", sess_id)
        v_a = il.validate(ev_a, skip_timestamp_check=True)
        reg.process_event(v_a)

        # Agent B tries to use the same session ID
        ev_b = _make_event("agent-b", sess_id)
        v_b = il.validate(ev_b, skip_timestamp_check=True)
        with pytest.raises(SessionRegistryError, match="Session ownership violation"):
            reg.process_event(v_b)

    def test_rejected_event_does_not_change_session_agent_id(self):
        """Rejected cross-agent event must not reassign session to Agent B."""
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id)
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))

        ev_b = _make_event("agent-b", sess_id)
        with pytest.raises(SessionRegistryError):
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        assert reg.get_session(sess_id).agent_id == "agent-a"

    def test_rejected_event_does_not_update_last_event_at(self):
        """Rejected event must not modify Agent A last_event_at."""
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id)
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))
        last_before = reg.get_session(sess_id).last_event_at

        import time; time.sleep(0.01)
        ev_b = _make_event("agent-b", sess_id)
        with pytest.raises(SessionRegistryError):
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        last_after = reg.get_session(sess_id).last_event_at
        assert last_after == last_before, "last_event_at must not change after rejection"

    def test_rejected_event_does_not_update_resource_spread(self):
        """Rejected event must not modify Agent A resource/capability spread."""
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id, "/data/x.csv")
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))
        spread_before = dict(reg.get_session(sess_id).resource_spread)

        ev_b = _make_event("agent-b", sess_id, "/secret/payload.csv")
        with pytest.raises(SessionRegistryError):
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        spread_after = dict(reg.get_session(sess_id).resource_spread)
        assert spread_after == spread_before, "resource_spread must not change after rejection"

    def test_rejected_event_does_not_increment_agent_a_escalation_count(self):
        """Rejected event must not increment Agent A scope_escalation_count."""
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id)
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))
        esc_before = reg.get_agent("agent-a").scope_escalation_count

        ev_b = _make_event("agent-b", sess_id)
        with pytest.raises(SessionRegistryError):
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        esc_after = reg.get_agent("agent-a").scope_escalation_count
        assert esc_after == esc_before, "agent-a escalation count must not change"

    def test_agent_a_events_work_after_rejected_cross_agent_attempt(self):
        """Agent A can still process legitimate events after a rejected attempt."""
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id)
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))

        ev_b = _make_event("agent-b", sess_id)
        with pytest.raises(SessionRegistryError):
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        # New event from Agent A with same session and new action_id
        from datetime import timedelta
        ev_a2 = AgentActionEvent.model_validate({
            "agent_id": "agent-a",
            "session_id": str(sess_id),
            "timestamp": (datetime.now(UTC) + timedelta(seconds=5)).isoformat(),
            "action_type": "READ",
            "capability_requested": "read:files",
            "target_resource": "/data/y.csv",
            "authorization_result": "allowed",
            "is_simulated": True,
        }, strict=False)
        # Use a fresh IngestionLayer to avoid dedup collision from the same instance
        from varynx.engine.ingestion import IngestionLayer as _IL
        ctx = reg.process_event(_IL().validate(ev_a2, skip_timestamp_check=True))
        assert ctx.agent_record.agent_id == "agent-a"
        assert ctx.session_record.agent_id == "agent-a"

    def test_unknown_session_id_creates_new_session_for_agent(self):
        """An event with a session_id not in the registry creates a new session.

        This is the existing intended behavior: unknown session ID -> auto-create.
        Must not change due to this security fix.
        """
        reg, il = _make_reg()
        fresh_sess_id = uuid4()  # never used before
        ev = _make_event("agent-a", fresh_sess_id)
        ctx = reg.process_event(il.validate(ev, skip_timestamp_check=True))
        assert ctx.session_record.session_id == fresh_sess_id
        assert ctx.session_record.agent_id == "agent-a"
        assert reg.get_session(fresh_sess_id) is not None

    def test_error_message_is_single_string(self):
        """SessionRegistryError must carry a single informative string, not a tuple.

        Regression for the two-argument construction bug.
        """
        reg, il = _make_reg()
        sess_id = uuid4()

        ev_a = _make_event("agent-a", sess_id)
        reg.process_event(il.validate(ev_a, skip_timestamp_check=True))

        ev_b = _make_event("agent-b", sess_id)
        with pytest.raises(SessionRegistryError) as exc_info:
            reg.process_event(il.validate(ev_b, skip_timestamp_check=True))

        err = exc_info.value
        assert len(err.args) == 1, f"Expected 1-arg error, got {err.args}"
        msg = str(err)
        assert "agent-a" in msg or "agent_id" in msg.lower(), f"Error must name agents: {msg}"
        assert "Session ownership violation" in msg, f"Must describe violation: {msg}"