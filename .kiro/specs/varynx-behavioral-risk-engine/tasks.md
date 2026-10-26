# Implementation Plan: Varynx — Behavioral Risk Control Engine

**Project:** Varynx — Behavioral Risk Control Engine for Autonomous AI Agents
**Research Title:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents
**Test runner:** pytest + Hypothesis
**Original IDs:** T1.1-T13.4 preserved in task descriptions for traceability.

---

## Overview

47 tasks across 13 phases. Tasks 1-39 are completed and verified. Tasks 40-47 remain in progress.

---

## Tasks

- [x] 1. Project Scaffold and Python Package Structure (T1.1) - pyproject.toml, package skeleton, test dirs, .gitignore, README.md
- [x] 2. Docker and Database Environment (T1.2) - docker/Dockerfile, docker-compose.yml, alembic.ini, 9-table migration
- [x] 3. Core Data Models (T1.3) - Pydantic v2 models for event, agent, evidence, trust, lease, bcse, prediction, response, enforcement, audit
- [x] 4. Configuration System (T1.4) - VarynxConfig with all sub-configs, load_config(), YAML policy and threshold files
- [x] 5. Ingestion and Validation Layer (T2.1) - IngestionLayer: timestamp bounds, idempotency, correlation_id assignment
- [x] 6. Identity and Session Registry (T2.2) - IdentitySessionRegistry: agent/session management, escalation detection, spread tracking
- [x] 7. Capability Lease Manager (T2.3) - LeaseManager: ACTIVE/SUSPENDED/REVOKED/EXPIRED lifecycle, cascade operations
- [x] 8. Evidence Engine Framework and Detector Protocol (T3.1) - EvidenceEngine orchestrator, AnomalyDetector protocol
- [x] 9. Six Anomaly Detectors (T3.2) - capability_escalation, resource_anomaly, action_frequency, authorization_bypass, context_deviation, temporal_anomaly
- [x] 10. Evidence Integrity Hashing (T3.3) - compute_content_hash, compute_record_hash, verify_record_integrity, make_evidence_record_with_hash
- [x] 11. Trust Scorer and Classifier (T4.1) - TrustScorer, deterministic formula, TrustLevel classification, history tracking
- [x] 12. Predictive Intelligence Stub (T4.2) - PredictiveEngine Phase 1 stub returning STABLE trajectory
- [x] 13. Trajectory Engine Placeholder Phase 2 (T4.3) - TrajectoryProjection with is_stub=True and is_projected=True
- [x] 14. BCSE Interface and Stub (T5.1) - BCSeEngine Phase 1 stub with low_history_warning
- [x] 15. BCSE Engine Placeholder Phase 2 (T5.2) - BCSeResult full model, Phase 2 interface documented
- [x] 16. Adaptive Response Engine (T6.1) - AdaptiveResponseEngine: YAML policy, escalation monotonicity, de-escalation
- [x] 17. Runtime Enforcement Layer (T6.2) - EnforcementLayer: idempotency, dry-run, audit-before-action, lease cascade
- [x] 18. Audit Store and Hash Chain (T7.1) - AuditStore: SHA-256 hash chain, append-only, verify_chain
- [x] 19. Correlation Identifier Propagation (T7.2) - CorrelationTracer with full provenance chain query
- [x] 20. Top-Level Pipeline Processor (T7.3) - VarynxPipeline: full 10-step event processing per design.md Section 6
- [x] 21. FastAPI Application and Middleware (T8.1) - FastAPI app with CORS, correlation ID, rate limiting middleware
- [x] 22. Event Ingestion API (T8.2) - POST /events, POST /events/batch, GET /events/{event_id}
- [x] 23. Agent Session and Lease APIs (T8.3) - /agents, /sessions, /leases endpoints
- [x] 24. BCSE Audit and Evaluation APIs (T8.4) - /bcse/evaluate, /audit/*, /evaluate/* endpoints
- [x] 25. Authentication Authorization and Rate Limiting (T8.5) - RateLimitMiddleware 1000 req/min, auth placeholder
- [x] 26. OpenAPI Documentation and Response Envelope (T8.6) - success_response/error_response; OpenAPI at /api/v1/openapi.json
- [x] 27. Scenario Runner (T9.1) - ScenarioRunner: load_scenario, run, run_named, run_all
- [x] 28. Baseline Comparisons (T9.2) - B1 always-permit, B2 single-dimension, B3 session-average
- [x] 29. Metrics Computation (T9.3) - MetricsComputer: precision, recall, F1, accuracy
- [x] 30. Statistical Analysis and Reporting (T9.4) - EvaluationReport, BaselineComparator, mean/std/95% CI, Cohen's d
- [x] 31. Trust Score Properties (T10.1) - Hypothesis: score in [0,1], never increases Phase 1, history grows
- [x] 32. Evidence Engine Properties (T10.2) - Hash determinism, integrity, 6 detectors, composite score range
- [x] 33. Response Engine Properties (T10.3) - Determinism, CRITICAL to TERMINATE, escalation monotonicity
- [x] 34. API Serialization Properties (T10.4) - Float range, round-trip, enum serialization, envelope structure
- [x] 35. Lease State Machine Properties (T10.5) - REVOKED terminal, cascade, expiry, state history
- [x] 36. Research Methodology Document (T11.1) - docs/research_methodology.md: H1-H4, study design, baselines
- [x] 37. Evaluation Protocol Document (T11.2) - docs/evaluation_protocol.md: run procedure, ablation, limitations
- [x] 38. API Reference Documentation (T11.3) - docs/api_reference.md: all endpoints, schemas, error codes
- [x] 39. Framework Adapter Contract Document (T11.4) - docs/framework_adapter_contract.md: AgentAdapterProtocol
- [x] 40. Full Pipeline Integration Test Suite (T12.1) - tests/integration/test_pipeline_integration.py
- [x] 41. Audit Chain Integrity Test (T12.2) - tests/integration/test_audit_chain.py
- [x] 42. Reproduce Script (T12.3) - reproduce.sh: full install, test, evaluate, report
- [x] 43. Performance Baseline Measurement (T12.4) - tests/benchmarks/test_performance.py
- [x] 44. Dashboard Scaffold (T13.1) - Next.js 14 + Tailwind under dashboard/
- [x] 45. Agent Overview and Session Detail Views (T13.2) - dashboard/app/agents/ pages
- [x] 46. Audit View and Evaluation View (T13.3) - dashboard/app/audit/ and dashboard/app/evaluation/
- [x] 47. BCSE Counterfactual View Phase 2 Placeholder (T13.4) - dashboard/app/bcse/ placeholder page

---

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1,  "tasks": [1] },
    { "wave": 2,  "tasks": [2, 3, 4, 36, 37] },
    { "wave": 3,  "tasks": [5, 6, 7, 35, 39] },
    { "wave": 4,  "tasks": [8] },
    { "wave": 5,  "tasks": [9, 10] },
    { "wave": 6,  "tasks": [11] },
    { "wave": 7,  "tasks": [12, 31] },
    { "wave": 8,  "tasks": [13, 14] },
    { "wave": 9,  "tasks": [15, 32] },
    { "wave": 10, "tasks": [16] },
    { "wave": 11, "tasks": [17, 33] },
    { "wave": 12, "tasks": [18] },
    { "wave": 13, "tasks": [19] },
    { "wave": 14, "tasks": [20] },
    { "wave": 15, "tasks": [21] },
    { "wave": 16, "tasks": [22, 23, 24, 25] },
    { "wave": 17, "tasks": [26, 34, 38] },
    { "wave": 18, "tasks": [27] },
    { "wave": 19, "tasks": [28, 29] },
    { "wave": 20, "tasks": [30] },
    { "wave": 21, "tasks": [40] },
    { "wave": 22, "tasks": [41, 42, 43, 44] },
    { "wave": 23, "tasks": [45, 46, 47] }
  ]
}
```

---

## Notes

Original task IDs T1.1-T13.4 are preserved inside each task description for traceability.
Sequential numbers 1-47 are required by the Kiro task parser.

Tasks 13 (T4.3), 15 (T5.2), and 47 (T13.4) are Phase 2 placeholders per specification.
Tasks 40-43 (T12.x) integration tests are pending implementation below.
Tasks 44-47 (T13.x) require Node.js/Next.js environment.
Task 2 (T1.2) DB verification requires a running PostgreSQL/TimescaleDB instance.
No performance benchmarks have been measured - all figures in spec require empirical evaluation.