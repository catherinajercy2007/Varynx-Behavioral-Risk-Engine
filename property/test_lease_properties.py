"""Lease state machine property tests (T10.5).

Satisfies: T10.5, REQ-010
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from varynx.engine.lease_manager import LeaseError, LeaseManager
from varynx.models.lease import LeaseState


def _now():
    return datetime.now(UTC)


def make_lease(manager: LeaseManager, agent_id: str = "ag-001"):
    return manager.create_lease(
        agent_id=agent_id, session_id=uuid4(),
        capability="read:files", resource_scope={},
        issuing_principal="test", issuing_policy_id="pol-1",
    )


def test_new_lease_is_active():
    m = LeaseManager()
    lease = make_lease(m)
    assert lease.state == LeaseState.ACTIVE


def test_active_can_be_suspended():
    m = LeaseManager()
    lease = make_lease(m)
    suspended = m.suspend(lease.lease_id)
    assert suspended.state == LeaseState.SUSPENDED


def test_active_can_be_revoked():
    m = LeaseManager()
    lease = make_lease(m)
    revoked = m.revoke(lease.lease_id)
    assert revoked.state == LeaseState.REVOKED


def test_revoked_is_terminal():
    """REVOKED lease never transitions to any other state (REQ-010.6)."""
    m = LeaseManager()
    lease = make_lease(m)
    m.revoke(lease.lease_id)
    with pytest.raises(LeaseError, match="REVOKED"):
        m.suspend(lease.lease_id)
    with pytest.raises(LeaseError, match="REVOKED"):
        m.reinstate(lease.lease_id)
    with pytest.raises(LeaseError, match="REVOKED"):
        m.revoke(lease.lease_id)


def test_suspended_can_be_reinstated():
    m = LeaseManager()
    lease = make_lease(m)
    m.suspend(lease.lease_id)
    reinstated = m.reinstate(lease.lease_id)
    assert reinstated.state == LeaseState.ACTIVE


def test_suspend_all_for_agent(  ):
    """Suspension cascades to all ACTIVE leases for agent (REQ-010.4)."""
    m = LeaseManager()
    leases = [make_lease(m, "ag-cascade") for _ in range(3)]
    m.suspend_all_for_agent("ag-cascade")
    for l in leases:
        updated = m.get_lease(l.lease_id)
        assert updated.state == LeaseState.SUSPENDED


def test_revoke_all_for_agent():
    """Revocation cascades to all ACTIVE and SUSPENDED leases (REQ-010.5)."""
    m = LeaseManager()
    l1 = make_lease(m, "ag-revoke")
    l2 = make_lease(m, "ag-revoke")
    m.suspend(l2.lease_id)  # One is suspended
    m.revoke_all_for_agent("ag-revoke")
    assert m.get_lease(l1.lease_id).state == LeaseState.REVOKED
    assert m.get_lease(l2.lease_id).state == LeaseState.REVOKED


def test_expired_lease_detected():
    """Leases past expiry_timestamp transition to EXPIRED on check_expiry (REQ-010.3)."""
    m = LeaseManager()
    lease = m.create_lease(
        agent_id="ag-exp", session_id=uuid4(),
        capability="read", resource_scope={},
        issuing_principal="test", issuing_policy_id="pol-1",
        expiry_timestamp=_now() - timedelta(seconds=1),  # Already expired
    )
    expired = m.check_expiry()
    assert len(expired) == 1
    assert expired[0].state == LeaseState.EXPIRED


@given(n=st.integers(min_value=1, max_value=20))
@settings(max_examples=50)
def test_revoked_never_transitions_property(n: int):
    """Property: REVOKED state is always terminal regardless of operation sequence."""
    m = LeaseManager()
    lease = make_lease(m)
    m.revoke(lease.lease_id)
    # Any subsequent operation must raise LeaseError
    for _ in range(n):
        with pytest.raises(LeaseError):
            m.revoke(lease.lease_id)


def test_state_history_records_all_transitions():
    """State history records every transition with timestamp and reason."""
    m = LeaseManager()
    lease = make_lease(m)
    m.suspend(lease.lease_id)
    m.reinstate(lease.lease_id, reason="test_reinstate")
    final = m.get_lease(lease.lease_id)
    states = [h["state"] for h in final.state_history]
    assert states == ["ACTIVE", "SUSPENDED", "ACTIVE"]
