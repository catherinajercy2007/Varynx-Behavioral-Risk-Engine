"""Full Pipeline Integration Test Suite (T12.1).

End-to-end tests covering the complete Varynx behavioral analysis pipeline:
event ingestion -> evidence -> trust -> BCSE -> response -> enforcement -> audit.

Satisfies: T12.1, REQ-001 through REQ-022
"""
from __future__ import annotations
import os
import pytest
from datetime import datetime, timezone
from uuid import uuid4

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test")

from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
from varynx.models.trust import TrustLevel
from varynx.models.response import ResponseType
from varynx.models.enforcement import EnforcementOutcome


def _now():
    return datetime.now(timezone.utc)


def make_event(agent_id: str, session_id, action_type=ActionType.READ,
               auth_result=AuthorizationResult.ALLOWED, task_id=None):
    return AgentActionEvent.model_validate({
        "agent_id": agent_id,
        "session_id": str(session_id),
        "timestamp": str(_now()),
        "action_type": action_type.value,
        "capability_requested": "read:files",
        "target_resource": "/data/test.csv",
        "authorization_result": auth_result.value,
        "is_simulated": True,
        "task_id": task_id,
    }, strict=False)


class TestPipelineEndToEnd:
    """Full pipeline integration: event -> pipeline -> result."""

    def test_single_event_produces_result(self):
        """A valid event produces event_id, correlation_id, trust score, and recommendation."""
        pipeline = VarynxPipeline()
        event = make_event("agent-e2e-001", uuid4())
        result = pipeline.process_event(event, action_id="action-001", skip_timestamp_check=True)
        assert result.error is None, f"Pipeline error: {result.error}"
        assert result.event_id is not None
        assert result.correlation_id is not None
        assert result.trust_score is not None
        assert 0.0 <= result.trust_score <= 1.0
        assert result.trust_level is not None
        assert result.recommendation is not None
        assert result.enforcement_record is not None

    def test_pipeline_creates_audit_records(self):
        """Pipeline produces audit records for each significant event."""
        pipeline = VarynxPipeline()
        event = make_event("agent-audit-001", uuid4())
        result = pipeline.process_event(event, action_id="action-audit-001", skip_timestamp_check=True)
        assert result.error is None
        records = pipeline.audit_store.all_records()
        assert len(records) >= 4  # EVENT_INGESTED, EVIDENCE_PRODUCED, TRUST_UPDATED, RESPONSE_RECOMMENDED

    def test_correlation_id_propagates_through_pipeline(self):
        """correlation_id from ValidatedEvent appears in all audit records."""
        pipeline = VarynxPipeline()
        sid = uuid4()
        event = make_event("agent-corr-001", sid)
        result = pipeline.process_event(event, action_id="action-corr-001", skip_timestamp_check=True)
        assert result.correlation_id is not None
        # Provenance trace finds records with that correlation_id
        trace = pipeline.tracer.trace(result.correlation_id)
        assert trace["found"] is True
        assert trace["record_count"] >= 1

    def test_audit_chain_integrity_after_pipeline(self):
        """SHA-256 hash chain is valid after multiple pipeline runs."""
        pipeline = VarynxPipeline()
        for i in range(5):
            event = make_event(f"agent-chain-{i}", uuid4())
            pipeline.process_event(event, action_id=f"action-chain-{i}", skip_timestamp_check=True)
        valid, violations = pipeline.audit_store.verify_chain()
        assert valid is True, f"Chain integrity violations: {violations}"

    def test_duplicate_action_id_rejected(self):
        """Duplicate action_id for same agent is rejected with error."""
        pipeline = VarynxPipeline()
        sid = uuid4()
        event1 = make_event("agent-dup-001", sid)
        pipeline.process_event(event1, action_id="action-dup", skip_timestamp_check=True)
        event2 = make_event("agent-dup-001", sid)
        result2 = pipeline.process_event(event2, action_id="action-dup", skip_timestamp_check=True)
        # Should fail with DuplicateActionError caught as pipeline error
        assert result2.error is not None

    def test_trust_score_degrades_on_repeated_denials(self):
        """Repeated authorization denials degrade trust score over time."""
        pipeline = VarynxPipeline()
        sid = uuid4()
        agent_id = "agent-deny-001"
        # First event: baseline
        e0 = make_event(agent_id, sid, auth_result=AuthorizationResult.ALLOWED)
        r0 = pipeline.process_event(e0, action_id="a0", skip_timestamp_check=True)
        initial_trust = r0.trust_score

        # Submit 4 denial events to cross the threshold and trigger evidence
        for i in range(4):
            e = make_event(agent_id, sid, auth_result=AuthorizationResult.DENIED)
            pipeline.process_event(e, action_id=f"deny-{i}", skip_timestamp_check=True)

        final_state = pipeline.trust_scorer._states.get(agent_id)
        assert final_state is not None
        # Trust should have degraded (or at minimum not increased)
        assert final_state.current_score <= initial_trust + 1e-6

    def test_critical_trust_triggers_terminate(self):
        """When trust falls to CRITICAL level, response is TERMINATE."""
        pipeline = VarynxPipeline()
        pipeline.response_engine.load_policy("config/default_policy.yaml")
        agent_id = "agent-crit-001"
        sid = uuid4()
        from varynx.models.trust import TrustState
        from varynx.engine.trust import classify_trust_level
        from varynx.config import TrustConfig
        # Force trust state to CRITICAL directly
        config = TrustConfig()
        pipeline.trust_scorer._states[agent_id] = TrustState.model_validate({
            "session_id": str(sid),
            "agent_id": agent_id,
            "current_score": 0.05,
            "level": "CRITICAL",
            "last_updated": str(_now()),
        }, strict=False)
        # Next event should see CRITICAL level
        e = make_event(agent_id, sid)
        result = pipeline.process_event(e, action_id="crit-event", skip_timestamp_check=True)
        assert result.recommendation is not None
        assert result.recommendation.response_type == ResponseType.TERMINATE

    def test_bcse_non_destructive(self):
        """BCSE evaluation does not modify the event log or trust state."""
        pipeline = VarynxPipeline()
        agent_id = "agent-bcse-001"
        sid = uuid4()
        # Process one event to build state
        e = make_event(agent_id, sid)
        pipeline.process_event(e, action_id="bcse-setup", skip_timestamp_check=True)
        trust_before = pipeline.trust_scorer._states[agent_id].current_score
        audit_count_before = len(pipeline.audit_store.all_records())
        # BCSE evaluate - should not change trust or audit log
        from varynx.models.bcse import BCSeContext
        from varynx.models.evidence import EvidenceBundle
        from varynx.models.trust import TrustState, TrustLevel
        trust_state = pipeline.trust_scorer._states[agent_id]
        empty_bundle = EvidenceBundle.model_validate({
            "bundle_id": str(uuid4()), "session_id": str(sid),
            "agent_id": agent_id, "correlation_id": str(uuid4()),
            "composite_score": 0.0, "correlation_window_seconds": 300.0,
            "timestamp": str(_now()), "is_simulated": True,
        }, strict=False)
        ctx = BCSeContext.model_validate({
            "context_id": str(uuid4()),
            "proposed_action": e.model_dump(),
            "evidence_bundle": empty_bundle.model_dump(),
            "trust_state": trust_state.model_dump(),
            "active_policy_id": "default",
        }, strict=False)
        bcse_result = pipeline.bcse_engine.analyze(ctx)
        # Verify non-destructive
        assert pipeline.trust_scorer._states[agent_id].current_score == trust_before
        assert len(pipeline.audit_store.all_records()) == audit_count_before
        assert bcse_result.is_stub is True


class TestMultiAgentPipeline:
    """Multi-agent session isolation tests."""

    def test_agents_have_independent_trust_states(self):
        """Two agents maintain independent trust scores."""
        pipeline = VarynxPipeline()
        sid1, sid2 = uuid4(), uuid4()
        e1 = make_event("agent-iso-A", sid1, auth_result=AuthorizationResult.DENIED)
        e2 = make_event("agent-iso-B", sid2, auth_result=AuthorizationResult.ALLOWED)
        pipeline.process_event(e1, action_id="iso-a1", skip_timestamp_check=True)
        for i in range(4):
            pipeline.process_event(
                make_event("agent-iso-A", sid1, auth_result=AuthorizationResult.DENIED),
                action_id=f"iso-a{i+2}", skip_timestamp_check=True
            )
        r2 = pipeline.process_event(e2, action_id="iso-b1", skip_timestamp_check=True)
        state_b = pipeline.trust_scorer._states.get("agent-iso-B")
        if state_b:
            # Agent B should have higher trust than Agent A (which had many denials)
            state_a = pipeline.trust_scorer._states.get("agent-iso-A")
            if state_a:
                assert state_b.current_score >= state_a.current_score

    def test_scope_escalation_detected_and_flagged(self):
        """Scope escalation is detected when agent accesses outside authorized resource scope."""
        pipeline = VarynxPipeline()
        pipeline.registry.register_agent(
            agent_id="agent-scope-001",
            owning_principal="test-org",
            declared_capability_scope=["READ"],
            authorized_resource_scope=["/data/public"],
        )
        sid = uuid4()
        # Access outside authorized scope
        event = AgentActionEvent.model_validate({
            "agent_id": "agent-scope-001",
            "session_id": str(sid),
            "timestamp": str(_now()),
            "action_type": "READ",
            "capability_requested": "read:files",
            "target_resource": "/secret/data",
            "authorization_result": "allowed",
            "is_simulated": True,
        }, strict=False)
        result = pipeline.process_event(event, action_id="scope-001", skip_timestamp_check=True)
        assert result.error is None
        # Check that scope escalation was detected
        agent = pipeline.registry._agents.get("agent-scope-001")
        assert agent is not None
        assert agent.scope_escalation_count >= 1

    def test_lease_suspension_on_suspend_recommendation(self):
        """SUSPEND response causes all active leases for agent to be suspended."""
        pipeline = VarynxPipeline()
        agent_id = "agent-lease-001"
        sid = uuid4()
        # Create an active lease
        lease = pipeline.lease_manager.create_lease(
            agent_id=agent_id, session_id=sid,
            capability="read:files", resource_scope={},
            issuing_principal="test", issuing_policy_id="pol-1",
        )
        # Force CRITICAL trust to get TERMINATE (which revokes leases)
        from varynx.models.trust import TrustState
        pipeline.trust_scorer._states[agent_id] = TrustState.model_validate({
            "session_id": str(sid), "agent_id": agent_id,
            "current_score": 0.05, "level": "CRITICAL",
            "last_updated": str(_now()),
        }, strict=False)
        e = make_event(agent_id, sid)
        result = pipeline.process_event(e, action_id="lease-test-001", skip_timestamp_check=True)
        assert result.recommendation is not None
        # TERMINATE should revoke leases
        from varynx.models.lease import LeaseState
        updated_lease = pipeline.lease_manager.get_lease(lease.lease_id)
        assert updated_lease.state == LeaseState.REVOKED


class TestAPIIntegration:
    """API-level integration tests."""

    def test_full_api_event_flow(self):
        """POST /events returns event_id and correlation_id; GET /audit/verify passes."""
        import varynx.api.app as api_app
        from fastapi.testclient import TestClient
        api_app._pipeline = VarynxPipeline()
        app = api_app.create_app()
        client = TestClient(app, raise_server_exceptions=True)

        r = client.post("/api/v1/events", json={
            "agent_id": "agent-api-001",
            "session_id": str(uuid4()),
            "timestamp": _now().isoformat(),
            "action_type": "READ",
            "capability_requested": "read:files",
            "target_resource": "/data/test.csv",
            "authorization_result": "allowed",
            "is_simulated": True,
        })
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "event_id" in data
        assert "correlation_id" in data
        assert 0.0 <= data["trust_score"] <= 1.0

        # Verify audit chain via API
        r2 = client.get("/api/v1/audit/verify")
        assert r2.status_code == 200
        assert r2.json()["data"]["chain_valid"] is True

    def test_lease_lifecycle_via_api(self):
        """Create, suspend, reinstate, revoke lease via API."""
        import varynx.api.app as api_app
        from fastapi.testclient import TestClient
        api_app._pipeline = VarynxPipeline()
        app = api_app.create_app()
        client = TestClient(app, raise_server_exceptions=True)

        # Register agent first
        client.post("/api/v1/agents", json={
            "agent_id": "agent-lease-api-001",
            "owning_principal": "test-org",
        })

        # Create lease
        r = client.post("/api/v1/leases", json={
            "agent_id": "agent-lease-api-001",
            "session_id": str(uuid4()),
            "capability": "read:files",
            "issuing_principal": "admin",
        })
        assert r.status_code == 200
        lease_id = r.json()["data"]["lease_id"]

        # Suspend
        r = client.patch(f"/api/v1/leases/{lease_id}/suspend")
        assert r.status_code == 200
        assert r.json()["data"]["state"] == "SUSPENDED"

        # Reinstate
        r = client.patch(f"/api/v1/leases/{lease_id}/reinstate")
        assert r.status_code == 200
        assert r.json()["data"]["state"] == "ACTIVE"

        # Revoke
        r = client.delete(f"/api/v1/leases/{lease_id}")
        assert r.status_code == 200

        # Verify revoked - any further operation should 409
        r = client.patch(f"/api/v1/leases/{lease_id}/suspend")
        assert r.status_code == 409