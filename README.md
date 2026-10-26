# Varynx — Behavioral Risk Control Engine

**Research Title:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents

A cloud-native behavioral risk control engine that monitors, analyzes, and responds to behavioral anomalies in autonomous AI agents. Varynx captures behavioral evidence, maintains dynamic trust profiles per agent, evaluates proposed actions via BCSE, and emits structured security recommendations to enforcement infrastructure.

## Phase 1 MVP Status

All 47 Phase 1 tasks implemented and verified. 90 tests passing.

**Note:** BCSE and Predictive Intelligence components are Phase 1 stubs. Phase 2 will implement full counterfactual analysis and trajectory prediction.

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
# Full test suite (90 tests)
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
# Set required environment variable
export VARYNX_DATABASE_URL=postgresql://user:pass@localhost/varynx  # or memory://dev for in-memory

# Start server
uvicorn varynx.api.app:app --host 0.0.0.0 --port 8000 --reload
```

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
                  → BCSE (Phase 1 stub) → Predictive (Phase 1 stub)
                  → Adaptive Response Engine → Enforcement Layer
                  → Audit Store (SHA-256 hash chain)
```

## Research Integrity

- All metrics are computed from actual pipeline outputs on scenario inputs
- No performance benchmarks are pre-claimed (T12.4 measures actual in-memory performance)
- Hypotheses H1–H4 require Phase 2 components and more scenario coverage for full evaluation
- All thresholds and scoring weights require empirical calibration

## Known Limitations

- **In-memory storage only** — no persistent PostgreSQL integration for event/trust storage
- **BCSE Phase 1 stub** — no counterfactual analysis; H3 evaluation deferred to Phase 2
- **Predictive stub** — always returns STABLE trajectory; H4 evaluation deferred to Phase 2
- **Synthetic scenarios only** — 2 scenarios available; H1–H4 require more coverage
- **Performance benchmarks** — measured in-memory only; DB-backed performance unverified
- **Authentication** — middleware placeholder; production requires real auth
- **TimescaleDB** — migration written but not executable without a live DB instance

## Directory Structure

```
varynx/           Python package (engine, models, api, evaluation, config)
tests/            pytest suite (unit, property, integration, benchmarks)
scenarios/        YAML scenario files for evaluation
config/           Policy and threshold YAML files
docs/             Research methodology, evaluation protocol, API reference
dashboard/        Next.js 14 analyst dashboard
docker/           Dockerfile + docker-compose.yml
alembic/          Database migrations (9-table schema)
```