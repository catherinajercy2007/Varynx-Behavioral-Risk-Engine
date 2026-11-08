from datetime import UTC, datetime
from uuid import uuid4

from varynx.engine.pipeline import VarynxPipeline
from varynx.engine.resource_gateway import (
    ResourceOperation,
    ResourceOperationRequest,
)
from varynx.models.event import AgentActionEvent


def _event(agent_id: str, session_id):
    return AgentActionEvent.model_validate(
        {
            "agent_id": agent_id,
            "session_id": str(session_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "action_type": "READ",
            "capability_requested": "read:files",
            "target_resource": "/data/sample.txt",
            "authorization_result": "allowed",
            "is_simulated": True,
        },
        strict=False,
    )


def _request(agent_id, session_id, correlation_id):
    return ResourceOperationRequest(
        agent_id=agent_id,
        capability="read:files",
        target_resource="/data/sample.txt",
        operation=ResourceOperation.READ,
        session_id=session_id,
        correlation_id=correlation_id,
    )


def _pipeline_with_recommendation():
    pipeline = VarynxPipeline(simulated_resources={"/data/sample.txt": "hello"})
    agent_id = "gateway-integration-agent"
    session_id = uuid4()
    analysis = pipeline.process_event(
        _event(agent_id, session_id),
        action_id="gateway-integration-event",
        skip_timestamp_check=True,
    )
    assert analysis.error is None, analysis.error
    assert analysis.recommendation is not None
    pipeline.lease_manager.create_lease(
        agent_id=agent_id,
        session_id=session_id,
        capability="read:files",
        resource_scope={"resources": ["/data"]},
        issuing_principal="integration-test",
        issuing_policy_id="integration-test-policy",
    )
    return pipeline, agent_id, session_id, analysis.recommendation


def test_pipeline_executes_only_when_behavior_and_lease_permit():
    pipeline, agent_id, session_id, recommendation = _pipeline_with_recommendation()
    request = _request(agent_id, session_id, recommendation.correlation_id)

    result = pipeline.execute_resource_operation(request, recommendation)

    if recommendation.response_type.value in {"PERMIT", "WARN"}:
        assert result.authorized is True
        assert result.executed is True
        assert result.value == "hello"
    else:
        assert result.executed is False
        assert result.status == "HELD"

    assert pipeline.audit_store.verify_chain()[0] is True


def test_pipeline_rejects_mismatched_recommendation_identity():
    pipeline, agent_id, session_id, recommendation = _pipeline_with_recommendation()
    request = _request(agent_id, session_id, recommendation.correlation_id)
    request.target_resource = "/data/other.txt"

    result = pipeline.execute_resource_operation(request, recommendation)

    assert result.executed is False
    assert result.status == "HELD"
    assert pipeline.audit_store.verify_chain()[0] is True


def test_pipeline_lease_denial_overrides_behavioral_permit():
    pipeline, agent_id, session_id, recommendation = _pipeline_with_recommendation()
    request = _request(agent_id, session_id, recommendation.correlation_id)
    request.target_resource = "/private/secret.txt"
    # Align recommendation context to prove the lease gate, not identity check,
    # is what denies this request.
    recommendation.target_resource = "/private/secret.txt"

    result = pipeline.execute_resource_operation(request, recommendation)

    assert result.authorized is False
    assert result.executed is False
    assert result.status == "DENIED"
    assert pipeline.audit_store.verify_chain()[0] is True


def test_pipeline_does_not_allow_delete_under_read_capability():
    pipeline, agent_id, session_id, recommendation = _pipeline_with_recommendation()
    request = ResourceOperationRequest(
        agent_id=agent_id,
        capability="read:files",
        target_resource="/data/sample.txt",
        operation=ResourceOperation.DELETE,
        session_id=session_id,
        correlation_id=recommendation.correlation_id,
    )

    result = pipeline.execute_resource_operation(request, recommendation)

    assert result.authorized is True
    assert result.executed is False
    assert result.status == "HELD"
    assert "/data/sample.txt" in pipeline.resource_gateway.snapshot()
    assert pipeline.audit_store.verify_chain()[0] is True


def test_pipeline_rejects_request_from_different_lease_session():
    pipeline, agent_id, session_id, recommendation = _pipeline_with_recommendation()
    request = _request(agent_id, session_id, recommendation.correlation_id)
    request.session_id = uuid4()

    result = pipeline.execute_resource_operation(request, recommendation)

    assert result.authorized is False
    assert result.executed is False
    assert result.status == "DENIED"
    assert pipeline.audit_store.verify_chain()[0] is True
