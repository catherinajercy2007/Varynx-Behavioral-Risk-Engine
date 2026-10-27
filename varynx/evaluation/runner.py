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
        # Optional: agent capability scope declaration for escalation scenarios.
        # When present the runner pre-registers agents with these declared capabilities
        # so the CAPABILITY_ESCALATION detector can fire correctly.
        self.agent_declared_capability_scope: list[str] = data.get(
            "agent_declared_capability_scope", []
        )


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
    """Computes detection metrics from scenario run results.

    Definedness semantics (per standard classification metric convention):

    - precision_defined: True when at least one positive prediction exists (TP+FP > 0).
      Precision = TP / (TP + FP).  If no predictions, precision is undefined (reported 0.0).

    - recall_defined: True when at least one positive ground-truth event exists (TP+FN > 0).
      Recall = TP / (TP + FN).  If no positive labels, recall is undefined (reported 0.0).

    - f1_defined: True when positive ground-truth events exist (same condition as recall).
      F1 = 2 * P * R / (P + R) when P+R > 0, else 0.0.
      F1 is always undefined when there are no positive labels, even if false positives exist.

    Distinguishing a genuine F1 = 0 (detector missed real anomalies) from an
    undefined F1 (no positive labels at all) is critical for honest evaluation.
    """

    def __init__(self) -> None:
        self.tp = self.fp = self.tn = self.fn = 0

    @property
    def precision_defined(self) -> bool:
        """True when at least one positive prediction was made (TP + FP > 0)."""
        return (self.tp + self.fp) > 0

    @property
    def recall_defined(self) -> bool:
        """True when at least one positive ground-truth label exists (TP + FN > 0)."""
        return (self.tp + self.fn) > 0

    @property
    def f1_defined(self) -> bool:
        """True when positive ground-truth labels exist (same condition as recall_defined)."""
        return self.recall_defined

    # Legacy alias kept for backward compatibility
    @property
    def has_positives(self) -> bool:
        """Alias for recall_defined / f1_defined."""
        return self.recall_defined

    def record(self, expected_anomaly: str | None, detected_anomalies: list[str]) -> None:
        """Record one event outcome into the confusion matrix.

        Args:
            expected_anomaly: The ground-truth anomaly class for this event, or None if benign.
            detected_anomalies: List of anomaly class strings actually detected by the pipeline.
        """
        if expected_anomaly:
            # Positive ground-truth event: check exact class match
            if expected_anomaly in detected_anomalies:
                self.tp += 1
            else:
                self.fn += 1   # wrong class or missed entirely
        else:
            # Negative ground-truth event
            if detected_anomalies:
                self.fp += 1   # detector fired on benign event
            else:
                self.tn += 1

    def precision(self) -> float:
        """Precision = TP / (TP + FP). Returns 0.0 when undefined (no predictions)."""
        return self.tp / (self.tp + self.fp) if self.precision_defined else 0.0

    def recall(self) -> float:
        """Recall = TP / (TP + FN). Returns 0.0 when undefined (no positive labels)."""
        return self.tp / (self.tp + self.fn) if self.recall_defined else 0.0

    def f1(self) -> float:
        """F1 = harmonic mean of precision and recall. Returns 0.0 when undefined."""
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def to_dict(self) -> dict:
        """Return the full confusion matrix and metric values as a serialisable dict."""
        return {
            "true_positives": self.tp,
            "false_positives": self.fp,
            "true_negatives": self.tn,
            "false_negatives": self.fn,
            "precision": round(self.precision(), 4),
            "recall": round(self.recall(), 4),
            "f1_score": round(self.f1(), 4),
            # Definedness flags — callers MUST check these before interpreting values
            "precision_defined": self.precision_defined,
            "recall_defined": self.recall_defined,
            "f1_defined": self.f1_defined,
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

        # Use a fully fixed UTC datetime so scenario evaluation is deterministic
        # regardless of the wall-clock date and time.  14:00 UTC is chosen so the
        # off-hours heuristic (00:00–06:00 UTC) does not fire spuriously on benign events,
        # which would otherwise cause false positives in every scenario run at night.
        # Temporal detection remains exercisable via timestamp_offset_seconds < -8*3600.
        base_time = datetime(2024, 6, 15, 14, 0, 0, tzinfo=UTC)
        session_id = uuid4()

        # Pre-register agents that have declared capability scopes in the scenario.
        # This is required for CAPABILITY_ESCALATION detection to fire correctly:
        # the detector compares the action_type against declared_capability_scope,
        # which is only set when the agent has been explicitly registered.
        if scenario.agent_declared_capability_scope:
            agent_ids = {se.agent_id for se in scenario.events}
            for agent_id in agent_ids:
                self.pipeline.registry.register_agent(
                    agent_id=agent_id,
                    owning_principal="scenario",
                    declared_capability_scope=scenario.agent_declared_capability_scope,
                    authorized_resource_scope=[],
                )

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
