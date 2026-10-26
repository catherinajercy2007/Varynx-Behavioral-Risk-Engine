# Varynx Corrected Implementation Plan

**Date:** 2026-10-25  
**Stage:** 1 — Corrected, evidence-based plan based on the baseline audit and 47-task audit  
**Source of truth:** Actual repository inspection (not `tasks.md` checkboxes)

---

## Honest Status Summary

| Status | Count | Task IDs |
|--------|-------|----------|
| VALIDATED | 30 | 1, 3, 4, 7, 8, 10, 11, 16, 18, 19, 20, 21, 22, 23, 26, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 27 (T9.1)*, 29 (T9.3)*, 30 (T9.4)* |
| TESTED | 6 | 5, 6, 9, 12, 14, 17, 42, 43 |
| IMPLEMENTED_NOT_TESTED | 4 | 24, 25, 28 |
| DEFERRED (Phase 2 placeholders) | 3 | 13, 15, 47 |
| BLOCKED | 4 | 2, 44, 45, 46 |
| NOT_STARTED | 0 | — |
| **Total** | **47** | |

*Items 27, 29, 30 are TESTED (exercised via integration) but not VALIDATED (no isolated unit tests).

**Net honest completion:** 30 VALIDATED + 6 TESTED + 3 DEFERRED (intentional) = 39 of 47 tasks in an acceptable state. 4 are IMPLEMENTED_NOT_TESTED, 4 are BLOCKED.

---

## Corrected Priority Order

Work proceeds in dependency order. Each item lists the reason, affected files, required work, tests, and acceptance criteria.

### P0 — Critical (must resolve before any deployment)

#### P0.1 — Initialize version control
- **Reason:** No `.git` directory. No rollback path. A single bad edit destroys work.
- **Affected:** Repository root
- **Work:** `git init`, add `.gitignore` (already present), initial commit of current state.
- **Acceptance:** `git status` shows clean tree; `git log` shows one commit.

#### P0.2 — Reconcile `pyproject.toml` with installed dependencies
- **Reason:** `sqlalchemy`, `psycopg2-binary`, `redis` are declared but NOT installed. The environment is inconsistent. Any code path importing them crashes.
- **Affected:** `pyproject.toml`, `.venv`
- **Work:** Either (a) `pip install` the missing packages and verify `alembic upgrade head` works against a local SQLite fallback, or (b) move `sqlalchemy`/`psycopg2`/`redis` to an optional `[db]` extra and document that the in-memory engine is the default. Option (b) is preferred — it makes the in-memory engine the supported default and avoids pretending DB support exists.
- **Acceptance:** `pip install -e .` succeeds with no missing imports; `import varynx` does not crash; `alembic` either runs or is documented as requiring the `[db]` extra.

#### P0.3 — Fix dashboard build (T13.1–T13.4)
- **Reason:** `npm run build` fails with `Cannot find module 'next/dist/compiled/commander'`. Tasks 44–47 are marked `[x]` but the dashboard has never been built.
- **Affected:** `dashboard/package.json` (bump `next` to a version compatible with Node 22, e.g., `next@14.2.15+` or `next@15`), `dashboard/next.config.js`
- **Work:** Bump Next.js version, run `npm install`, run `npm run build`, verify `dashboard/.next/` is produced.
- **Acceptance:** `npm run build` exits 0; `npm run start` serves the dashboard on port 3000; the four pages render without runtime errors.

#### P0.4 — Add API-level tests for untested routes (T8.4, T8.5)
- **Reason:** `tests/integration/test_pipeline_integration.py::TestAPIIntegration` only covers `/events` and `/leases`. Routes for `/bcse/evaluate`, `/audit/*`, `/evaluate/*`, and rate-limiting are untested.
- **Affected:** `tests/integration/test_pipeline_integration.py` (extend) or new `tests/integration/test_api_routes.py`
- **Work:** Add TestClient tests for: BCSE evaluate, audit query, audit verify, audit provenance, evaluate scenarios list, rate-limit 429 behavior.
- **Acceptance:** New tests pass; coverage of route handlers ≥ 80%.

#### P0.5 — Add baseline comparison test (T9.2)
- **Reason:** `BaselineB1AlwaysPermit`, `BaselineB2SingleDimension`, `BaselineB3SessionAverage` exist with real logic but are never exercised. No baseline results have been generated.
- **Affected:** New `tests/integration/test_baselines.py`
- **Work:** Run all three baselines against the existing 2 scenarios; verify B1 always returns PERMIT, B2 detects repeated denials, B3 computes session-average trust.
- **Acceptance:** Tests pass; baseline outputs are real (not fabricated).

### P1 — High (correctness and security)

#### P1.1 — Add authentication middleware
- **Reason:** T8.5 is IMPLEMENTED_NOT_TESTED. CORS is `*`. No auth is enforced. The API is unsafe to deploy.
- **Affected:** `varynx/api/middleware.py` (new `AuthMiddleware`), `varynx/config.py` (auth config), `tests/integration/test_api_routes.py`
- **Work:** Add a configurable auth middleware (API-key header for Phase 1; integrate with Cognito or JWT in Phase 2). Default-deny when auth is enabled. Document the local-dev bypass.
- **Acceptance:** With auth enabled, unauthenticated requests get 401; authenticated requests succeed. Test covers both paths. Security control is not weakened.

#### P1.2 — Restrict CORS
- **Reason:** `allow_origins=["*"]` is over-permissive.
- **Affected:** `varynx/api/app.py`
- **Work:** Make allowed origins configurable via `VARYNX_CORS_ORIGINS` env var; default to `["http://localhost:3000"]` for the dashboard.
- **Acceptance:** Non-allowed origin receives no CORS headers; allowed origin succeeds.

#### P1.3 — Add isolated unit tests for evidence detectors
- **Reason:** T3.2 (9) is TESTED via integration only. No test isolates a single detector's behavior.
- **Affected:** New `tests/unit/test_detectors.py`
- **Work:** Construct minimal `ValidatedEvent` + `SessionContext` + `LeaseEvaluation` fixtures; assert each detector fires/not-fires on representative inputs.
- **Acceptance:** Each detector has ≥2 passing tests (trigger and non-trigger case).

#### P1.4 — Add idempotency test for enforcement layer
- **Reason:** T6.2 (17) — `DUPLICATE_ENFORCEMENT` path is not explicitly tested.
- **Affected:** `tests/integration/test_pipeline_integration.py` (extend)
- **Work:** Apply the same recommendation twice; assert second produces `SKIPPED` with `DUPLICATE_ENFORCEMENT`.
- **Acceptance:** Test passes; idempotency contract is verified.

#### P1.5 — Add metrics/statistics unit tests
- **Reason:** T9.3 (29) and T9.4 (30) are TESTED indirectly. No isolated test verifies precision/recall/F1 math or mean/std/CI computation.
- **Affected:** New `tests/unit/test_metrics.py`
- **Work:** Test `MetricsComputer.compute_detection_metrics` with known TP/FP/TN/FN; test `aggregate_runs` mean/std/CI against hand-computed values.
- **Acceptance:** Tests pass; metric math is verified independently of pipeline.

### P2 — Medium (research validation)

#### P2.1 — Add at least 3 more evaluation scenarios
- **Reason:** Only 2 scenarios exist; `EvaluationReport` returns `INCOMPLETE` per REQ-026.6. H1–H4 cannot be evaluated.
- **Affected:** `scenarios/` (new YAML files)
- **Work:** Author scenarios covering: capability escalation, resource spread anomaly, context deviation, temporal anomaly, action frequency. Each with ground-truth annotations.
- **Acceptance:** ≥5 scenarios exist; `run_all` returns status `COMPLETE`; per-scenario F1 is computed from real pipeline output.

#### P2.2 — Run baseline comparison and produce a real evaluation report
- **Reason:** No `output/eval_*.json` exists. No baseline comparison has been executed.
- **Affected:** `output/`, `reproduce.sh`
- **Work:** Execute `reproduce.sh`; generate `output/eval_*.json`; verify report contains real per-scenario F1 and aggregated metrics.
- **Acceptance:** `output/` contains ≥1 JSON report; report status is `COMPLETE`; no fabricated values.

#### P2.3 — Run ablation study
- **Reason:** Ablation toggles exist in `config/evaluation_config.yaml` but have never been toggled.
- **Affected:** New `scripts/run_ablation.py` or extend `reproduce.sh`
- **Work:** For each of the 6 detectors: disable it, run all scenarios, record F1 delta. Produce `output/ablation_report.json`.
- **Acceptance:** Report contains 6 ablation rows; F1 deltas are real numbers (positive or negative).

#### P2.4 — Threshold sensitivity sweep
- **Reason:** Trust thresholds (0.85/0.65/0.40/0.20) are documented as "requiring empirical calibration" but never swept.
- **Affected:** New `scripts/threshold_sweep.py`
- **Work:** Vary `trust.threshold_low` and `trust.threshold_guarded` across ±0.05 increments; record precision/recall/F1 at each.
- **Acceptance:** Sweep output exists; sensitivity curve is plotted or tabulated.

#### P2.5 — DB-backed performance benchmark
- **Reason:** T12.4 measured in-memory only. NFR-PERF-001/002/003 require DB-backed measurement.
- **Affected:** `tests/benchmarks/test_performance.py` (extend), requires PostgreSQL
- **Work:** Stand up a local PostgreSQL (via Docker when available), run `alembic upgrade head`, run benchmarks against DB-backed storage.
- **Acceptance:** DB-backed P99 and throughput are measured and recorded. Not blocked on AWS — a local Docker PostgreSQL suffices.

### P3 — Future (Phase 2 capabilities)

#### P3.1 — Full BCSE engine (T5.2)
- **Reason:** Phase 2 deliverable. Phase 1 stub is intentional.
- **Work:** Implement policy simulation, consequence projection, divergence scoring, confidence derivation.
- **Acceptance:** `is_stub=False`; counterfactual_consequences is non-empty; divergence_score > 0 when policies differ.

#### P3.2 — Predictive trajectory engine (T4.3)
- **Reason:** Phase 2 deliverable.
- **Work:** Window-based linear regression over `TrustHistoryEntry`; configurable window/horizon; 95% CI; EARLY_WARNING_TRAJECTORY_BREACH emission.
- **Acceptance:** `is_stub=False`; trend classification is non-STABLE for degrading/improving histories; early_warning fires below threshold.

#### P3.3 — Framework adapters (LangChain, AutoGen, CrewAI)
- **Reason:** Documented in `docs/framework_adapter_contract.md` as Phase 2+.
- **Work:** Implement `AgentAdapterProtocol` for each framework; package as optional modules.
- **Acceptance:** Adapter translates a real framework event into a valid `AgentActionEvent`.

#### P3.4 — AWS deployment
- **Reason:** Phase 7–8 of the master prompt. No AWS infrastructure exists yet.
- **Work:** Produce `VARYNX_AWS_ARCHITECTURE.md`, IaC (CDK or Terraform), CI/CD pipeline, container hardening.
- **Acceptance:** Only after P0 and P1 are complete and the user has explicitly approved AWS provisioning.

---

## Milestone View

### Milestone 1 — Repository audit and implementation corrections (P0)
- P0.1 git init
- P0.2 dependency reconciliation
- P0.3 dashboard build fix
- P0.4 API route tests
- P0.5 baseline comparison test
- **Exit criteria:** All P0 items complete; `tasks.md` reconciled with reality; 90+ tests still pass.

### Milestone 2 — Security and integration correctness (P1)
- P1.1 auth middleware
- P1.2 CORS restriction
- P1.3 detector unit tests
- P1.4 enforcement idempotency test
- P1.5 metrics unit tests
- **Exit criteria:** All P1 tests pass; authn enforced when enabled; CORS not wildcards.

### Milestone 3 — Research evaluation and reproducibility (P2)
- P2.1 ≥5 scenarios
- P2.2 evaluation report generated
- P2.3 ablation study
- P2.4 threshold sweep
- P2.5 DB-backed benchmark (requires PostgreSQL)
- **Exit criteria:** `output/` contains real reports; `reproduce.sh` produces a COMPLETE report.

### Milestone 4 — AWS integration and non-production deployment (P3.4)
- Architecture decision record
- IaC (CDK or Terraform)
- CI/CD pipeline with OIDC federation
- Container hardening
- **Exit criteria:** Only after explicit user approval; no AWS resources created without sign-off.

### Milestone 5 — Production-readiness validation
- Production-readiness checklist
- Security review
- Operational runbook
- **Exit criteria:** All P0/P1 items verified; documented limitations; no critical security defect.

### Milestone 6 — Phase 2 dynamic trust and BCSE (P3.1–P3.3)
- Full BCSE engine
- Predictive trajectory engine
- Framework adapters
- **Exit criteria:** Phase 2 acceptance criteria met; H3 and H4 become evaluable.

---

## Acceptance Criteria for "Implementation Complete"

The project may be reported as "implementation complete" (distinct from "production-ready" or "research-validated") only when:

1. All P0 items are resolved.
2. All P1 items are resolved OR explicitly deferred with documentation.
3. `tasks.md` matches the actual evidence (no overclaimed `[x]`).
4. The full test suite passes (target: ≥95 tests after P1 additions).
5. `reproduce.sh` produces a COMPLETE evaluation report.
6. The dashboard builds and starts.
7. Dependency declaration matches the installed environment.

"Production-ready" additionally requires:
- All P2 items resolved or documented as limitations.
- AWS architecture reviewed and approved.
- Security review complete.
- Operational runbook complete.

"Research-validated" additionally requires:
- H1–H4 evaluation with ≥5 scenarios and ≥5 runs each.
- Statistical significance reported with effect sizes.
- Phase 2 BCSE and predictive engines implemented (H3, H4).

---

## Reconciliation with tasks.md

The `tasks.md` file currently marks all 47 tasks `[x]`. The evidence shows this is overstated. After Stage 2 work, `tasks.md` should be updated to reflect:

- `[x]` for VALIDATED and TESTED tasks (36 tasks)
- `[ ]` with a `BLOCKED:` note for T1.2, T13.1, T13.2, T13.3 (4 tasks)
- `[ ]` with a `DEFERRED:` note for T4.3, T5.2, T13.4 (3 tasks — intentional Phase 2)
- `[ ]` with an `IMPLEMENTED_NOT_TESTED:` note for T8.4, T8.5, T9.2 (3 tasks; T9.2 becomes TESTED after P0.5)
- `[x]` for T13.4 once the dashboard builds (the placeholder page itself is correct; only the build is blocked)

This reconciliation will be applied in Stage 2 after the P0 fixes are implemented and verified, not during Stage 1.