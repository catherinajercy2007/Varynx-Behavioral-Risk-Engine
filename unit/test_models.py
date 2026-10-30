from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from varynx.models import (
    ActionType,
    AgentActionEvent,
    AgentRecord,
    AnomalyClass,
    AuditRecord,
    AuditRecordType,
    AuthorizationResult,
    CapabilityLease,
    ConsequenceProjection,
    EnforcementOutcome,
    EnforcementRecord,
    EvidenceRecord,
    LeaseState,
    TrajectoryProjection,
    TrendDirection,
    TrustLevel,
    TrustState,
    ValidatedEvent,
)


def now():
    return datetime.now(UTC)

def make_event(**kwargs):
    d = dict(agent_id="agent-001", session_id=uuid4(), timestamp=now(),
             action_type=ActionType.READ, capability_requested="read:files",
             target_resource="/data", authorization_result=AuthorizationResult.ALLOWED,
             is_simulated=True)
    d.update(kwargs)
    return AgentActionEvent.model_validate(d, strict=False)

def make_trust_state(**kwargs):
    d = dict(session_id=uuid4(), agent_id="agent-001", current_score=0.7,
             level=TrustLevel.ELEVATED, last_updated=now())
    d.update(kwargs)
    return TrustState.model_validate(d, strict=False)

def make_evidence_record(**kwargs):
    d = dict(evidence_id=uuid4(), event_id=uuid4(), session_id=uuid4(),
             agent_id="agent-001", correlation_id=uuid4(),
             anomaly_class=AnomalyClass.ACTION_FREQUENCY, score=0.5, weight=0.8,
             detector_id="action_frequency", timestamp=now(), is_simulated=True,
             content_hash="abc123")
    d.update(kwargs)
    return EvidenceRecord.model_validate(d, strict=False)

class TestActionTypeEnum:
    def test_has_nine_values(self):
        assert len(ActionType) == 9

class TestAnomalyClassEnum:
    def test_has_exactly_six_members(self):
        assert len(AnomalyClass) == 6

    def test_all_expected_classes_present(self):
        expected = {"CAPABILITY_ESCALATION","RESOURCE_ANOMALY","ACTION_FREQUENCY",
                    "AUTHORIZATION_BYPASS_ATTEMPT","CONTEXT_DEVIATION","TEMPORAL_ANOMALY"}
        assert {a.value for a in AnomalyClass} == expected

class TestAgentActionEvent:
    def test_valid_event(self):
        event = make_event()
        assert event.agent_id == "agent-001"

    def test_missing_agent_id_raises(self):
        with pytest.raises(ValidationError):
            AgentActionEvent.model_validate(
                dict(session_id=str(uuid4()), timestamp=now().isoformat(),
                     action_type="READ", capability_requested="r", target_resource="/d",
                     authorization_result="allowed", is_simulated=True),
                strict=False)

    def test_trust_signal_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            make_event(trust_signal=1.5)

    def test_round_trip(self):
        e = make_event()
        r = AgentActionEvent.model_validate(e.model_dump(), strict=False)
        assert r.agent_id == e.agent_id

class TestValidatedEvent:
    def test_from_event_factory(self):
        e = make_event()
        eid, cid = uuid4(), uuid4()
        v = ValidatedEvent.from_event(e, eid, cid)
        assert v.event_id == eid
        assert v.correlation_id == cid

class TestEvidenceRecord:
    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            make_evidence_record(score=1.5)

    def test_score_negative_rejected(self):
        with pytest.raises(ValidationError):
            make_evidence_record(score=-0.1)

    def test_weight_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            make_evidence_record(weight=1.1)

    def test_derivation_status_default(self):
        assert make_evidence_record().derivation_status == "COMPLETE"

    def test_round_trip(self):
        r = make_evidence_record()
        r2 = EvidenceRecord.model_validate(r.model_dump(), strict=False)
        assert r2.evidence_id == r.evidence_id

class TestTrustState:
    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            make_trust_state(current_score=1.1)

    def test_round_trip(self):
        ts = make_trust_state()
        ts2 = TrustState.model_validate(ts.model_dump(), strict=False)
        assert ts2.session_id == ts.session_id

class TestConsequenceProjection:
    def test_is_projected_default_true(self):
        cp = ConsequenceProjection(policy_id="p1", projected_response="PERMIT",
                                   projected_trust_impact=-0.1, risk_level="LOW",
                                   uncertainty_score=0.1, confidence=0.9, rationale="test")
        assert cp.is_projected is True

    def test_uncertainty_out_of_range(self):
        with pytest.raises(ValidationError):
            ConsequenceProjection(policy_id="p1", projected_response="PERMIT",
                                  projected_trust_impact=-0.1, risk_level="LOW",
                                  uncertainty_score=1.5, confidence=0.9, rationale="test")

class TestTrajectoryProjection:
    def test_is_projected_default_true(self):
        tp = TrajectoryProjection(projection_id=uuid4(), session_id=uuid4(),
                                  agent_id="a1", trend=TrendDirection.STABLE,
                                  projected_trust_at_horizon=0.7, horizon_seconds=3600.0,
                                  confidence_interval=(0.5,0.9), warning_threshold=0.3,
                                  is_stub=True, computation_timestamp=now())
        assert tp.is_projected is True

    def test_projected_trust_out_of_range(self):
        with pytest.raises(ValidationError):
            TrajectoryProjection(projection_id=uuid4(), session_id=uuid4(),
                                 agent_id="a1", trend=TrendDirection.STABLE,
                                 projected_trust_at_horizon=1.5, horizon_seconds=3600.0,
                                 confidence_interval=(0.5,0.9), warning_threshold=0.3,
                                 is_stub=True, computation_timestamp=now())

class TestAuditRecord:
    def test_has_eight_record_types(self):
        assert len(AuditRecordType) == 8

    def test_round_trip(self):
        r = AuditRecord(record_id=uuid4(), timestamp=now(),
                        record_type=AuditRecordType.EVENT_INGESTED,
                        source_entity_id="e1", payload={}, record_hash="abc")
        r2 = AuditRecord.model_validate(r.model_dump(), strict=False)
        assert r2.record_id == r.record_id

class TestLeaseLifecycle:
    def test_round_trip(self):
        l = CapabilityLease(lease_id=uuid4(), agent_id="a1", session_id=uuid4(),
                            capability="read", resource_scope={}, activation_timestamp=now(),
                            issuing_principal="admin", issuing_policy_id="p1",
                            state=LeaseState.ACTIVE)
        l2 = CapabilityLease.model_validate(l.model_dump(), strict=False)
        assert l2.state == LeaseState.ACTIVE

class TestEnforcementRecord:
    def test_round_trip(self):
        r = EnforcementRecord(enforcement_id=uuid4(), source_recommendation_id=uuid4(),
                               action_taken="SUSPEND", target_agent_id="a1",
                               action_timestamp=now(), outcome=EnforcementOutcome.SUCCESS)
        r2 = EnforcementRecord.model_validate(r.model_dump(), strict=False)
        assert r2.outcome == EnforcementOutcome.SUCCESS
        assert r2.dry_run is False

class TestAgentRecord:
    def test_round_trip(self):
        a = AgentRecord(agent_id="a1", owning_principal="org", registered_at=now())
        a2 = AgentRecord.model_validate(a.model_dump(), strict=False)
        assert a2.agent_id == "a1"
