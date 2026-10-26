#!/usr/bin/env bash
# reproduce.sh — Varynx full reproducibility script
# Satisfies: T12.3, REQ-027.6, NFR-REP-002
#
# This script installs dependencies, runs all tests, executes evaluation
# scenarios, and produces evaluation reports in output/.
# Any reviewer can run this script to reproduce the evaluation results.
#
# Usage:
#   ./reproduce.sh [--skip-install] [--seed <int>] [--scenarios-dir <path>]
#
# Requirements:
#   - Python 3.11+
#   - pip
#   - bash

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
SEED=42
SCENARIOS_DIR="scenarios"
SKIP_INSTALL=false
PYTHON="${PYTHON:-python}"
OUTPUT_DIR="output"

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-install) SKIP_INSTALL=true; shift ;;
    --seed) SEED="$2"; shift 2 ;;
    --scenarios-dir) SCENARIOS_DIR="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Environment check
# ──────────────────────────────────────────────────────────────────────────────
echo "=== Varynx Reproducibility Script ==="
echo "Python: $($PYTHON --version)"
echo "Seed: $SEED"
echo "Scenarios: $SCENARIOS_DIR"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Install dependencies
# ──────────────────────────────────────────────────────────────────────────────
if [ "$SKIP_INSTALL" = false ]; then
  echo "=== Installing dependencies ==="
  $PYTHON -m pip install -e ".[dev]" --quiet
  echo "Dependencies installed."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 3: Verify package import
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Verifying package ==="
$PYTHON -c "import varynx; print(f'varynx {varynx.__version__} OK')"

# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Run test suite
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Running test suite ==="
$PYTHON -m pytest tests/ -q --tb=short
echo "Test suite complete."

# ──────────────────────────────────────────────────────────────────────────────
# Step 5: Run evaluation scenarios
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Running evaluation scenarios ==="
mkdir -p "$OUTPUT_DIR"

EVAL_SCRIPT=$(cat <<'PYEOF'
import sys, os, json, pathlib
from uuid import uuid4

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://reproduce")
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
scenarios_dir = sys.argv[2] if len(sys.argv) > 2 else "scenarios"
output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"

from varynx.engine.pipeline import VarynxPipeline
from varynx.evaluation.runner import ScenarioRunner
from varynx.evaluation.analysis import EvaluationReport

pipeline = VarynxPipeline()
runner = ScenarioRunner(pipeline=pipeline, scenarios_dir=scenarios_dir)
results = runner.run_all(seed=seed, min_runs=5)

run_id = str(uuid4())[:8]
report = EvaluationReport(
    run_id=run_id,
    scenario_results=results.get("results", []),
    config_snapshot={
        "seed": seed,
        "scenarios_dir": scenarios_dir,
        "varynx_version": "0.1.0",
    }
)
path = report.save(output_dir)
print(f"Report saved: {path}")
print(f"Status: {results.get('status', 'UNKNOWN')}")
print(f"Scenarios run: {results.get('total_scenarios', 0)}")

# Print summary metrics
for r in results.get("results", []):
    if "metrics" in r:
        m = r["metrics"]
        print(f"  {r['scenario']}: F1={m['f1_score']:.4f} P={m['precision']:.4f} R={m['recall']:.4f}")
    elif r.get("skipped"):
        print(f"  {r['scenario']}: SKIPPED ({r.get('error', '')})")
PYEOF
)

$PYTHON -c "$EVAL_SCRIPT" "$SEED" "$SCENARIOS_DIR" "$OUTPUT_DIR"
echo "Evaluation complete."

# ──────────────────────────────────────────────────────────────────────────────
# Step 6: Verify hash chain integrity
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Verifying audit integrity ==="
$PYTHON -c "
import os
os.environ.setdefault('VARYNX_DATABASE_URL', 'memory://verify')
from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
from datetime import datetime, timezone
from uuid import uuid4

p = VarynxPipeline()
for i in range(3):
    e = AgentActionEvent.model_validate({
        'agent_id': 'verify-agent', 'session_id': str(uuid4()),
        'timestamp': str(datetime.now(timezone.utc)), 'action_type': 'READ',
        'capability_requested': 'read', 'target_resource': '/data',
        'authorization_result': 'allowed', 'is_simulated': True,
    }, strict=False)
    p.process_event(e, action_id=f'verify-{i}', skip_timestamp_check=True)

valid, violations = p.audit_store.verify_chain()
print(f'Audit chain valid: {valid}')
if violations:
    print(f'Violations: {violations}')
    sys.exit(1)
"
echo "Audit integrity: OK"

# ──────────────────────────────────────────────────────────────────────────────
# Step 7: Summary
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Reproduction Complete ==="
echo "Output reports: $OUTPUT_DIR/"
echo ""
echo "Research integrity notes:"
echo "  - All metrics are derived from pipeline outputs on scenario inputs."
echo "  - No interpolation or fabrication was applied."
echo "  - BCSE and predictive components are Phase 1 stubs."
echo "  - Performance benchmarks (NFR-PERF-001 through NFR-PERF-003) are not yet measured."
echo "  - H1-H4 require Phase 2 components and more scenario coverage for full evaluation."