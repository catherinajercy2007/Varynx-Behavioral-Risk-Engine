"""Scenario Runner — loads YAML scenario files and executes them against the pipeline.

Satisfies: REQ-015, REQ-025
"""
from __future__ import annotations

import logging
import pathlib
import time
from datetime import UTC, datetime
from uuid import uuid4

import yaml

from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import AgentActionEvent

logger = logging.getLogger(__name__)


class ScenarioValidationError(Exception):
    """Raised when a scenario YAML fails validation."""
    reason_code = "SCENARIO_VALIDATION_FAILED"


class ScenarioEvent:
    """A single event definition from a scenario file."""
    def __init__(self, data: dict) -> None:
        self.agent_id: str = data["agent_id"]
        self.action_type: str = data["action_type"]
        self.capability_requested: str = data.get("capability_requested", "default")
        self.target_resource: str = data.get("target_resource", "/default")
        self.authorization_result: str = data.get("authorization_result", "allowed")
        self.task_id: str | None = data.get("task_id")
        self.expected_anomaly: str | None = data.get("expected_anomaly")
        self.expected_response: str | None = data.get("expected_response")
        self.timestamp_offset_seconds: float = data.get("timestamp_offset_seconds", 0.0)
        self.metadata: dict = data.get("metadata", {})


class ScenarioFile:
    """Parsed scenario YAML."""
    def __init__(self, data: dict, path: pathlib.Path) -> None:
        self.name: str = data.get("name", path.stem)
        self.description: str = data.get("description", "")
        self.version: str = str(data.get("version", "1.0"))
        self.is_simulated: bool = data.get("is_simulated", True)
        self.events: list[ScenarioEvent] = [ScenarioEvent(e) for e in data.get("events", [])]
        self.ground_truth: dict = data.get("ground_truth", {})
        self.path = path


def load_scenario(path: pathlib.Path) -> ScenarioFile:
    """Load and validate a scenario YAML file. Raises ScenarioValidationError on failure."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        raise ScenarioValidationError(f"Cannot parse scenario {path}: {exc}")
    if not isinstance(data, dict):
        raise ScenarioValidationError(f"Scenario {path} must be a YAML mapping")
    if "events" not in data:
        raise ScenarioValidationError(f"Scenario {path} missing required 'events' key")
    return ScenarioFile(data, path)


class EvalMetrics:
    """Computes detection metrics from scenario run results."""

    def __init__(self) -> None:
        self.tp = self.fp = self.tn = self.fn = 0

    def record(self, expected_anomaly: str | None, detected_anomalies: list[str]) -> None:
        if expected_anomaly:
            if expected_anomaly in detected_anomalies:
                self.tp += 1
            else:
                self.fn += 1
        else:
            if detected_anomalies:
                self.fp += 1
            else:
                self.tn += 1

    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "true_positives": self.tp,
            "false_positives": self.fp,
            "true_negatives": self.tn,
            "false_negatives": self.fn,
            "precision": round(self.precision(), 4),
            "recall": round(self.recall(), 4),
            "f1_score": round(self.f1(), 4),
        }


class ScenarioRunner:
    """Executes evaluation scenarios against the Varynx pipeline.

    Satisfies: REQ-015, REQ-025
    """

    def __init__(
        self,
        pipeline: VarynxPipeline | None = None,
        scenarios_dir: str = "scenarios",
    ) -> None:
        self.pipeline = pipeline or VarynxPipeline()
        self.scenarios_dir = pathlib.Path(scenarios_dir)

    def run(self, scenario: ScenarioFile, seed: int = 42) -> dict:
        """Execute a single scenario and return results dict."""
        metrics = EvalMetrics()
        run_id = str(uuid4())
        start_time = time.monotonic()
        events_processed = 0
        errors = []
        mismatches = []

        base_time = datetime.now(UTC)
        session_id = uuid4()

        for i, se in enumerate(scenario.events):
            from datetime import timedelta
            ts = base_time.replace(microsecond=0)
            if se.timestamp_offset_seconds:
                ts = base_time + timedelta(seconds=se.timestamp_offset_seconds)

            try:
                event = AgentActionEvent.model_validate({
                    "agent_id": se.agent_id,
                    "session_id": str(session_id),
                    "timestamp": ts.isoformat(),
                    "action_type": se.action_type,
                    "capability_requested": se.capability_requested,
                    "target_resource": se.target_resource,
                    "authorization_result": se.authorization_result,
                    "is_simulated": scenario.is_simulated,
                    "task_id": se.task_id,
                }, strict=False)
            except Exception as exc:
                errors.append({"event_index": i, "error": f"SCHEMA_INVALID: {exc}"})
                continue

            result = self.pipeline.process_event(
                event,
                action_id=f"scenario-{run_id}-{i}",
                skip_timestamp_check=True,
            )

            if result.error:
                errors.append({"event_index": i, "error": result.error})
                continue

            events_processed += 1
            metrics.record(se.expected_anomaly, result.anomalies_detected)

            if se.expected_response and result.recommendation:
                actual = result.recommendation.response_type.value
                if actual != se.expected_response:
                    mismatches.append({
                        "event_index": i,
                        "expected": se.expected_response,
                        "actual": actual,
                        "reason": "SCENARIO_EXPECTATION_MISMATCH",
                    })

        elapsed = time.monotonic() - start_time
        return {
            "run_id": run_id,
            "scenario": scenario.name,
            "scenario_version": scenario.version,
            "seed": seed,
            "events_total": len(scenario.events),
            "events_processed": events_processed,
            "errors": errors,
            "mismatches": mismatches,
            "metrics": metrics.to_dict(),
            "elapsed_seconds": round(elapsed, 4),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def run_named(self, name: str, seed: int = 42) -> dict:
        """Run a named scenario from the scenarios directory."""
        candidates = list(self.scenarios_dir.glob(f"{name}.yaml")) + \
                     list(self.scenarios_dir.glob(f"{name}.yml"))
        if not candidates:
            raise FileNotFoundError(f"Scenario '{name}' not found in {self.scenarios_dir}")
        scenario = load_scenario(candidates[0])
        return self.run(scenario, seed=seed)

    def run_all(self, seed: int = 42, min_runs: int = 5) -> dict:
        """Run all scenarios in the directory. Returns aggregated report."""
        results = []
        files = list(self.scenarios_dir.glob("*.yaml")) + list(self.scenarios_dir.glob("*.yml"))

        if not files:
            return {
                "status": "NO_SCENARIOS",
                "message": f"No scenario files found in {self.scenarios_dir}",
                "scenarios_dir": str(self.scenarios_dir),
            }

        for f in sorted(files):
            try:
                scenario = load_scenario(f)
                result = self.run(scenario, seed=seed)
                results.append(result)
            except ScenarioValidationError as exc:
                results.append({"scenario": f.stem, "error": str(exc), "skipped": True})

        return {
            "status": "COMPLETE" if len(results) >= min_runs else "INCOMPLETE",
            "total_scenarios": len(results),
            "min_runs": min_runs,
            "results": results,
            "timestamp": datetime.now(UTC).isoformat(),
        }
