"""Audit Chain Integrity Tests (T12.2).

Verifies append-only behavior, tamper detection, and provenance query.

Satisfies: T12.2, REQ-013, REQ-014
"""
from __future__ import annotations
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from varynx.engine.audit import AuditStore, CorrelationTracer
from varynx.models.audit import AuditRecord, AuditRecordType


def _now():
    return datetime.now(timezone.utc)


class TestAuditChainIntegrity:

    def test_empty_chain_is_valid(self):
        store = AuditStore()
        valid, violations = store.verify_chain()
        assert valid is True
        assert violations == []

    def test_single_record_chain_valid(self):
        store = AuditStore()
        store.append(AuditRecordType.EVENT_INGESTED, "entity-1", {"k": "v"})
        valid, violations = store.verify_chain()
        assert valid is True

    def test_multi_record_chain_valid(self):
        """A sequence of appended records forms a valid hash chain."""
        store = AuditStore()
        for i in range(10):
            store.append(AuditRecordType.EVENT_INGESTED, f"entity-{i}", {"idx": i})
        valid, violations = store.verify_chain()
        assert valid is True
        assert len(violations) == 0

    def test_tamper_detected_when_record_modified(self):
        """Modifying a stored record is detected as TAMPER_DETECTED."""
        store = AuditStore()
        store.append(AuditRecordType.EVENT_INGESTED, "entity-1", {"data": "original"})
        store.append(AuditRecordType.TRUST_UPDATED, "entity-2", {"data": "second"})
        # Tamper: directly modify the first record's payload
        store._records[0] = AuditRecord.model_validate(
            {**store._records[0].model_dump(mode="json"), "payload": {"data": "TAMPERED"}},
            strict=False
        )
        valid, violations = store.verify_chain()
        assert valid is False
        assert len(violations) >= 1
        assert "TAMPER_DETECTED" in violations[0]

    def test_prior_record_hash_chains_correctly(self):
        """Each record's prior_record_hash matches the previous record's record_hash."""
        store = AuditStore()
        records = []
        for i in range(5):
            r = store.append(AuditRecordType.EVENT_INGESTED, f"e-{i}", {})
            records.append(r)
        # First record has no prior
        assert records[0].prior_record_hash is None
        # Each subsequent record chains to the previous
        for i in range(1, len(records)):
            assert records[i].prior_record_hash == records[i - 1].record_hash

    def test_query_by_correlation_id(self):
        """Records with a given correlation_id are retrievable by query."""
        store = AuditStore()
        cid = uuid4()
        store.append(AuditRecordType.EVENT_INGESTED, "e1", {}, correlation_id=cid)
        store.append(AuditRecordType.EVIDENCE_PRODUCED, "e2", {}, correlation_id=cid)
        store.append(AuditRecordType.TRUST_UPDATED, "e3", {})  # Different corr_id
        results = store.query_by_correlation_id(cid)
        assert len(results) == 2
        for r in results:
            assert r.correlation_id == cid

    def test_provenance_trace_returns_all_records(self):
        """CorrelationTracer.trace() returns all records for a correlation_id."""
        store = AuditStore()
        tracer = CorrelationTracer(store)
        cid = uuid4()
        for rt in [AuditRecordType.EVENT_INGESTED, AuditRecordType.EVIDENCE_PRODUCED,
                   AuditRecordType.TRUST_UPDATED, AuditRecordType.RESPONSE_RECOMMENDED]:
            store.append(rt, "entity", {}, correlation_id=cid)
        trace = tracer.trace(cid)
        assert trace["found"] is True
        assert trace["record_count"] == 4

    def test_provenance_trace_not_found_returns_found_false(self):
        """CorrelationTracer.trace() returns found=False for unknown correlation_id."""
        store = AuditStore()
        tracer = CorrelationTracer(store)
        trace = tracer.trace(uuid4())
        assert trace["found"] is False

    def test_pipeline_audit_records_chain_valid(self):
        """Full pipeline execution produces a valid hash chain in the audit store."""
        import os
        os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test")
        from varynx.engine.pipeline import VarynxPipeline
        from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
        pipeline = VarynxPipeline()
        for i in range(5):
            event = AgentActionEvent.model_validate({
                "agent_id": "agent-chain-001",
                "session_id": str(uuid4()),
                "timestamp": str(_now()),
                "action_type": "READ",
                "capability_requested": "read",
                "target_resource": "/data",
                "authorization_result": "allowed",
                "is_simulated": True,
            }, strict=False)
            pipeline.process_event(event, action_id=f"chain-{i}", skip_timestamp_check=True)
        valid, violations = pipeline.audit_store.verify_chain()
        assert valid is True, f"Chain violated: {violations}"

    def test_record_retrieval_by_id(self):
        """Individual audit records are retrievable by their record_id."""
        store = AuditStore()
        r = store.append(AuditRecordType.SESSION_CREATED, "session-1", {"agent": "ag"})
        fetched = store.get_record(r.record_id)
        assert fetched is not None
        assert fetched.record_id == r.record_id
        assert fetched.record_hash == r.record_hash

    def test_chain_with_session_metadata(self):
        """Records with session_id and agent_id preserve those fields."""
        store = AuditStore()
        sid = uuid4()
        cid = uuid4()
        r = store.append(
            AuditRecordType.SESSION_CREATED, "session-1", {},
            correlation_id=cid, session_id=sid, agent_id="agent-001"
        )
        assert r.session_id == sid
        assert r.agent_id == "agent-001"
        assert r.correlation_id == cid