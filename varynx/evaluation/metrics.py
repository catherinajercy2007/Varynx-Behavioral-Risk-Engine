"""Metrics Computation — precision, recall, F1, effect sizes, CI.

Satisfies: REQ-015, REQ-026
"""
from __future__ import annotations

import math


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def confidence_interval_95(values: list[float]) -> tuple[float, float]:
    """95% CI using t-distribution approximation (z=1.96 for large n)."""
    if not values:
        return (0.0, 0.0)
    m = mean(values)
    s = std_dev(values)
    n = len(values)
    margin = 1.96 * s / math.sqrt(n) if n > 1 else 0.0
    return (round(m - margin, 4), round(m + margin, 4))


def cohens_d(group1: list[float], group2: list[float]) -> float:
    """Cohen'sd effect size between two groups."""
    if not group1 or not group2:
        return 0.0
    m1, m2 = mean(group1), mean(group2)
    s1, s2 = std_dev(group1), std_dev(group2)
    pooled = math.sqrt((s1 ** 2 + s2 ** 2) / 2)
    return (m1 - m2) / pooled if pooled > 0 else 0.0


class MetricsComputer:
    """Computes evaluation metrics from run results.

    Satisfies: REQ-015, REQ-026
    """

    @staticmethod
    def compute_detection_metrics(
        predictions: list[bool], ground_truth: list[bool]
    ) -> dict:
        """Binary classification metrics."""
        tp = sum(p and g for p, g in zip(predictions, ground_truth))
        fp = sum(p and not g for p, g in zip(predictions, ground_truth))
        tn = sum(not p and not g for p, g in zip(predictions, ground_truth))
        fn = sum(not p and g for p, g in zip(predictions, ground_truth))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / len(predictions) if predictions else 0.0

        return {
            "true_positives": tp, "false_positives": fp,
            "true_negatives": tn, "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "n": len(predictions),
        }

    @staticmethod
    def aggregate_runs(run_results: list[dict]) -> dict:
        """Compute mean, std, 95% CI across multiple evaluation runs."""
        if not run_results:
            return {"error": "No run results to aggregate"}

        f1_scores = [r["metrics"]["f1_score"] for r in run_results if "metrics" in r]
        precisions = [r["metrics"]["precision"] for r in run_results if "metrics" in r]
        recalls = [r["metrics"]["recall"] for r in run_results if "metrics" in r]

        return {
            "n_runs": len(run_results),
            "f1_score": {
                "mean": round(mean(f1_scores), 4),
                "std": round(std_dev(f1_scores), 4),
                "ci_95": confidence_interval_95(f1_scores),
            },
            "precision": {
                "mean": round(mean(precisions), 4),
                "std": round(std_dev(precisions), 4),
                "ci_95": confidence_interval_95(precisions),
            },
            "recall": {
                "mean": round(mean(recalls), 4),
                "std": round(std_dev(recalls), 4),
                "ci_95": confidence_interval_95(recalls),
            },
        }
