# Varynx — Evaluation Protocol

**Document:** T11.2 Evaluation Protocol  
**Status:** Phase 1 — Protocol defined prior to experimental execution  
**Research Integrity:** No results are pre-claimed. Hypotheses are prospectively registered.

---

## 1. Scope

This document defines the exact procedure for executing Varynx evaluation runs, computing metrics, comparing against baselines, and reporting results in a reproducible manner.

---

## 2. Prerequisites

```bash
# Environment setup
cd C:\Users\cathe\OneDrive\Desktop\varynx
.venv\Scripts\activate          # Windows
# or: source .venv/bin/activate  # Linux/macOS

# Verify installation
python -c "import varynx; print(varynx.__version__)"
python -m pytest tests/ -q      # All tests must pass
```

---

## 3. Scenario Execution Protocol

### 3.1 Single Scenario Run

```bash
python -c "
from varynx.engine.pipeline import VarynxPipeline
from varynx.evaluation.runner import ScenarioRunner
pipeline = VarynxPipeline()
runner = ScenarioRunner(pipeline=pipeline, scenarios_dir='scenarios')
result = runner.run_named('authz_bypass_detection', seed=42)
import json; print(json.dumps(result, indent=2, default=str))
"
```

### 3.2 Full Evaluation Run (all scenarios)

```bash
python -c "
from varynx.engine.pipeline import VarynxPipeline
from varynx.evaluation.runner import ScenarioRunner
from varynx.evaluation.analysis import EvaluationReport
from uuid import uuid4
pipeline = VarynxPipeline()
runner = ScenarioRunner(pipeline=pipeline)
results = runner.run_all(seed=42, min_runs=5)
report = EvaluationReport(run_id=str(uuid4()), scenario_results=results.get('results', []))
path = report.save('output')
print(f'Report saved: {path}')
"
```

### 3.3 Baseline Comparison

```bash
python -c "
from varynx.evaluation.baselines import BaselineB1AlwaysPermit, BaselineB2SingleDimension, BaselineB3SessionAverage
from varynx.evaluation.analysis import BaselineComparator
# Run against scenarios and compare
# See evaluation/analysis.py BaselineComparator.compare() for API
"
```

---

## 4. Ablation Protocol

Edit `config/evaluation_config.yaml` to disable individual detectors:

```yaml
ablation:
  enable_capability_escalation: false   # Disable one detector
  enable_resource_anomaly: true
  # ... etc
```

Run evaluation with the modified config. Record results separately for each ablation condition.

---

## 5. Minimum Run Requirements

- Minimum 5 runs required for statistical reporting (REQ-026.6)
- Reports with fewer runs are marked `INCOMPLETE`
- Run with the same seed for reproducibility; vary seed across runs for variance estimation

---

## 6. Metrics Recording

All metrics are recorded from pipeline output. Prohibited operations:

| Prohibited | Reason |
|-----------|--------|
| Manual metric adjustment | REQ-015.8: no metric fabrication |
| Threshold tuning post-evaluation | REQ-025.6: no annotation modification |
| Reporting unaggregated results as CI | REQ-026 |
| Claiming Phase 2 BCSE/predictive results | Components are Phase 1 stubs |

---

## 7. Reporting Standards

Each evaluation report must include:
- Run ID (UUID)
- Timestamp
- Scenario names and versions
- Configuration snapshot (excluding secrets)
- Per-run metrics (precision, recall, F1)
- Aggregated metrics (mean, std, 95% CI)
- Status: COMPLETE (≥5 runs) or INCOMPLETE (<5 runs)
- Research notes citing applicable REQ-015, REQ-026 constraints

---

## 8. Limitations at Phase 1

| Limitation | Impact |
|-----------|--------|
| Synthetic scenarios only | H1–H4 cannot be generalized to production traffic |
| Phase 1 BCSE stub | H3 requires Phase 2 engine |
| Phase 1 predictive stub | Trajectory-based claims not evaluable |
| No TimescaleDB in test environment | DB-level performance benchmarks blocked |
| Performance SLAs unverified | T12.4 benchmarks pending execution |