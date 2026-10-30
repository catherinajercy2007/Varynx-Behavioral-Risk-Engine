# Varynx — Behavioral Risk Control Engine

**Research Title:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents

A cloud-native behavioral risk control engine that monitors, analyzes, and responds to behavioral anomalies in autonomous AI agents. Varynx captures behavioral evidence, maintains dynamic trust profiles per agent, evaluates proposed actions via BCSE, and emits structured security recommendations to enforcement infrastructure.

## Current Status

**329 tests passing** (full suite, Python 3.13.1, verified 2025).

- BCSE Phase 2 full engine implemented: evaluates PolicyAlternatives, computes divergence scores.
- Predictive Phase 2 full engine implemented: OLS regression over TrustHistoryEntry with correct 95% CI.
- API-key authentication middleware implemented and tested.
- 12 AWS service adapters implemented (LOCAL_MODE by default; no real AWS calls without credentials).
- Live AWS integration and production deployment **not verified** — mocked tests only.
- H3/H4 hypothesis evaluation deferred: additional scenario coverage required.

---

## Setup

```powershell
# Windows PowerShell
cd C:\Users\cathe\OneDrive\Desktop\varynx
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

```bash
# Linux/macOS
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
# Full test suite (329 tests)
pytest tests/ -q

# Unit tests only
pytest tests/unit/ -v

# Property-based tests (Hypothesis)
pytest tests/property/ -v

# Integration tests
pytest tests/integration/ -v

# Performance benchmarks (records actual measurements; no hard threshold assertions)
pytest tests/benchmarks/ -v -s
```

## Running the API Server

```bash
# Required
export VARYNX_DATABASE_URL=memory://dev   # or postgresql://user:pass@host/varynx

# Authentication — local development (optional)
# Leave VARYNX_API_KEY unset. Every request is allowed; a WARNING is logged at startup.

# Authentication — protected deployment (required before any public exposure)
export VARYNX_API_KEY=your-secret-api-key   # clients must send X-API-Key: <key>
export VARYNX_REQUIRE_API_KEY=true          # startup fails if key is missing

# Start server (bind to localhost for local dev)
uvicorn varynx.api.app:app --host 127.0.0.1 --port 8000 --reload
```

> **Security note — protected deployments**: Setting `VARYNX_REQUIRE_API_KEY=true` causes
> the application to refuse to start if `VARYNX_API_KEY` is not set, preventing accidental
> unauthenticated exposure. Do not bind to `0.0.0.0` without configuring `VARYNX_API_KEY`
> and placing the application behind a TLS-terminating reverse proxy.

API documentation: http://localhost:8000/api/v1/docs

## Running the Dashboard

Requires Node.js 18+ and npm.

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:3000
# Requires VARYNX_API_URL=http://localhost:8000/api/v1
```

## Evaluation

```bash
# Run all available scenarios
python -c "
import os; os.environ['VARYNX_DATABASE_URL']='memory://eval'
from varynx.engine.pipeline import VarynxPipeline
from varynx.evaluation.runner import ScenarioRunner
runner = ScenarioRunner(VarynxPipeline(), scenarios_dir='scenarios')
results = runner.run_all(seed=42)
print(results['status'], '-', results['total_scenarios'], 'scenarios')
"
```

## Reproducibility

```bash
./reproduce.sh              # Full install + tests + evaluation + report
./reproduce.sh --skip-install --seed 42  # Skip install, use fixed seed
```

## Database Setup (PostgreSQL + TimescaleDB)

```bash
docker-compose -f docker/docker-compose.yml up -d db
export DATABASE_URL=postgresql://varynx:varynx_dev@localhost:5432/varynx
alembic upgrade head
```

## Architecture

```
REST API (FastAPI) → Ingestion → Identity Registry → Lease Manager
                  → Evidence Engine (6 detectors) → Trust Scorer
                  → BCSE (Phase 2 full engine) → Predictive (Phase 2 full engine)
                  → Adaptive Response Engine → Enforcement Layer
                  → Audit Store (SHA-256 hash chain)
                  → AWS Adapters (CloudWatch metrics, S3 exports, CloudTrail ingest)
```

## Research Integrity

- All metrics are computed from actual pipeline outputs on scenario inputs
- No performance benchmarks are pre-claimed (T12.4 measures actual in-memory performance)
- Hypotheses H1–H4 require additional scenario coverage for full evaluation
- All thresholds and scoring weights require empirical calibration

## Known Limitations

- **In-memory storage only** — no persistent PostgreSQL integration for event/trust storage
- **BCSE Phase 2** — counterfactual engine implemented; H3 evaluation requires more scenario coverage
- **Predictive Phase 2** — OLS regression engine implemented; H4 evaluation requires more scenario coverage
- **Synthetic scenarios only** — 3 scenarios available; H1–H4 require broader coverage
- **Performance benchmarks** — measured in-memory only; DB-backed performance unverified
- **Authentication** — API-key middleware implemented and tested (329 tests). Set `VARYNX_API_KEY`
  and `VARYNX_REQUIRE_API_KEY=true` for protected deployments. Local development with no key is
  intentionally permitted with a logged warning. JWT/Cognito integration is not implemented.
- **AWS integration** — 12 AWS service adapters implemented. All run in LOCAL_MODE by default;
  no real AWS calls are made without credentials. **Live AWS integration is not verified** — mocked
  tests only. See `varynx/aws/` for adapter modules.
- **Production deployment** — not verified; no ECS/Fargate tasks have been deployed.
  See `varynx/aws/github_oidc.py` for a CI/CD workflow template (OIDC, ECR, ECS).
- **TimescaleDB** — migration written but not executable without a live DB instance
- **Dashboard build** — requires Node.js 18+ and compatible Next.js version

## Directory Structure

```
varynx/           Python package (engine, models, api, evaluation, aws, config)
tests/            pytest suite (unit, property, integration, benchmarks)
scenarios/        YAML scenario files for evaluation
config/           Policy and threshold YAML files
docs/             Research methodology, evaluation protocol, API reference
dashboard/        Next.js 14 analyst dashboard
docker/           Dockerfile + docker-compose.yml
alembic/          Database migrations (9-table schema)
```