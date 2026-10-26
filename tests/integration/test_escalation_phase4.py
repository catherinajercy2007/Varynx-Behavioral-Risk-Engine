"""Phase 4 focused tests — ESCALATE explicit pending-review enforcement.

Covers:
- Pending-review state recording
- Audit record enrichment
- Duplicate escalation handling
- Missing context safety
- Authorization / capability isolation
- Failure handling when registration fails
- RESTRICT regression (Phase 3 must still work)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4, UUID

import pytest

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-phase4")

from varynx.engine.enforcement import EnforcementLayer
from varynx.engine.lease_manager import LeaseManager
from varynx.models.enforcement import EnforcementOutcome
from varynx.models.lease import LeaseState
from varynx.models.response import ReasonCode, ResponseRecommendation, ResponseType
from varynx.models.trust import TrustLevel, TrustState


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trust_state(agent_id: str = "ag", score: float = 0.5) -> TrustState:
    return TrustState.model_validate(
        {"session_id": str(uuid4()), "agent_id": agent_id,
         "current_score": score, "level": TrustLevel.GUARDED.value,
         "last_updated": str(_now())},
        strict=False,
    )


def _rec(
    agent_id: str,
    response_type: ResponseType,
    target_capability: str | None = None,
    target_resource: str | None = None,
    reason_codes: list[str] | None = None,
) -> ResponseRecommendation:
    ts = _trust_state(agent_id)
    codes = reason_codes or ["TRUST_DEGRADED"]
    rc_list = [
        ReasonCode.model_validate(
            {"code": c, "description": c, "trust_level_at_recommendation": TrustLevel.GUARDED.value, "severity": "CRITICAL"},
            strict=False,
        )
        for c in codes
    ]
    return ResponseRecommendation.model_validate(
        {"recommendation_id": str(uuid4()), "agent_id": agent_id,
         "correlation_id": str(uuid4()), "response_type": response_type.value,
         "reason_codes": [rc.model_dump() for rc in rc_list],
         "evidence_bundle_id": str(uuid4()),
         "trust_state_snapshot": ts.model_dump(),
         "rationale": "phase4-test", "timestamp": str(_now()),
         "policy_id": "test", "policy_version": "1.0",
         "target_capability": target_capability, "target_resource": target_resource},
        strict=False,
    )


def _enforcer(dry_run: bool = False) -> tuple[EnforcementLayer, LeaseManager]:
    lm = LeaseManager()
    return EnforcementLayer(dry_run=dry_run, lease_manager=lm), lm


# ─────────────────────────────────────────────────────────────────────────────
# Pending-review state recording
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationPendingState:
    """Escalation must be recorded as PENDING_HUMAN_REVIEW, never as approved."""

    def test_escalation_is_registered_in_pending_register(self):
        el, _ = _enforcer()
        rec = _rec("ag-pe-1", ResponseType.ESCALATE, target_capability="delete:data")
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.FAILED
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry is not None, "Escalation must be recorded in the pending register"
        assert entry["status"] == "PENDING_HUMAN_REVIEW"
        assert entry["agent_id"] == "ag-pe-1"
        assert entry["recommendation_id"] == str(rec.recommendation_id)

    def test_escalation_status_is_never_approved(self):
        """No code path must set status to APPROVED or any non-pending value."""
        el, _ = _enforcer()
        rec = _rec("ag-pe-2", ResponseType.ESCALATE, target_capability="write:admin")
        el.enforce(rec)
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert "APPROVED" not in entry["status"]
        assert "COMPLETE" not in entry["status"]
        assert "ALLOWED" not in entry["status"]

    def test_escalation_records_target_capability(self):
        el, _ = _enforcer()
        rec = _rec("ag-pe-3", ResponseType.ESCALATE, target_capability="credential:vault")
        el.enforce(rec)
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry["target_capability"] == "credential:vault"

    def test_escalation_records_target_resource(self):
        el, _ = _enforcer()
        rec = _rec("ag-pe-4", ResponseType.ESCALATE,
                   target_capability="credential:vault", target_resource="/secrets/db")
        el.enforce(rec)
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry["target_resource"] == "/secrets/db"

    def test_escalation_records_reason_codes(self):
        el, _ = _enforcer()
        rec = _rec("ag-pe-5", ResponseType.ESCALATE, reason_codes=["BYPASS_ATTEMPT", "TRUST_DEGRADED"])
        el.enforce(rec)
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert "BYPASS_ATTEMPT" in entry["reason_codes"]
        assert "TRUST_DEGRADED" in entry["reason_codes"]

    def test_escalation_records_timestamp(self):
        el, _ = _enforcer()
        rec = _rec("ag-pe-6", ResponseType.ESCALATE)
        el.enforce(rec)
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert "escalated_at" in entry
        assert entry["escalated_at"]  # non-empty

    def test_list_pending_escalations_returns_all(self):
        el, _ = _enforcer()
        recs = [_rec(f"ag-pe-list-{i}", ResponseType.ESCALATE) for i in range(3)]
        for r in recs:
            el.enforce(r)
        all_entries = el.list_pending_escalations()
        assert len(all_entries) == 3

    def test_get_unknown_recommendation_returns_none(self):
        el, _ = _enforcer()
        assert el.get_pending_escalation(uuid4()) is None

    def test_escalation_blocks_operation_returns_failed(self):
        """ESCALATE must never return SUCCESS — that would mean the operation proceeded."""
        el, _ = _enforcer()
        rec = _rec("ag-pe-7", ResponseType.ESCALATE)
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.FAILED, (
            "ESCALATE must block the operation; outcome must be FAILED not SUCCESS"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Audit record enrichment
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationAuditRecords:
    """The pipeline's ENFORCEMENT_APPLIED audit record carries escalation context."""

    def test_audit_record_carries_pending_status(self):
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
        from varynx.models.response import ResponseType as RT

        pipeline = VarynxPipeline()
        agent_id = "ag-audit-esc-1"
        sid = uuid4()
        pipeline.response_engine._active_responses[agent_id] = RT.ESCALATE.value

        event = AgentActionEvent.model_validate({
            "agent_id": agent_id, "session_id": str(sid),
            "timestamp": str(_now()), "action_type": "CREDENTIAL_ACCESS",
            "capability_requested": "credential:vault",
            "target_resource": "/secrets/db_pass",
            "authorization_result": "allowed", "is_simulated": True,
        }, strict=False)

        res = pipeline.process_event(event, action_id="audit-esc-1", skip_timestamp_check=True)
        assert res.error is None

        if res.recommendation and res.recommendation.response_type == RT.ESCALATE:
            assert res.enforcement_record.outcome == EnforcementOutcome.FAILED

            from varynx.models.audit import AuditRecordType
            audit_records = pipeline.audit_store.all_records()
            enf_record = next(
                (r for r in audit_records if r.record_type == AuditRecordType.ENFORCEMENT_APPLIED),
                None
            )
            assert enf_record is not None, "ENFORCEMENT_APPLIED audit record missing"
            assert "escalation_status" in enf_record.payload, (
                f"escalation_status missing from audit payload: {enf_record.payload}"
            )
            assert enf_record.payload["escalation_status"] == "PENDING_HUMAN_REVIEW"
            assert "escalation_reason_codes" in enf_record.payload

    def test_audit_record_does_not_claim_human_approval(self):
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent
        from varynx.models.response import ResponseType as RT

        pipeline = VarynxPipeline()
        agent_id = "ag-audit-esc-2"
        sid = uuid4()
        pipeline.response_engine._active_responses[agent_id] = RT.ESCALATE.value

        event = AgentActionEvent.model_validate({
            "agent_id": agent_id, "session_id": str(sid),
            "timestamp": str(_now()), "action_type": "WRITE",
            "capability_requested": "write:admin", "target_resource": "/admin",
            "authorization_result": "allowed", "is_simulated": True,
        }, strict=False)

        res = pipeline.process_event(event, action_id="audit-esc-2", skip_timestamp_check=True)
        if res.recommendation and res.recommendation.response_type == RT.ESCALATE:
            from varynx.models.audit import AuditRecordType
            for r in pipeline.audit_store.all_records():
                payload_str = str(r.payload)
                assert "APPROVED" not in payload_str, (
                    "Audit record must never contain APPROVED for a pending escalation"
                )

    def test_audit_record_links_to_enforcement_record(self):
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent
        from varynx.models.response import ResponseType as RT
        from varynx.models.audit import AuditRecordType

        pipeline = VarynxPipeline()
        agent_id = "ag-audit-esc-3"
        sid = uuid4()
        pipeline.response_engine._active_responses[agent_id] = RT.ESCALATE.value

        event = AgentActionEvent.model_validate({
            "agent_id": agent_id, "session_id": str(sid),
            "timestamp": str(_now()), "action_type": "DELETE",
            "capability_requested": "delete:records", "target_resource": "/data",
            "authorization_result": "allowed", "is_simulated": True,
        }, strict=False)

        res = pipeline.process_event(event, action_id="audit-esc-3", skip_timestamp_check=True)
        if res.recommendation and res.recommendation.response_type == RT.ESCALATE:
            enf_audit = next(
                (r for r in pipeline.audit_store.all_records()
                 if r.record_type == AuditRecordType.ENFORCEMENT_APPLIED),
                None
            )
            assert enf_audit is not None
            assert str(res.enforcement_record.enforcement_id) == enf_audit.source_entity_id


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate escalation handling
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationDuplicateHandling:

    def test_duplicate_recommendation_id_returns_skipped(self):
        el, _ = _enforcer()
        rec = _rec("ag-dup-1", ResponseType.ESCALATE)
        r1 = el.enforce(rec)
        r2 = el.enforce(rec)
        assert r1.outcome == EnforcementOutcome.FAILED
        assert r2.outcome == EnforcementOutcome.SKIPPED
        assert r2.outcome_reason == "DUPLICATE_ENFORCEMENT"

    def test_duplicate_does_not_create_second_register_entry(self):
        el, _ = _enforcer()
        rec = _rec("ag-dup-2", ResponseType.ESCALATE)
        el.enforce(rec)
        el.enforce(rec)
        entries = el.list_pending_escalations()
        assert len(entries) == 1, "Duplicate escalation must not create a second register entry"

    def test_two_different_recommendations_both_register(self):
        el, _ = _enforcer()
        rec1 = _rec("ag-dup-3", ResponseType.ESCALATE, target_capability="cap-a")
        rec2 = _rec("ag-dup-3", ResponseType.ESCALATE, target_capability="cap-b")
        el.enforce(rec1)
        el.enforce(rec2)
        entries = el.list_pending_escalations()
        assert len(entries) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Missing context safety
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationMissingContext:

    def test_missing_target_capability_still_blocks_and_registers(self):
        """Escalation without target_capability must still block and be recorded."""
        el, _ = _enforcer()
        rec = _rec("ag-mc-1", ResponseType.ESCALATE, target_capability=None)
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.FAILED
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry is not None
        assert entry["target_capability"] == "(not specified)"

    def test_missing_target_resource_still_registers(self):
        el, _ = _enforcer()
        rec = _rec("ag-mc-2", ResponseType.ESCALATE,
                   target_capability="write:files", target_resource=None)
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.FAILED
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry["target_resource"] == "(not specified)"

    def test_empty_reason_codes_still_registers(self):
        """Escalation with no reason codes must still block and register.

        Builds the recommendation directly (bypassing helper default) to ensure
        an actually-empty reason_codes list reaches the enforcement layer.
        """
        el, _ = _enforcer()
        ts = _trust_state("ag-mc-3")
        # Build rec directly so reason_codes is genuinely empty
        rec = ResponseRecommendation.model_validate(
            {"recommendation_id": str(uuid4()), "agent_id": "ag-mc-3",
             "correlation_id": str(uuid4()), "response_type": ResponseType.ESCALATE.value,
             "reason_codes": [],  # intentionally empty
             "evidence_bundle_id": str(uuid4()),
             "trust_state_snapshot": ts.model_dump(),
             "rationale": "empty-codes-test", "timestamp": str(_now()),
             "policy_id": "test", "policy_version": "1.0",
             "target_capability": None, "target_resource": None},
            strict=False,
        )
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.FAILED
        entry = el.get_pending_escalation(rec.recommendation_id)
        assert entry is not None
        assert entry["reason_codes"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Authorization and capability isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationAuthorizationBehavior:

    def test_escalate_does_not_suspend_any_lease(self):
        """ESCALATE must not cascade lease suspensions — that is SUSPEND's job."""
        el, lm = _enforcer()
        lease1 = lm.create_lease("ag-auth-1", uuid4(), "read:files", {}, "test", "pol")
        lease2 = lm.create_lease("ag-auth-1", uuid4(), "delete:data", {}, "test", "pol")
        rec = _rec("ag-auth-1", ResponseType.ESCALATE, target_capability="delete:data")
        el.enforce(rec)
        assert lm.get_lease(lease1.lease_id).state == LeaseState.ACTIVE
        assert lm.get_lease(lease2.lease_id).state == LeaseState.ACTIVE

    def test_escalate_does_not_revoke_any_lease(self):
        """ESCALATE must not revoke leases — that is TERMINATE's job."""
        el, lm = _enforcer()
        lease = lm.create_lease("ag-auth-2", uuid4(), "read:files", {}, "test", "pol")
        rec = _rec("ag-auth-2", ResponseType.ESCALATE, target_capability="read:files")
        el.enforce(rec)
        assert lm.get_lease(lease.lease_id).state != LeaseState.REVOKED

    def test_pending_escalation_does_not_grant_additional_capability(self):
        """A pending escalation must not grant additional capabilities."""
        el, lm = _enforcer()
        # No lease for this capability exists before escalation
        rec = _rec("ag-auth-3", ResponseType.ESCALATE, target_capability="credential:vault")
        el.enforce(rec)
        # After escalation, the capability must still not be covered
        eval_result = lm.evaluate("ag-auth-3", "credential:vault", "/secrets")
        assert not eval_result.capability_covered, (
            "Pending escalation must not grant the capability — agent must not gain access"
        )

    def test_different_agent_not_affected_by_escalation(self):
        """Escalating one agent must not affect another agent's state."""
        el, lm = _enforcer()
        other_lease = lm.create_lease("ag-other", uuid4(), "read:files", {}, "test", "pol")
        rec = _rec("ag-target", ResponseType.ESCALATE, target_capability="credential:vault")
        el.enforce(rec)
        assert lm.get_lease(other_lease.lease_id).state == LeaseState.ACTIVE

    def test_escalate_outcome_is_failed_not_permit(self):
        """Callers must not be able to interpret ESCALATE as a permit decision."""
        el, _ = _enforcer()
        rec = _rec("ag-auth-4", ResponseType.ESCALATE)
        result = el.enforce(rec)
        assert result.outcome != EnforcementOutcome.SUCCESS, (
            "ESCALATE must never succeed — the operation must be blocked"
        )
        assert result.outcome == EnforcementOutcome.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 regression — RESTRICT still works
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase3RestrictRegression:
    """Confirm Phase 3 RESTRICT behavior is preserved after Phase 4 changes."""

    def test_restrict_still_suspends_targeted_lease(self):
        el, lm = _enforcer()
        lease = lm.create_lease("ag-reg-1", uuid4(), "read:files", {}, "test", "pol")
        rec = _rec("ag-reg-1", ResponseType.RESTRICT, target_capability="read:files")
        result = el.enforce(rec)
        assert result.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(lease.lease_id).state == LeaseState.SUSPENDED

    def test_restrict_unrelated_lease_unchanged(self):
        el, lm = _enforcer()
        _target = lm.create_lease("ag-reg-2", uuid4(), "read:files", {}, "test", "pol")
        other = lm.create_lease("ag-reg-2", uuid4(), "write:files", {}, "test", "pol")
        rec = _rec("ag-reg-2", ResponseType.RESTRICT, target_capability="read:files")
        el.enforce(rec)
        assert lm.get_lease(other.lease_id).state == LeaseState.ACTIVE

    def test_restrict_missing_target_returns_failed(self):
        el, _ = _enforcer()
        rec = _rec("ag-reg-3", ResponseType.RESTRICT, target_capability=None)
        assert el.enforce(rec).outcome == EnforcementOutcome.FAILED

    def test_restrict_not_confused_with_escalate(self):
        """RESTRICT and ESCALATE must be dispatched independently."""
        el, lm = _enforcer()
        lease = lm.create_lease("ag-reg-4", uuid4(), "delete:data", {}, "test", "pol")

        restrict_rec = _rec("ag-reg-4", ResponseType.RESTRICT, target_capability="delete:data")
        escalate_rec = _rec("ag-reg-4", ResponseType.ESCALATE, target_capability="delete:data")

        r1 = el.enforce(restrict_rec)
        r2 = el.enforce(escalate_rec)

        assert r1.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(lease.lease_id).state == LeaseState.SUSPENDED

        assert r2.outcome == EnforcementOutcome.FAILED
        entry = el.get_pending_escalation(escalate_rec.recommendation_id)
        assert entry is not None  # escalate registered separately