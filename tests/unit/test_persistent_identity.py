from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from varynx.engine.lease_manager import LeaseManager
from varynx.engine.record_store import RecordIntegrityError
from varynx.engine.registry import IdentitySessionRegistry, SessionRegistryError
from varynx.models.agent import SessionRecord


def test_agent_and_session_survive_registry_restart(tmp_path):
    registry = IdentitySessionRegistry(tmp_path)
    agent = registry.register_agent(
        "agent-persist-1", "principal-1", ["READ"], ["/data"]
    )
    session = SessionRecord(
        session_id=uuid4(), agent_id=agent.agent_id,
        started_at=datetime.now(UTC),
    )
    registry.create_session(session)
    session_id = session.session_id
    registry.close()

    reopened = IdentitySessionRegistry(tmp_path)
    assert reopened.get_agent("agent-persist-1").owning_principal == "principal-1"
    assert reopened.get_session(session_id).agent_id == "agent-persist-1"
    reopened.close()


def test_agent_owner_is_immutable(tmp_path):
    registry = IdentitySessionRegistry(tmp_path)
    registry.register_agent("agent-immutable", "owner-A", [], [])
    with pytest.raises(SessionRegistryError, match="immutable"):
        registry.register_agent("agent-immutable", "owner-B", [], [])
    registry.close()


def test_lease_state_and_history_survive_restart(tmp_path):
    manager = LeaseManager(tmp_path)
    lease = manager.create_lease(
        agent_id="agent-lease", session_id=uuid4(), capability="read:files",
        resource_scope={"resources": ["/data"]}, issuing_principal="owner",
        issuing_policy_id="policy-1", expiry_timestamp=datetime.now(UTC) + timedelta(hours=1),
    )
    manager.revoke(lease.lease_id, reason="test-revocation")
    manager.close()

    reopened = LeaseManager(tmp_path)
    restored = reopened.get_lease(lease.lease_id)
    assert restored is not None
    assert restored.state.value == "REVOKED"
    assert restored.state_history[-1]["reason"] == "test-revocation"
    reopened.close()


def test_persisted_lease_tampering_fails_closed(tmp_path):
    manager = LeaseManager(tmp_path)
    lease = manager.create_lease(
        agent_id="agent-tamper", session_id=uuid4(), capability="read:files",
        resource_scope={"resources": ["/data"]}, issuing_principal="owner",
        issuing_policy_id="policy-1",
    )
    manager.close()

    import sqlite3
    connection = sqlite3.connect(tmp_path / "leases.sqlite3")
    connection.execute(
        "UPDATE leases SET payload=? WHERE record_key=?",
        ('{"state":"ACTIVE"}', str(lease.lease_id)),
    )
    connection.commit()
    connection.close()

    with pytest.raises(RecordIntegrityError):
        LeaseManager(tmp_path)
