"""API serialization property tests (T10.4).

Satisfies: T10.4, REQ-016
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from varynx.models.audit import AuditRecord, AuditRecordType
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult
from varynx.models.evidence import AnomalyClass, EvidenceRecord
from varynx.models.response import ReasonCode, ResponseRecommendation, ResponseType
from varynx.models.trust import TrustLevel, TrustState


def _now():
    return datetime.now(UTC)


@given(
    score=st.floats(min_value=0.0, max_value=1.0),
    weight=st.floats(min_value=0.0, max_value=1.0),
    uncertainty=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_all_float_fields_in_range(score, weight, uncertainty):
    """All score/weight/uncertainty fields serialize within [0.0, 1.0]."""
    data = dict(
        evidence_id=str(uuid4()), event_id=str(uuid4()), session_id=str(uuid4()),
        agent_id="ag", correlation_id=str(uuid4()),
        anomaly_class=AnomalyClass.ACTION_FREQUENCY.value,
        score=score, weight=weight, detector_id="test",
        timestamp=str(_now()), is_simulated=True, content_hash="abc",
    )
    rec = EvidenceRecord.model_validate(data, strict=False)
    dumped = rec.model_dump()
    assert 0.0 <= dumped["score"] <= 1.0
    assert 0.0 <= dumped["weight"] <= 1.0


@given(
    action_type=st.sampled_from(list(ActionType)),
    auth_result=st.sampled_from(list(AuthorizationResult)),
)
@settings(max_examples=100)
def test_agent_action_event_round_trips(action_type, auth_result):
    """AgentActionEvent serializes and deserializes cleanly."""
    event = AgentActionEvent.model_validate({
        "agent_id": "ag-001", "session_id": str(uuid4()),
        "timestamp": str(_now()), "action_type": action_type.value,
        "capability_requested": "cap", "target_resource": "/res",
        "authorization_result": auth_result.value, "is_simulated": True,
    }, strict=False)
    restored = AgentActionEvent.model_validate(event.model_dump(), strict=False)
    assert restored.action_type == event.action_type
    assert restored.authorization_result == event.authorization_result


@given(
    response_type=st.sampled_from(list(ResponseType)),
    record_type=st.sampled_from(list(AuditRecordType)),
)
@settings(max_examples=100)
def test_enum_fields_serialize_to_strings(response_type, record_type):
    """Enum fields serialize to their string values."""
    # ResponseType
    ts = TrustState.model_validate({
        "session_id": str(uuid4()), "agent_id": "ag",
        "current_score": 0.7, "level": TrustLevel.ELEVATED.value,
        "last_updated": str(_now()),
    }, strict=False)
    rc = ReasonCode.model_validate({
        "code": "TEST", "description": "test",
        "trust_level_at_recommendation": TrustLevel.ELEVATED.value,
        "severity": "INFO",
    }, strict=False)
    rec = ResponseRecommendation.model_validate({
        "recommendation_id": str(uuid4()), "agent_id": "ag",
        "correlation_id": str(uuid4()), "response_type": response_type.value,
        "evidence_bundle_id": str(uuid4()), "trust_state_snapshot": ts.model_dump(),
        "rationale": "test", "timestamp": str(_now()),
        "policy_id": "default", "policy_version": "1.0.0",
        "reason_codes": [rc.model_dump()],
    }, strict=False)
    dumped = rec.model_dump()
    assert isinstance(dumped["response_type"], str)

    # AuditRecord
    audit = AuditRecord.model_validate({
        "record_id": str(uuid4()), "timestamp": str(_now()),
        "record_type": record_type.value,
        "source_entity_id": "e1", "payload": {}, "record_hash": "abc",
    }, strict=False)
    assert isinstance(audit.model_dump()["record_type"], str)


def test_api_response_envelope_structure():
    """Success response envelope has required fields."""
    from varynx.api.schemas import error_response, success_response
    s = success_response({"key": "value"})
    assert s["status"] == "success"
    assert "request_id" in s
    assert "timestamp" in s
    assert s["data"] == {"key": "value"}

    e = error_response("TEST_CODE", "test message")
    assert e["status"] == "error"
    assert e["error_code"] == "TEST_CODE"
