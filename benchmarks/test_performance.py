"""Performance Baseline Measurement (T12.4).

Measures pipeline throughput and P99 latency under controlled conditions.

IMPORTANT: These are baseline measurements for research calibration purposes.
The targets (P99<=50ms, >=100 events/s) are PROPOSALS from NFR-PERF-001/002
that have NOT been verified as achievable. Results here are actual measurements.

Satisfies: T12.4, NFR-PERF-001, NFR-PERF-002
"""
from __future__ import annotations
import os
import statistics
import time
import pytest

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://perf")

from datetime import datetime, timezone
from uuid import uuid4
from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult


def _now():
    return datetime.now(timezone.utc)


def make_event(agent_id: str, session_id, i: int = 0) -> AgentActionEvent:
    return AgentActionEvent.model_validate({
        "agent_id": agent_id,
        "session_id": str(session_id),
        "timestamp": str(_now()),
        "action_type": ActionType.READ.value,
        "capability_requested": "read:files",
        "target_resource": f"/data/file-{i}.csv",
        "authorization_result": AuthorizationResult.ALLOWED.value,
        "is_simulated": True,
    }, strict=False)


class TestPerformanceBaseline:
    """
    Performance baseline measurements.

    NOTE: These tests measure actual in-process performance with the in-memory
    pipeline (no database). Real-world performance with PostgreSQL will differ.
    No performance guarantees are made. See NFR-PERF-001 through NFR-PERF-003.
    """

    def test_single_event_latency_baseline(self):
        """Measure single-event processing latency. Records result; does not assert a threshold."""
        pipeline = VarynxPipeline()
        sid = uuid4()
        # Warmup
        for i in range(3):
            e = make_event("perf-warmup", uuid4(), i)
            pipeline.process_event(e, action_id=f"warmup-{i}", skip_timestamp_check=True)

        latencies_ms = []
        for i in range(50):
            e = make_event("perf-agent-001", sid, i)
            start = time.perf_counter()
            result = pipeline.process_event(e, action_id=f"perf-single-{i}", skip_timestamp_check=True)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert result.error is None, f"Pipeline error: {result.error}"
            latencies_ms.append(elapsed_ms)

        p50 = statistics.median(latencies_ms)
        p99 = sorted(latencies_ms)[int(len(latencies_ms) * 0.99) - 1] if len(latencies_ms) > 1 else latencies_ms[0]
        mean_ms = statistics.mean(latencies_ms)
        std_ms = statistics.stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0

        print(f"\nSingle-event latency (n=50, in-memory):")
        print(f"  mean={mean_ms:.2f}ms  std={std_ms:.2f}ms  p50={p50:.2f}ms  p99={p99:.2f}ms")
        print(f"  NFR-PERF-001 proposal: P99 <= 50ms (not yet verified for DB-backed deployment)")

        # Soft assertion: just ensure the pipeline completes without error
        # Hard threshold (50ms) is NOT asserted because it is an unverified proposal
        assert p99 < 5000, f"P99 {p99:.1f}ms exceeds sanity limit of 5000ms"

    def test_batch_throughput_baseline(self):
        """Measure batch throughput. Records result; does not assert a threshold."""
        pipeline = VarynxPipeline()
        n_events = 100
        agent_id = "perf-throughput-001"
        sid = uuid4()
        events = [make_event(agent_id, sid, i) for i in range(n_events)]

        start = time.perf_counter()
        results = []
        for i, e in enumerate(events):
            r = pipeline.process_event(e, action_id=f"batch-{i}", skip_timestamp_check=True)
            results.append(r)
        elapsed = time.perf_counter() - start

        errors = [r.error for r in results if r.error]
        throughput = n_events / elapsed

        print(f"\nBatch throughput (n={n_events}, in-memory):")
        print(f"  elapsed={elapsed:.3f}s  throughput={throughput:.1f} events/s  errors={len(errors)}")
        print(f"  NFR-PERF-002 proposal: >= 100 events/s (not yet verified for DB-backed deployment)")

        assert len(errors) == 0, f"Pipeline errors during batch: {errors[:3]}"
        # Soft assertion: ensure at least 1 event/s (sanity check only)
        assert throughput > 1.0, f"Throughput {throughput:.1f} events/s is below sanity minimum"

        # Store results for reporting (no threshold assertion per research integrity)
        import json, pathlib, datetime as dt
        pathlib.Path("output").mkdir(exist_ok=True)
        perf_results = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "test": "batch_throughput",
            "n_events": n_events,
            "elapsed_seconds": elapsed,
            "throughput_events_per_second": throughput,
            "environment": "in-memory pipeline (no database)",
            "nfr_note": "NFR-PERF-002 (>=100 events/s) requires DB-backed deployment verification",
        }
        pathlib.Path("output/perf_batch.json").write_text(
            json.dumps(perf_results, indent=2)
        )

    def test_audit_chain_append_performance(self):
        """Measure audit store append performance for 100 records."""
        from varynx.engine.audit import AuditStore
        from varynx.models.audit import AuditRecordType
        store = AuditStore()
        n = 100
        start = time.perf_counter()
        for i in range(n):
            store.append(AuditRecordType.EVENT_INGESTED, f"entity-{i}", {"idx": i})
        elapsed = time.perf_counter() - start
        throughput = n / elapsed
        print(f"\nAudit append throughput (n={n}): {throughput:.0f} records/s")
        # Verify chain still valid
        valid, _ = store.verify_chain()
        assert valid is True
        assert throughput > 10, f"Audit throughput {throughput:.0f} rec/s below sanity minimum"