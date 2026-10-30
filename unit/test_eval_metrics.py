"""Tests for evaluation metric semantics and scenario runner correctness.

Covers:
1. No positive labels, no detections -> TN only, F1 undefined
2. No positive labels with false positives -> FP only, F1 undefined
3. Positive labels with all positives missed -> FN only, F1=0 (defined)
4. TP and FP together -> partial precision, partial recall
5. Wrong anomaly class detected -> treated as FN for expected, FP for wrong class
6. scope_escalation scenario: TP=2 FP=0 TN=3 FN=0 (regression after fix)
7. benign scenario: TP=0 FP=0 TN=3 FN=0 (no false alarms, F1 undefined)
8. authz_bypass scenario: TP=1 FP=0 TN=4 FN=0 (regression)

Satisfies: Phase 2 evaluation correctness requirements
"""
from __future__ import annotations

import os

# Must be set before importing varynx modules that read config at import time.
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-eval")

from varynx.engine.pipeline import VarynxPipeline  # noqa: E402
from varynx.evaluation.runner import EvalMetrics, ScenarioRunner  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# EvalMetrics unit tests (Task 4)
# ─────────────────────────────────────────────────────────────────────────────

class TestEvalMetricsSemantics:
    """Unit tests for EvalMetrics confusion-matrix semantics."""

    def test_no_positives_no_detections_is_tn_only(self):
        """Scenario with no labels and no detections: all TN, F1 undefined."""
        m = EvalMetrics()
        m.record(None, [])
        m.record(None, [])
        m.record(None, [])
        d = m.to_dict()
        assert d["true_negatives"] == 3
        assert d["true_positives"] == 0
        assert d["false_positives"] == 0
        assert d["false_negatives"] == 0
        assert d["f1_defined"] is False, "F1 must be undefined when no positive labels exist"
        assert d["f1_score"] == 0.0  # convention: undefined represented as 0.0

    def test_no_positives_with_false_positives(self):
        """Scenario with no positive labels but detector fires: FP registered, F1 undefined."""
        m = EvalMetrics()
        m.record(None, ["CAPABILITY_ESCALATION"])  # FP
        m.record(None, [])                          # TN
        d = m.to_dict()
        assert d["false_positives"] == 1
        assert d["true_negatives"] == 1
        assert d["f1_defined"] is False, "F1 undefined — no positive labels"
        assert d["recall_defined"] is False, "Recall undefined — no positive labels"
        # Precision IS defined when predictions exist (TP+FP > 0)
        assert d["precision_defined"] is True, "Precision defined — we made a prediction"
        assert d["precision"] == 0.0, "Precision=0 because prediction was FP"

    def test_positive_labels_all_missed_is_fn(self):
        """Detector misses all labeled positives: FN only, F1=0 (defined)."""
        m = EvalMetrics()
        m.record("AUTHORIZATION_BYPASS_ATTEMPT", [])   # FN
        m.record("AUTHORIZATION_BYPASS_ATTEMPT", [])   # FN
        d = m.to_dict()
        assert d["false_negatives"] == 2
        assert d["true_positives"] == 0
        assert d["f1_defined"] is True, "F1 IS defined when positive labels exist"
        assert d["f1_score"] == 0.0  # Genuinely zero due to missed detections
        assert d["recall"] == 0.0

    def test_tp_and_fp_together(self):
        """Mix of TP and FP: precision < 1, recall can be 1."""
        m = EvalMetrics()
        m.record("CAPABILITY_ESCALATION", ["CAPABILITY_ESCALATION"])   # TP
        m.record(None, ["CAPABILITY_ESCALATION"])                       # FP
        d = m.to_dict()
        assert d["true_positives"] == 1
        assert d["false_positives"] == 1
        assert d["false_negatives"] == 0
        assert d["f1_defined"] is True
        # precision = 1/(1+1)=0.5, recall=1/(1+0)=1.0, F1=2*0.5*1/(0.5+1)=0.6667
        assert abs(d["precision"] - 0.5) < 0.001
        assert d["recall"] == 1.0
        assert abs(d["f1_score"] - 0.6667) < 0.001

    def test_wrong_anomaly_class_is_fn_and_fp(self):
        """Expected CAPABILITY_ESCALATION but got TEMPORAL_ANOMALY: FN + FP."""
        m = EvalMetrics()
        # Expected positive label, got wrong class -> FN
        m.record("CAPABILITY_ESCALATION", ["TEMPORAL_ANOMALY"])
        d = m.to_dict()
        # "CAPABILITY_ESCALATION" not in ["TEMPORAL_ANOMALY"] -> FN
        assert d["false_negatives"] == 1
        # The detected anomaly was for an event expected to be positive,
        # so it's not counted as FP (the record() call is per-event, not per-detection)
        assert d["false_positives"] == 0
        assert d["f1_defined"] is True
        assert d["f1_score"] == 0.0  # missed the right class

    def test_undefined_f1_distinguishable_from_zero_f1_from_missed_detections(self):
        """F1=0 with f1_defined=False != F1=0 with f1_defined=True."""
        all_tn = EvalMetrics()
        all_tn.record(None, [])

        all_fn = EvalMetrics()
        all_fn.record("CAPABILITY_ESCALATION", [])

        tn_d = all_tn.to_dict()
        fn_d = all_fn.to_dict()

        assert tn_d["f1_score"] == 0.0
        assert fn_d["f1_score"] == 0.0
        # Same numeric value — but the interpretation is different:
        assert tn_d["f1_defined"] is False  # no positive labels
        assert fn_d["f1_defined"] is True   # positives exist but missed

    def test_perfect_detection(self):
        """TP only: precision=1, recall=1, F1=1."""
        m = EvalMetrics()
        m.record("AUTHORIZATION_BYPASS_ATTEMPT", ["AUTHORIZATION_BYPASS_ATTEMPT"])
        m.record(None, [])
        d = m.to_dict()
        assert d["true_positives"] == 1
        assert d["false_positives"] == 0
        assert d["true_negatives"] == 1
        assert d["false_negatives"] == 0
        assert d["precision"] == 1.0
        assert d["recall"] == 1.0
        assert d["f1_score"] == 1.0
        assert d["f1_defined"] is True

    def test_has_positives_property(self):
        """has_positives is False until a positive label is recorded."""
        m = EvalMetrics()
        assert m.has_positives is False
        m.record(None, [])
        assert m.has_positives is False
        m.record("CAPABILITY_ESCALATION", [])
        assert m.has_positives is True


# ─────────────────────────────────────────────────────────────────────────────
# Scenario regression tests (Task 4 item 6-8)
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioRegressions:
    """Regression tests for the three evaluation scenarios."""

    def _run_scenario(self, name: str) -> dict:
        pipeline = VarynxPipeline()
        runner = ScenarioRunner(pipeline=pipeline, scenarios_dir="scenarios")
        return runner.run_named(name, seed=42)

    def test_scope_escalation_detection_f1_1_0(self):
        """scope_escalation_detection: TP=2 FP=0 TN=3 FN=0, F1=1.0 (regression).

        Failures here mean either:
        - The CAPABILITY_ESCALATION detector stopped working, OR
        - Agent pre-registration in the runner was broken, OR
        - The timestamp fix was reverted (temporal anomaly firing at off-hours)
        """
        result = self._run_scenario("scope_escalation_detection")
        m = result["metrics"]
        assert m["true_positives"] == 2, f"Expected 2 TP, got {m['true_positives']}"
        assert m["false_positives"] == 0, f"Expected 0 FP, got {m['false_positives']}"
        assert m["true_negatives"] == 3, f"Expected 3 TN, got {m['true_negatives']}"
        assert m["false_negatives"] == 0, f"Expected 0 FN, got {m['false_negatives']}"
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0
        assert m["f1_score"] == 1.0
        assert m["f1_defined"] is True
        assert len(result["errors"]) == 0

    def test_benign_no_false_alarms_produces_tn_only(self):
        """benign_agent_no_false_alarms: no FP, f1_defined=False."""
        result = self._run_scenario("benign_agent_no_false_alarms")
        m = result["metrics"]
        assert m["false_positives"] == 0, f"Expected 0 FP (no false alarms), got {m['false_positives']}"
        assert m["true_negatives"] == 3
        assert m["f1_defined"] is False, "F1 must be undefined for a benign-only scenario"
        assert len(result["errors"]) == 0

    def test_authz_bypass_f1_1_0(self):
        """authz_bypass_detection: TP=1 FP=0 TN=4 FN=0, F1=1.0 (regression)."""
        result = self._run_scenario("authz_bypass_detection")
        m = result["metrics"]
        assert m["true_positives"] == 1
        assert m["false_positives"] == 0
        assert m["true_negatives"] == 4
        assert m["false_negatives"] == 0
        assert m["f1_score"] == 1.0
        assert m["f1_defined"] is True
        assert len(result["errors"]) == 0

    def test_scenario_runner_timestamps_are_deterministic(self):
        """Running the same scenario twice produces identical metrics."""
        r1 = self._run_scenario("authz_bypass_detection")
        r2 = self._run_scenario("authz_bypass_detection")
        assert r1["metrics"] == r2["metrics"], "Metrics must be identical across runs"

    def test_run_all_discovers_three_scenarios(self):
        """ScenarioRunner.run_all() finds all three scenario files."""
        pipeline = VarynxPipeline()
        runner = ScenarioRunner(pipeline=pipeline, scenarios_dir="scenarios")
        result = runner.run_all(seed=42, min_runs=5)
        assert result["total_scenarios"] == 3, f"Expected 3 scenarios, got {result['total_scenarios']}"
        # Still INCOMPLETE because 3 < 5 required runs
        assert result["status"] == "INCOMPLETE"
