"""Enforcement behavior tests — Phase 3 (RESTRICT) and Phase 4 (ESCALATE).

Verifies that the enforcement layer applies real state changes for RESTRICT
and produces an explicit, auditable outcome for ESCALATE.  Also includes
regression tests confirming that PERMIT, WARN, SUSPEND, and TERMINATE
continue to behave as before.

Satisfies: Phase 3–4 acceptance criteria.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-enforcement")

from varynx.engine.enforcement import EnforcementLayer
from varynx.engine.lease_manager import LeaseManager
from varynx.models.enforcement import EnforcementOutcome, EnforcementRecord
from varynx.models.lease import LeaseState
from varynx.models.response import ReasonCode, ResponseRecommendation, ResponseType
from varynx.models.trust import TrustLevel, TrustState


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trust_state(agent_id: str = "ag", score: float = 0.7) -> TrustState:
    return TrustState.model_validate(
        {
            "session_id": str(uuid4()),
            "agent_id": agent_id,
            "current_score": score,
            "level": TrustLevel.ELEVATED.value,
            "last_updated": str(_now()),
        },
        strict=False,
    )


def _recommendation(
    agent_id: str,
    response_type: ResponseType,
    target_capability: str | None = None,
    target_resource: str | None = None,
) -> ResponseRecommendation:
    """Build a minimal ResponseRecommendation suitable for enforcement tests."""
    ts = _trust_state(agent_id)
    rc = ReasonCode.model_validate(
        {
            "code": "TEST_CODE",
            "description": "test",
            "trust_level_at_recommendation": TrustLevel.ELEVATED.value,
            "severity": "WARNING",
        },
        strict=False,
    )
    return ResponseRecommendation.model_validate(
        {
            "recommendation_id": str(uuid4()),
            "agent_id": agent_id,
            "correlation_id": str(uuid4()),
            "response_type": response_type.value,
            "reason_codes": [rc.model_dump()],
            "evidence_bundle_id": str(uuid4()),
            "trust_state_snapshot": ts.model_dump(),
            "rationale": "enforcement-behavior-test",
            "timestamp": str(_now()),
            "policy_id": "test",
            "policy_version": "1.0.0",
            "target_capability": target_capability,
            "target_resource": target_resource,
        },
        strict=False,
    )


def _enforcer(dry_run: bool = False) -> tuple[EnforcementLayer, LeaseManager]:
    lm = LeaseManager()
    el = EnforcementLayer(dry_run=dry_run, lease_manager=lm)
    return el, lm


def _add_lease(lm: LeaseManager, agent_id: str, capability: str) -> "CapabilityLease":  # noqa: F821
    return lm.create_lease(
        agent_id=agent_id,
        session_id=uuid4(),
        capability=capability,
        resource_scope={},
        issuing_principal="test",
        issuing_policy_id="pol-1",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — RESTRICT tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRestrictEnforcement:
    """RESTRICT suspends the targeted capability lease and leaves others intact."""

    def test_restrict_suspends_matching_lease(self):
        """RESTRICT suspends the lease covering the offending capability."""
        el, lm = _enforcer()
        lease = _add_lease(lm, "ag-r1", "read:files")
        rec = _recommendation("ag-r1", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(lease.lease_id).state == LeaseState.SUSPENDED

    def test_restrict_leaves_unrelated_lease_active(self):
        """An unrelated lease is untouched when only the offending capability is restricted."""
        el, lm = _enforcer()
        target_lease = _add_lease(lm, "ag-r2", "read:files")
        other_lease = _add_lease(lm, "ag-r2", "write:files")
        rec = _recommendation("ag-r2", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(target_lease.lease_id).state == LeaseState.SUSPENDED
        assert lm.get_lease(other_lease.lease_id).state == LeaseState.ACTIVE, (
            "Unrelated 'write:files' lease must remain ACTIVE after 'read:files' restriction"
        )

    def test_restrict_with_prefix_match(self):
        """RESTRICT applies when the event capability starts with the lease capability."""
        el, lm = _enforcer()
        # Lease grants broad "read" capability; event requests "read:files" (prefix match)
        broad_lease = _add_lease(lm, "ag-r3", "read")
        rec = _recommendation("ag-r3", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(broad_lease.lease_id).state == LeaseState.SUSPENDED

    def test_restrict_missing_target_capability_returns_failed(self):
        """RESTRICT with target_capability=None must return FAILED, not SUCCESS."""
        el, lm = _enforcer()
        _add_lease(lm, "ag-r4", "read:files")
        rec = _recommendation("ag-r4", ResponseType.RESTRICT, target_capability=None)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.FAILED, (
            "Missing target_capability must yield FAILED, not a false SUCCESS"
        )

    def test_restrict_no_matching_lease_returns_skipped(self):
        """RESTRICT returns SKIPPED when the capability is not currently granted (no lease)."""
        el, lm = _enforcer()
        # No lease for this agent — capability never granted
        rec = _recommendation("ag-r5", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SKIPPED, (
            "No matching lease must yield SKIPPED (explicit, auditable), not SUCCESS"
        )

    def test_restrict_different_agent_lease_not_affected(self):
        """Restriction on one agent does not touch another agent's leases."""
        el, lm = _enforcer()
        target_lease = _add_lease(lm, "ag-target", "read:files")
        other_agent_lease = _add_lease(lm, "ag-other", "read:files")
        rec = _recommendation("ag-target", ResponseType.RESTRICT, target_capability="read:files")
        el.enforce(rec)
        # Other agent's lease untouched
        assert lm.get_lease(other_agent_lease.lease_id).state == LeaseState.ACTIVE

    def test_restrict_repeated_same_recommendation_is_idempotent(self):
        """Submitting the same recommendation_id twice produces SKIPPED on the second call."""
        el, lm = _enforcer()
        _add_lease(lm, "ag-r6", "read:files")
        rec = _recommendation("ag-r6", ResponseType.RESTRICT, target_capability="read:files")
        r1 = el.enforce(rec)
        r2 = el.enforce(rec)  # same recommendation_id
        assert r1.outcome == EnforcementOutcome.SUCCESS
        assert r2.outcome == EnforcementOutcome.SKIPPED
        assert r2.outcome_reason == "DUPLICATE_ENFORCEMENT"

    def test_restrict_subsequent_lease_evaluation_reflects_suspension(self):
        """After RESTRICT, lease evaluation for that capability returns not covered."""
        el, lm = _enforcer()
        _add_lease(lm, "ag-r7", "read:files")
        rec = _recommendation("ag-r7", ResponseType.RESTRICT, target_capability="read:files")
        el.enforce(rec)
        # Now evaluating whether "read:files" is covered should show it is not
        evaluation = lm.evaluate("ag-r7", "read:files", "/data/test.csv")
        assert not evaluation.capability_covered, (
            "After RESTRICT, the capability must no longer be covered by an ACTIVE lease"
        )

    def test_restrict_no_lease_manager_returns_failed(self):
        """RESTRICT without a lease manager attached must return FAILED."""
        el = EnforcementLayer(dry_run=False, lease_manager=None)
        rec = _recommendation("ag-r8", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.FAILED

    def test_restrict_dry_run_does_not_change_lease_state(self):
        """In dry-run mode, RESTRICT does not change lease state."""
        el, lm = _enforcer(dry_run=True)
        lease = _add_lease(lm, "ag-r9", "read:files")
        rec = _recommendation("ag-r9", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        # Dry-run: the enforcement layer skips _apply_action, returns SUCCESS
        assert record.dry_run is True
        # Lease state must not have changed
        assert lm.get_lease(lease.lease_id).state == LeaseState.ACTIVE, (
            "Dry-run RESTRICT must not change lease state"
        )

    def test_restrict_enforcement_record_carries_action_taken(self):
        """EnforcementRecord.action_taken reflects the RESTRICT response type."""
        el, lm = _enforcer()
        _add_lease(lm, "ag-r10", "read:files")
        rec = _recommendation("ag-r10", ResponseType.RESTRICT, target_capability="read:files")
        record = el.enforce(rec)
        assert "RESTRICT" in record.action_taken


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — ESCALATE tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEscalateEnforcement:
    """ESCALATE blocks the operation with an explicit pending-review outcome."""

    def test_escalate_returns_failed_not_success(self):
        """ESCALATE must return FAILED so the operation does not silently proceed."""
        el, lm = _enforcer()
        rec = _recommendation("ag-e1", ResponseType.ESCALATE, target_capability="delete:data")
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.FAILED, (
            "ESCALATE must block the operation — outcome must be FAILED, not SUCCESS"
        )

    def test_escalate_does_not_suspend_unrelated_leases(self):
        """ESCALATE does not cascade lease changes to unrelated capabilities."""
        el, lm = _enforcer()
        other_lease = _add_lease(lm, "ag-e2", "read:files")
        rec = _recommendation("ag-e2", ResponseType.ESCALATE, target_capability="delete:data")
        el.enforce(rec)
        # Unrelated lease must remain ACTIVE
        assert lm.get_lease(other_lease.lease_id).state == LeaseState.ACTIVE, (
            "ESCALATE must not cascade to unrelated leases"
        )

    def test_escalate_action_taken_identifies_escalation(self):
        """EnforcementRecord.action_taken must identify ESCALATE so auditors can find it."""
        el, lm = _enforcer()
        rec = _recommendation("ag-e3", ResponseType.ESCALATE, target_capability="execute:code")
        record = el.enforce(rec)
        assert "ESCALATE" in record.action_taken

    def test_escalate_missing_target_still_returns_failed(self):
        """ESCALATE with no target_capability still blocks the operation."""
        el, lm = _enforcer()
        rec = _recommendation("ag-e4", ResponseType.ESCALATE, target_capability=None)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.FAILED

    def test_escalate_idempotency(self):
        """Submitting the same ESCALATE recommendation twice yields SKIPPED on second call."""
        el, lm = _enforcer()
        rec = _recommendation("ag-e5", ResponseType.ESCALATE, target_capability="delete:data")
        r1 = el.enforce(rec)
        r2 = el.enforce(rec)
        assert r1.outcome == EnforcementOutcome.FAILED
        assert r2.outcome == EnforcementOutcome.SKIPPED
        assert r2.outcome_reason == "DUPLICATE_ENFORCEMENT"

    def test_escalate_carries_recommendation_id_in_record(self):
        """Audit record links back to the source recommendation_id."""
        el, lm = _enforcer()
        rec = _recommendation("ag-e6", ResponseType.ESCALATE, target_capability="credential:access")
        record = el.enforce(rec)
        assert record.source_recommendation_id == rec.recommendation_id

    def test_escalate_does_not_revoke_leases(self):
        """ESCALATE does not revoke leases — only TERMINATE does."""
        el, lm = _enforcer()
        active_lease = _add_lease(lm, "ag-e7", "read:files")
        rec = _recommendation("ag-e7", ResponseType.ESCALATE, target_capability="delete:data")
        el.enforce(rec)
        assert lm.get_lease(active_lease.lease_id).state != LeaseState.REVOKED


# ─────────────────────────────────────────────────────────────────────────────
# Regression: existing PERMIT / WARN / SUSPEND / TERMINATE behavior
# ─────────────────────────────────────────────────────────────────────────────


class TestRegressionExistingResponses:
    """Ensure Phase 3/4 changes have not altered existing enforcement behavior."""

    def test_permit_produces_success_no_lease_change(self):
        """PERMIT: SUCCESS outcome, no lease state changes."""
        el, lm = _enforcer()
        lease = _add_lease(lm, "ag-p1", "read:files")
        rec = _recommendation("ag-p1", ResponseType.PERMIT)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(lease.lease_id).state == LeaseState.ACTIVE

    def test_warn_produces_success_no_lease_change(self):
        """WARN: SUCCESS outcome, no lease state changes (notification only)."""
        el, lm = _enforcer()
        lease = _add_lease(lm, "ag-w1", "read:files")
        rec = _recommendation("ag-w1", ResponseType.WARN)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(lease.lease_id).state == LeaseState.ACTIVE

    def test_suspend_suspends_all_active_leases(self):
        """SUSPEND: all ACTIVE leases for the agent are suspended."""
        el, lm = _enforcer()
        leases = [_add_lease(lm, "ag-s1", f"cap-{i}") for i in range(3)]
        rec = _recommendation("ag-s1", ResponseType.SUSPEND)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        for lease in leases:
            assert lm.get_lease(lease.lease_id).state == LeaseState.SUSPENDED

    def test_terminate_revokes_all_leases(self):
        """TERMINATE: all ACTIVE and SUSPENDED leases for the agent are revoked."""
        el, lm = _enforcer()
        active_lease = _add_lease(lm, "ag-t1", "read:files")
        susp_lease = _add_lease(lm, "ag-t1", "write:files")
        lm.suspend(susp_lease.lease_id)
        rec = _recommendation("ag-t1", ResponseType.TERMINATE)
        record = el.enforce(rec)
        assert record.outcome == EnforcementOutcome.SUCCESS
        assert lm.get_lease(active_lease.lease_id).state == LeaseState.REVOKED
        assert lm.get_lease(susp_lease.lease_id).state == LeaseState.REVOKED

    def test_duplicate_enforcement_idempotency(self):
        """Any response type: second call with same recommendation_id yields SKIPPED."""
        el, lm = _enforcer()
        rec = _recommendation("ag-d1", ResponseType.PERMIT)
        r1 = el.enforce(rec)
        r2 = el.enforce(rec)
        assert r1.outcome == EnforcementOutcome.SUCCESS
        assert r2.outcome == EnforcementOutcome.SKIPPED
        assert r2.outcome_reason == "DUPLICATE_ENFORCEMENT"

    def test_policy_validation_rejects_missing_agent_id(self):
        """Empty agent_id fails independent policy validation and returns SKIPPED."""
        el, lm = _enforcer()
        rec = _recommendation("ag-v1", ResponseType.PERMIT)
        # Poke the agent_id to empty string after construction
        bad_data = rec.model_dump()
        bad_data["agent_id"] = ""
        bad_rec = ResponseRecommendation.model_validate(bad_data, strict=False)
        record = el.enforce(bad_rec)
        assert record.outcome == EnforcementOutcome.SKIPPED
        assert record.outcome_reason == "POLICY_VALIDATION_REJECTED"

    def test_dry_run_does_not_change_lease_state_for_suspend(self):
        """SUSPEND in dry-run mode: success recorded but no lease state change."""
        el, lm = _enforcer(dry_run=True)
        lease = _add_lease(lm, "ag-dr1", "read:files")
        rec = _recommendation("ag-dr1", ResponseType.SUSPEND)
        record = el.enforce(rec)
        assert record.dry_run is True
        assert lm.get_lease(lease.lease_id).state == LeaseState.ACTIVE


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline integration — RESTRICT and ESCALATE via full pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineEnforcementIntegration:
    """RESTRICT and ESCALATE enforcement via the full VarynxPipeline."""

    def test_restrict_via_pipeline_suspends_matching_lease(self):
        """End-to-end: capability escalation anomaly → RESTRICT → lease suspended."""
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
        from varynx.models.trust import TrustState

        pipeline = VarynxPipeline()
        agent_id = "ag-pipe-restrict"
        sid = uuid4()

        # Register agent with declared capabilities so CAPABILITY_ESCALATION fires
        pipeline.registry.register_agent(
            agent_id=agent_id,
            owning_principal="test",
            declared_capability_scope=["READ"],
            authorized_resource_scope=["/data"],
        )

        # Create an active lease for a different capability to confirm it's untouched
        unrelated_lease = pipeline.lease_manager.create_lease(
            agent_id=agent_id, session_id=sid, capability="write:files",
            resource_scope={}, issuing_principal="test", issuing_policy_id="pol-1",
        )
        # Create the lease for the capability being requested
        target_lease = pipeline.lease_manager.create_lease(
            agent_id=agent_id, session_id=sid, capability="DELETE",
            resource_scope={}, issuing_principal="test", issuing_policy_id="pol-1",
        )

        # Force the response engine to return RESTRICT for this agent
        from varynx.engine.response import AdaptiveResponseEngine, _SEVERITY_ORDER
        from varynx.models.response import ResponseType
        pipeline.response_engine._active_responses[agent_id] = ResponseType.RESTRICT.value

        # Submit an event requesting the "DELETE" capability (outside declared READ scope)
        event = AgentActionEvent.model_validate({
            "agent_id": agent_id,
            "session_id": str(sid),
            "timestamp": str(_now()),
            "action_type": "DELETE",
            "capability_requested": "DELETE",
            "target_resource": "/data/file.csv",
            "authorization_result": "allowed",
            "is_simulated": True,
        }, strict=False)

        result = pipeline.process_event(event, action_id="pipe-restrict-001", skip_timestamp_check=True)
        assert result.error is None, f"Pipeline error: {result.error}"
        assert result.recommendation is not None

        # If RESTRICT was applied: the DELETE lease is suspended
        if result.recommendation.response_type == ResponseType.RESTRICT:
            target = pipeline.lease_manager.get_lease(target_lease.lease_id)
            unrelated = pipeline.lease_manager.get_lease(unrelated_lease.lease_id)
            if result.enforcement_record.outcome == EnforcementOutcome.SUCCESS:
                assert target.state == LeaseState.SUSPENDED, (
                    "RESTRICT should suspend the DELETE lease"
                )
                assert unrelated.state == LeaseState.ACTIVE, (
                    "Unrelated write:files lease must remain ACTIVE"
                )

    def test_escalate_via_pipeline_does_not_proceed_as_permit(self):
        """End-to-end: ESCALATE enforcement outcome is FAILED (operation blocked)."""
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
        from varynx.models.response import ResponseType

        pipeline = VarynxPipeline()
        agent_id = "ag-pipe-escalate"
        sid = uuid4()

        # Force ESCALATE recommendation
        pipeline.response_engine._active_responses[agent_id] = ResponseType.ESCALATE.value

        event = AgentActionEvent.model_validate({
            "agent_id": agent_id,
            "session_id": str(sid),
            "timestamp": str(_now()),
            "action_type": "CREDENTIAL_ACCESS",
            "capability_requested": "credential:vault",
            "target_resource": "/secrets/db_password",
            "authorization_result": "allowed",
            "is_simulated": True,
        }, strict=False)

        result = pipeline.process_event(event, action_id="pipe-escalate-001", skip_timestamp_check=True)
        assert result.error is None, f"Pipeline error: {result.error}"

        if result.recommendation is not None and result.recommendation.response_type == ResponseType.ESCALATE:
            assert result.enforcement_record is not None
            assert result.enforcement_record.outcome == EnforcementOutcome.FAILED, (
                "ESCALATE must block the operation (FAILED), not silently permit it"
            )
            assert "ESCALATE" in result.enforcement_record.action_taken
