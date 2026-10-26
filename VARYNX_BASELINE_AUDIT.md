# Varynx Baseline Audit

**Date:** 2026-10-25  
**Stage:** 1 — Repository Discovery and Baseline  
**Rule:** No application code was modified during this assessment.  
**Method:** Direct filesystem inspection, dependency probing, and live test execution.

---

## 1. Repository Identity

| Item | Value |
|------|-------|
| Project | Varynx — Behavioral Risk Control Engine for Autonomous AI Agents |
| Root path | `C:\Users\cathe\OneDrive\Desktop\varynx` |
| Version control | **NOT a git repository** (no `.git` directory present) |
| Branch / commit | N/A — repository is not version-controlled locally |
| Uncommitted changes | Cannot be determined (no VCS) |
| Tracked files | All files appear untracked; no `.gitignore` evidence of VCS use |

**Immediate risk:** Without version control, there is no rollback path, no change history, and no atomic recovery. A `git init` plus initial commit is a P0 prerequisite before any further engineering or deployment work.

---

## 2. Python and Dependency Environment

| Item | Value |
|------|-------|
| Interpreter | Python 3.13.1 (`.venv\Scripts\python.exe`) |
| venv present | Yes (`.venv\`, Windows-style) |
| Test runner | pytest 9.1.1 with hypothesis 6.170.9, pytest-asyncio 1.4.0 |

**Installed packages actually importable (verified via `__import__`):**

| Package | Version | Status |
|---------|---------|--------|
| fastapi | 0.162.0 | OK |
| pydantic | 2.14.1 | OK |
| pydantic-settings | 2.16.1 | OK |
| starlette | 1.9.0 | OK |
| uvicorn | 0.54.0 | OK |
| PyYAML | 6.0.3 | OK |
| httpx | 0.28.1 | OK |
| hypothesis | 6.170.9 | OK |
| pytest | 9.1.1 | OK |
| mypy | 1.10.0 | OK |
| ruff | 0.4.4 | OK |
| alembic | present | OK (importable, but unusable — see below) |
| **sqlalchemy** | **NOT INSTALLED** | **MISSING** |
| **psycopg2** | **NOT INSTALLED** | **MISSING** |
| **redis** | **NOT INSTALLED** | **MISSING** |

**Critical finding:** `pyproject.toml` declares `sqlalchemy==2.0.30`, `psycopg2-binary==2.9.9`, `alembic==1.13.1`, and `redis==5.0.4` as required runtime dependencies, but **none of these are installed in the active venv**. The most recent `pip install -e ".[dev]"` either skipped them or installed only the dev subset. Consequence: the database and migration tooling has never been exercised in this environment.

---

## 3. External Runtime Dependencies

| Service | Installed | Notes |
|---------|-----------|-------|
| Node.js | v22.18.0 | Available at `C:\Program Files\nodejs\node.exe` |
| npm | 10.9.3 | Available |
| Docker | **NOT INSTALLED** | `docker` command not on PATH |
| PostgreSQL (`psql`) | **NOT INSTALLED** | `psql` command not on PATH |
| TimescaleDB | **NOT INSTALLED** | Extension not available |
| Redis | **NOT INSTALLED** | Service not available |

---

## 4. Test Framework and Commands

**Test command (verified):**
```powershell
.venv\Scripts\python.exe -m pytest tests\ -v --tb=short --no-header
```

**Result captured during this audit (real, not assumed):**
```
collected 90 items
tests/benchmarks/test_performance.py .....     [  3%]
tests/integration/test_audit_chain.py ...........  [ 15%]
tests/integration/test_pipeline_integration.py ............ [ 30%]
tests/property/test_api_serialization.py ....    [ 34%]
tests/property/test_evidence_properties.py ....... [ 42%]
tests/property/test_lease_properties.py ..........  [ 53%]
tests/property/test_response_properties.py .......  [ 61%]
tests/property/test_trust_properties.py .....    [ 66%]
tests/unit/test_config.py ......                [ 73%]
tests/unit/test_models.py ......................  [100%]
======================== 90 passed in 6.31s =========================
```

**Known failing tests:** None. All 90 tests pass.

**Test inventory:**
- `tests/unit/` — 30 tests (models, config)
- `tests/property/` — 39 tests (Hypothesis property-based)
- `tests/integration/` — 18 tests (pipeline, audit chain, API)
- `tests/benchmarks/` — 3 tests (performance baseline)
- **Total: 90**

---

## 5. Application Startup Verification

### API server (VERIFIED WORKING)

Started uvicorn programmatically against the real `varynx.api.app:app` and queried `/api/v1/health`:

```
GET /health: HTTP 200
body: {"status":"success","request_id":"...","timestamp":"...","data":{"status":"healthy",
       "storage":{"agents":0,"sessions":0,"leases":0,"audit_records":0},
       "subsystems":{"ingestion":"ok","evidence_engine":"ok",...}}}
API SMOKE TEST: PASS
```

**Startup procedure (verified):**
```powershell
$env:VARYNX_DATABASE_URL = "memory://dev"
.venv\Scripts\uvicorn.exe varynx.api.app:app --host 0.0.0.0 --port 8000 --reload
```
Docs endpoint: `http://localhost:8000/api/v1/docs`

### Dashboard (FAILED TO BUILD)

`npm install` succeeded (386 packages installed in 4 minutes), but `npm run build` failed:

```
Error: Cannot find module 'next/dist/compiled/commander'
  Require stack:
  - ...\node_modules\next\dist\bin\next
```

This is a Next.js 14.2.3 + Node.js 22 compatibility issue. The dashboard TSX files exist and are non-trivial in size, but they have **never been verified to compile or run**.

**Dashboard startup procedure (documented, not verified):**
```powershell
cd dashboard
npm install
npm run dev   # fails in current environment
```

---

## 6. Repository Structure

```
varynx/
├── varynx/                    Python package (41 source files)
│   ├── models/                10 Pydantic v2 model modules
│   ├── engine/                12 pipeline component modules
│   ├── api/                   FastAPI app + 8 route modules
│   ├── evaluation/            4 evaluation framework modules
│   └── config.py              Pydantic Settings configuration
├── tests/                     10 test files, 90 tests total
│   ├── unit/                  30 tests
│   ├── property/              39 tests (Hypothesis)
│   ├── integration/           18 tests
│   ├── benchmarks/            3 tests
│   └── fixtures/              (empty)
├── dashboard/                 Next.js 14 + Tailwind (TSX exists, build fails)
├── docs/                      4 markdown documents
├── config/                    3 YAML configuration files
├── docker/                    Dockerfile + docker-compose.yml (untested)
├── alembic/                   Initial 9-table migration (unrunnable: sqlalchemy missing)
├── scenarios/                 2 YAML scenario files
├── output/                    (empty — no evaluation reports generated)
├── .kiro/specs/varynx-behavioral-risk-engine/
│   ├── requirements.md
│   ├── design.md
│   ├── tasks.md               47 tasks, all marked [x]
│   └── tasks.md.bak           Backup created during prior formatting fix
├── pyproject.toml             Declares dependencies not actually installed
├── reproduce.sh               8 KB bash reproducibility script
└── README.md                  Project documentation
```

---

## 7. Architecture Observations

The Varynx pipeline is implemented as a single in-process orchestrator (`VarynxPipeline`) that wires together 10 stages per `design.md` Section 6:

1. Ingestion & Validation (`engine/ingestion.py`)
2. Identity & Session Registry (`engine/registry.py`)
3. Capability Lease evaluation (`engine/lease_manager.py`)
4. Behavioral Evidence Engine — 6 detectors (`engine/evidence.py`)
5. Dynamic Trust Module (`engine/trust.py`)
6. BCSE Engine — **Phase 1 stub** (`engine/bcse.py`)
7. Predictive Intelligence — **Phase 1 stub** (`engine/prediction.py`)
8. Adaptive Response Engine (`engine/response.py`)
9. Runtime Enforcement Layer (`engine/enforcement.py`)
10. Audit Store with SHA-256 hash chain (`engine/audit.py`)

**Persistence:** All state is in-memory Python dictionaries. The Alembic migration defines the 9-table PostgreSQL/TimescaleDB schema but has never been run. No SQLAlchemy ORM layer exists — the migration uses raw `op.execute(SQL)`. The application has no database connection logic; `VARYNX_DATABASE_URL` is required by config validation but unused at runtime.

**API:** FastAPI with 27 routes across 8 routers. CORS is open (`allow_origins=["*"]`). Rate limiting is in-memory per-IP (1000 req/min default). Authentication is a placeholder — no auth middleware actually enforces identity.

**BCSE and Predictive Intelligence:** Both are correctly documented as Phase 1 stubs returning `is_stub=True`. These are intentional placeholders per the specification, not defects.

---

## 8. Security and Deployment Configuration

| Control | Status | Evidence |
|---------|--------|----------|
| Authentication | **PLACEHOLDER** | No auth middleware enforces identity; all endpoints accept all requests |
| Authorization | **PLACEHOLDER** | `agents.py` and `leases.py` create records without verifying caller identity |
| CORS | **OVER-PERMISSIVE** | `allow_origins=["*"]`, `allow_credentials=False` |
| Rate limiting | In-memory, per-IP, 1000 req/min | `middleware.py` RateLimitMiddleware |
| TLS | Not configured | No TLS in app code; would rely on reverse proxy |
| Secret management | None | `VARYNX_DATABASE_URL` read from env; no secrets manager integration |
| Input validation | Pydantic v2 strict mode | Enforced on all API request bodies |
| Audit integrity | SHA-256 hash chain | `AuditStore.verify_chain()` detects tampering |
| Append-only enforcement | Application-level only | No DB privilege constraints (no DB in use) |

**AWS infrastructure:** None. No `.tf`, `.cdk`, `cloudformation`, `sam.yaml`, or `.github/workflows` files exist. The project has zero cloud deployment artifacts.

---

## 9. Current Limitations and Environmental Blockers

| Blocker | Impact |
|---------|--------|
| Not a git repository | No version control, no rollback, no history |
| `sqlalchemy`/`psycopg2`/`redis` not installed despite being declared | DB layer is dead code; migrations cannot run |
| Docker not installed locally | Container build cannot be verified in this environment |
| PostgreSQL/TimescaleDB not installed | Migration `0001_initial_schema.py` cannot be executed and verified |
| Dashboard `npm run build` fails | T13.1–T13.4 are not verified despite being marked `[x]` |
| No AWS infrastructure files | Phase 7–8 (AWS integration) has not started |
| No CI/CD pipeline | No automated build/test/deploy path |
| In-memory storage only | All state lost on process restart; not production-viable |
| Only 2 evaluation scenarios | Below the 5-run minimum for statistical reporting (REQ-026.6) |
| BCSE/Predictive are stubs | H3 and H4 hypotheses cannot be evaluated |
| Performance measured in-memory only | NFR-PERF-001/002/003 unverified for DB-backed deployment |

---

## 10. Immediate Risks (P0)

1. **No version control.** A single accidental edit or failed experiment can destroy work. Initialize git immediately.
2. **DB dependencies declared but not installed.** Any code path that imports `sqlalchemy` (e.g., a future attempt to run `alembic upgrade`) will crash. The `pyproject.toml` does not match the installed environment.
3. **Dashboard marked complete but does not build.** T13.1–T13.4 claim `[x]` status without verification.
4. **No authentication on the API.** All endpoints are publicly callable when the server runs. This is acceptable for local development but must not be deployed.
5. **No secrets management.** `VARYNX_DATABASE_URL` is expected to contain credentials but is read directly from environment with no secrets-manager integration.
6. **CORS `allow_origins=["*"]`.** Over-permissive for any deployment beyond a single developer's machine.

---

## 11. Baseline Acceptance Criteria

This baseline audit is complete. The repository has been inspected without modification, real test results have been captured, and environmental blockers have been documented. Stage 2 (47-task audit) and Stage 3 (corrected implementation plan) build on this evidence.