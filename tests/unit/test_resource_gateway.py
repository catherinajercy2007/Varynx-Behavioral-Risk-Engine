from uuid import uuid4

import pytest

from varynx.engine.audit import AuditStore
from varynx.engine.lease_manager import LeaseManager
from varynx.engine.resource_gateway import (
    ResourceOperation,
    ResourceOperationRequest,
    SimulatedResourceGateway,
)


@pytest.fixture
def setup_gateway():
    leases = LeaseManager()
    audit = AuditStore()
    session_id = uuid4()
    leases.create_lease(
        agent_id="agent-allowed",
        session_id=session_id,
        capability="read:files",
        resource_scope={"resources": ["/data"]},
        issuing_principal="test-admin",
        issuing_policy_id="test-policy",
    )
    gateway = SimulatedResourceGateway(
        lease_manager=leases,
        audit_store=audit,
        resources={"/data/sample.txt": "initial"},
    )
    return gateway, audit, session_id


def make_request(session_id, **overrides):
    values = {
        "agent_id": "agent-allowed",
        "capability": "read:files",
        "target_resource": "/data/sample.txt",
        "operation": ResourceOperation.READ,
        "session_id": session_id,
        "correlation_id": uuid4(),
    }
    values.update(overrides)
    return ResourceOperationRequest(**values)


def test_valid_lease_and_behavioral_permit_execute_read(setup_gateway):
    gateway, audit, session_id = setup_gateway
    result = gateway.execute(
        make_request(session_id),
        behavioral_permit=True,
    )
    assert result.authorized is True
    assert result.executed is True
    assert result.value == "initial"
    assert result.status == "EXECUTED"
    assert audit.verify_chain()[0] is True


def test_unauthorized_resource_is_blocked_even_if_behavior_permits(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id, target_resource="/private/secret.txt")
    result = gateway.execute(request, behavioral_permit=True)
    assert result.authorized is False
    assert result.executed is False
    assert result.status == "DENIED"
    assert gateway.snapshot()["/data/sample.txt"] == "initial"


def test_behavioral_gate_defaults_to_deny(setup_gateway):
    gateway, _, session_id = setup_gateway
    result = gateway.execute(make_request(session_id))
    assert result.authorized is True
    assert result.executed is False
    assert result.status == "HELD"


def test_write_updates_only_after_both_gates_pass(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(
        session_id,
        operation=ResourceOperation.WRITE,
        value="updated",
    )
    held = gateway.execute(request)
    assert held.executed is False
    assert gateway.snapshot()["/data/sample.txt"] == "initial"

    # A new request ID is required when retrying after a held decision.
    approved_request = request.model_copy(update={"request_id": uuid4()})
    executed = gateway.execute(approved_request, behavioral_permit=True)
    assert executed.executed is True
    assert gateway.snapshot()["/data/sample.txt"] == "updated"


def test_delete_removes_simulated_resource(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id, operation=ResourceOperation.DELETE)
    result = gateway.execute(request, behavioral_permit=True)
    assert result.executed is True
    assert "/data/sample.txt" not in gateway.snapshot()


def test_missing_resource_does_not_execute(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id, target_resource="/data/missing.txt")
    result = gateway.execute(request, behavioral_permit=True)
    assert result.status == "NOT_FOUND"
    assert result.executed is False


def test_unknown_agent_is_denied(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id, agent_id="unknown-agent")
    result = gateway.execute(request, behavioral_permit=True)
    assert result.status == "DENIED"
    assert result.executed is False


def test_audit_chain_remains_valid_after_denial_and_success(setup_gateway):
    gateway, audit, session_id = setup_gateway
    gateway.execute(
        make_request(session_id, target_resource="/outside/file"),
        behavioral_permit=True,
    )
    gateway.execute(make_request(session_id), behavioral_permit=True)
    valid, violations = audit.verify_chain()
    assert valid, violations
    assert len(audit.all_records()) >= 5


def test_session_mismatch_is_denied_even_when_agent_and_scope_match(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id).model_copy(update={"session_id": uuid4()})
    result = gateway.execute(request, behavioral_permit=True)
    assert result.authorized is False
    assert result.executed is False
    assert result.status == "DENIED"


def test_duplicate_write_request_is_idempotent(setup_gateway):
    gateway, audit, session_id = setup_gateway
    request = make_request(
        session_id,
        operation=ResourceOperation.WRITE,
        value="written-once",
    )

    first = gateway.execute(request, behavioral_permit=True)
    records_after_first = len(audit.all_records())
    second = gateway.execute(request, behavioral_permit=True)

    assert first.executed is True
    assert second.executed is True
    assert second.value is None
    assert gateway.snapshot()["/data/sample.txt"] == "written-once"
    assert len(audit.all_records()) == records_after_first + 1
    assert audit.all_records()[-1].payload["stage"] == "RESOURCE_REQUEST_REPLAYED"
    assert audit.verify_chain()[0] is True


def test_request_id_reuse_with_changed_payload_is_rejected(setup_gateway):
    gateway, audit, session_id = setup_gateway
    request = make_request(
        session_id,
        operation=ResourceOperation.WRITE,
        value="first-value",
    )
    first = gateway.execute(request, behavioral_permit=True)
    conflicting = request.model_copy(update={"value": "different-value"})

    second = gateway.execute(conflicting, behavioral_permit=True)

    assert first.executed is True
    assert second.executed is False
    assert second.status == "REPLAY_CONFLICT"
    assert gateway.snapshot()["/data/sample.txt"] == "first-value"
    assert audit.all_records()[-1].payload["stage"] == "RESOURCE_REQUEST_REPLAY_CONFLICT"
    assert audit.verify_chain()[0] is True


def test_duplicate_delete_request_does_not_repeat_mutation(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(session_id, operation=ResourceOperation.DELETE)

    first = gateway.execute(request, behavioral_permit=True)
    second = gateway.execute(request, behavioral_permit=True)

    assert first.executed is True
    assert second.executed is True
    assert second.status == "EXECUTED"
    assert "/data/sample.txt" not in gateway.snapshot()


def test_behavioral_approval_cannot_be_upgraded_with_same_request_id(setup_gateway):
    gateway, _, session_id = setup_gateway
    request = make_request(
        session_id,
        operation=ResourceOperation.WRITE,
        value="must-not-write",
    )

    held = gateway.execute(request, behavioral_permit=False)
    replay = gateway.execute(request, behavioral_permit=True)

    assert held.status == "HELD"
    assert replay.status == "REPLAY_CONFLICT"
    assert replay.executed is False
    assert gateway.snapshot()["/data/sample.txt"] == "initial"
