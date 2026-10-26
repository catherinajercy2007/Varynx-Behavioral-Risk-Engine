"""Statistical Analysis and Reporting.

Computes hypothesis test results, effect sizes, and structured evaluation reports.

Satisfies: REQ-026, H1-H4
"""
from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime
from typing import Any

from varynx.evaluation.metrics import (
    MetricsComputer,
    cohens_d,
)


class EvaluationReport:
    """Structured evaluation report with statistical summaries.

    Satisfies: REQ-026
    """

    def __init__(
        self,
        run_id: str,
        scenario_results: list[dict],
        baseline_results: dict | None = None,
        config_snapshot: dict | None = None,
    ) -> None:
        self.run_id = run_id
        self.scenario_results = scenario_results
        self.baseline_results = baseline_results or {}
        self.config_snapshot = config_snapshot or {}
        self.timestamp = datetime.now(UTC).isoformat()

    def build(self) -> dict:
        """Build the complete evaluation report."""
        aggregated = MetricsComputer.aggregate_runs(self.scenario_results)
        n_runs = len(self.scenario_results)
        min_runs = 5

        report: dict[str, Any] = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "status": "COMPLETE" if n_runs >= min_runs else "INCOMPLETE",
            "n_scenarios": n_runs,
            "min_runs_required": min_runs,
            "aggregated_metrics": aggregated,
            "scenarios": self.scenario_results,
            "baselines": self.baseline_results,
            "config_snapshot": self.config_snapshot,
            "research_notes": [
                "All metrics are derived exclusively from pipeline outputs on real scenario inputs.",
                "No interpolation, smoothing, or manual adjustment applied (REQ-015.8).",
                "Thresholds and formulas require empirical calibration (REQ-024, REQ-026).",
                "Hypotheses H1-H4 cannot be confirmed or rejected without sufficient scenario coverage.",
            ],
        }

        if n_runs < min_runs:
            report["incomplete_reason"] = (
                f"Fewer than {min_runs} runs completed ({n_runs}). "
                "Report marked INCOMPLETE per REQ-026.6."
            )

        return report

    def save(self, output_dir: str = "output") -> pathlib.Path:
        """Save report to JSON file."""
        out = pathlib.Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"eval_{self.run_id}.json"
        path.write_text(json.dumps(self.build(), indent=2, default=str))
        return path


class BaselineComparator:
    """Compares Varynx detection performance against B1-B3 baselines.

    Satisfies: REQ-015 (H1 evaluation support)
    """

    @staticmethod
    def compare(
        varynx_results: list[dict],
        b1_results: list[dict],
        b2_results: list[dict],
        b3_results: list[dict] | None = None,
    ) -> dict:
        """Compute F1 comparison across Varynx and baselines.

        NOTE: Results are computed from actual data. No pre-claimed results.
        """
        varynx_agg = MetricsComputer.aggregate_runs(varynx_results)
        b1_agg = MetricsComputer.aggregate_runs(b1_results)
        b2_agg = MetricsComputer.aggregate_runs(b2_results)

        varynx_f1s = [r["metrics"]["f1_score"] for r in varynx_results if "metrics" in r]
        b1_f1s = [r["metrics"]["f1_score"] for r in b1_results if "metrics" in r]
        b2_f1s = [r["metrics"]["f1_score"] for r in b2_results if "metrics" in r]

        result: dict[str, Any] = {
            "varynx": varynx_agg,
            "B1_always_permit": b1_agg,
            "B2_single_dimension": b2_agg,
            "effect_sizes": {
                "varynx_vs_B1": cohens_d(varynx_f1s, b1_f1s),
                "varynx_vs_B2": cohens_d(varynx_f1s, b2_f1s),
            },
            "note": (
                "H1 (Varynx F1 > baselines) cannot be confirmed or rejected "
                "without sufficient scenario coverage with ground-truth annotations."
            ),
        }

        if b3_results:
            b3_agg = MetricsComputer.aggregate_runs(b3_results)
            b3_f1s = [r["metrics"]["f1_score"] for r in b3_results if "metrics" in r]
            result["B3_session_average"] = b3_agg
            result["effect_sizes"]["varynx_vs_B3"] = cohens_d(varynx_f1s, b3_f1s)

        return result
