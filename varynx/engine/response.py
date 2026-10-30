"""Adaptive Response Engine.

Maps (TrustLevel, AnomalyClass[]) to ResponseType using a configurable YAML policy.
Enforces escalation monotonicity. Records policy version with every recommendation.

Satisfies: REQ-009, REQ-011
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml

from varynx.models.bcse import BCSeResult
from varynx.models.evidence import EvidenceBundle
from varynx.models.prediction import TrajectoryProjection
from varynx.models.response import ReasonCode, ResponseRecommendation, ResponseType
from varynx.models.trust import TrustLevel, TrustState

logger = logging.getLogger(__name__)

# Severity ordering for escalation monotonicity (REQ-011.5)
_SEVERITY_ORDER: dict[str, int] = {
    ResponseType.PERMIT.value: 0,
    ResponseType.WARN.value: 1,
    ResponseType.RESTRICT.value: 2,
    ResponseType.ESCALATE.value: 3,
    ResponseType.SUSPEND.value: 4,
    ResponseType.TERMINATE.value: 5,
}


class AdaptiveResponseEngine:
    """Maps evidence + trust + trajectory to ResponseRecommendation via policy YAML.

    Satisfies: REQ-009, REQ-011
    """

    def __init__(self, policy_path: str | Path | None = None) -> None:
        self._policy: dict[str, Any] = {}
        self._policy_version = "unknown"
        self._policy_id = "default"
        self._active_responses: dict[str, str] = {}  # agent_id -> current response_type
        self._policy_invalid = False

        if policy_path:
            self.load_policy(policy_path)
        else:
            # Try default path
            default = Path("config/default_policy.yaml")
            if default.exists():
                self.load_policy(default)
            else:
                self._policy_invalid = True
                logger.error("POLICY_TABLE_INVALID: No policy file found at startup")

    def load_policy(self, path: str | Path) -> None:
        """Load and validate the policy YAML file (REQ-020.2)."""
        try:
            with open(path) as f:
                policy = yaml.safe_load(f)
            self._policy = policy
            self._policy_version = str(policy.get("version", "1.0.0"))
            self._policy_id = str(Path(path).stem)
            self._policy_invalid = False
            logger.info("Loaded policy %s v%s from %s", self._policy_id, self._policy_version, path)
        except Exception as exc:
            self._policy_invalid = True
            logger.error("POLICY_TABLE_INVALID: Failed to load policy from %s: %s", path, exc)

    def _get_anomaly_classes(self, bundle: EvidenceBundle) -> list[str]:
        return list({r.anomaly_class.value for r in bundle.records if r.derivation_status == "COMPLETE"})

    def _evaluate_rule(
        self,
        rule_if: dict[str, Any],
        trust_level: TrustLevel,
        anomaly_classes: list[str],
        trajectory: TrajectoryProjection | None,
    ) -> bool:
        """Check if a policy rule condition matches."""
        rule_trust = rule_if.get("trust_level")
        if rule_trust:
            levels = [rule_trust] if isinstance(rule_trust, str) else rule_trust
            if trust_level.value not in levels:
                return False

        rule_anomaly = rule_if.get("anomaly_class")
        if rule_anomaly:
            if rule_anomaly not in anomaly_classes:
                return False

        rule_traj = rule_if.get("trajectory")
        if rule_traj and trajectory:
            if trajectory.trend.value.lower() != rule_traj.lower():
                return False

        return True

    def _apply_escalation_monotonicity(
        self, agent_id: str, proposed: str
    ) -> str:
        """Enforce escalation monotonicity: never de-escalate without explicit event.

        REQ-011.5: The engine never recommends a lower severity response than the
        current active recommendation without an explicit de-escalation event.
        """
        current = self._active_responses.get(agent_id)
        if current is None:
            return proposed
        current_ord = _SEVERITY_ORDER.get(current, 0)
        proposed_ord = _SEVERITY_ORDER.get(proposed, 0)
        if proposed_ord >= current_ord:
            return proposed
        # Cannot de-escalate; maintain current response
        return current

    def recommend(
        self,
        agent_id: str,
        correlation_id: UUID,
        evidence_bundle: EvidenceBundle,
        trust_state: TrustState,
        bcse_result: BCSeResult | None = None,
        trajectory: TrajectoryProjection | None = None,
        target_capability: str | None = None,
        target_resource: str | None = None,
    ) -> ResponseRecommendation:
        """Generate a ResponseRecommendation for the given agent state.

        Satisfies: REQ-009, REQ-011
        """
        # Policy table fallback (REQ-011.7)
        if self._policy_invalid or not self._policy:
            # REQ-011.7: fall back to WARN (the "MONITOR" response) when the
            # policy table is invalid or missing.  WARN permits the operation to
            # proceed but signals that the policy layer is degraded; every
            # subsequent event is still analysed by the full behavioral pipeline.
            # Using PERMIT here was a defect -- it silently allows everything
            # through with no indication that policy evaluation failed.
            logger.error("POLICY_TABLE_INVALID: Falling back to WARN (MONITOR) per REQ-011.7")
            return self._make_recommendation(
                agent_id=agent_id,
                correlation_id=correlation_id,
                response_type=ResponseType.WARN,
                evidence_bundle=evidence_bundle,
                trust_state=trust_state,
                bcse_result=bcse_result,
                trajectory=trajectory,
                reason_code_strs=["POLICY_TABLE_INVALID"],
                target_capability=target_capability,
                target_resource=target_resource,
            )

        trust_level = trust_state.level
        anomaly_classes = self._get_anomaly_classes(evidence_bundle)
        rules = self._policy.get("rules", [])

        response_type_str = None
        reason_code_strs: list[str] = []

        for rule in rules:
            if "default" in rule:
                response_type_str = rule["default"]["response"]
                reason_code_strs = rule["default"].get("reason_codes", [])
                break
            rule_if = rule.get("if", {})
            rule_then = rule.get("then", {})
            if self._evaluate_rule(rule_if, trust_level, anomaly_classes, trajectory):
                response_type_str = rule_then["response"]
                reason_code_strs = rule_then.get("reason_codes", [])
                break

        if response_type_str is None:
            response_type_str = "PERMIT"

        # Escalation monotonicity (REQ-011.5)
        final_response = self._apply_escalation_monotonicity(agent_id, response_type_str)
        self._active_responses[agent_id] = final_response

        return self._make_recommendation(
            agent_id=agent_id,
            correlation_id=correlation_id,
            response_type=ResponseType(final_response),
            evidence_bundle=evidence_bundle,
            trust_state=trust_state,
            bcse_result=bcse_result,
            trajectory=trajectory,
            reason_code_strs=reason_code_strs,
            target_capability=target_capability,
            target_resource=target_resource,
        )

    def _make_recommendation(
        self,
        agent_id: str,
        correlation_id: UUID,
        response_type: ResponseType,
        evidence_bundle: EvidenceBundle,
        trust_state: TrustState,
        bcse_result: BCSeResult | None,
        trajectory: TrajectoryProjection | None,
        reason_code_strs: list[str],
        target_capability: str | None = None,
        target_resource: str | None = None,
    ) -> ResponseRecommendation:
        """Construct a ResponseRecommendation with all required fields (REQ-009.1)."""
        evidence_ids = [r.evidence_id for r in evidence_bundle.records[:5]]
        severity_map = {
            ResponseType.PERMIT: "INFO",
            ResponseType.WARN: "WARNING",
            ResponseType.RESTRICT: "WARNING",
            ResponseType.ESCALATE: "CRITICAL",
            ResponseType.SUSPEND: "CRITICAL",
            ResponseType.TERMINATE: "CRITICAL",
        }
        reason_codes = [
            ReasonCode.model_validate(
                dict(
                    code=code,
                    description=f"Policy rule triggered: {code}",
                    contributing_evidence_ids=[str(eid) for eid in evidence_ids],
                    trust_level_at_recommendation=trust_state.level.value,
                    severity=severity_map.get(response_type, "INFO"),
                ),
                strict=False,
            )
            for code in (reason_code_strs or ["POLICY_EVALUATION_COMPLETE"])
        ]

        rationale = (
            f"Response recommendation '{response_type.value}' for agent '{agent_id}'. "
            f"Trust level: {trust_state.level.value} (score={trust_state.current_score:.3f}). "
            f"Anomaly classes detected: {self._get_anomaly_classes(evidence_bundle) or ['none']}. "
            f"Policy: {self._policy_id} v{self._policy_version}. "
            f"Evidence IDs: {[str(eid) for eid in evidence_ids[:3]]}."
        )

        return ResponseRecommendation.model_validate(
            dict(
                recommendation_id=str(uuid4()),
                agent_id=agent_id,
                correlation_id=str(correlation_id),
                response_type=response_type.value,
                reason_codes=[rc.model_dump() for rc in reason_codes],
                evidence_bundle_id=str(evidence_bundle.bundle_id),
                trust_state_snapshot=trust_state.model_dump(),
                bcse_result_id=str(bcse_result.bcse_id) if bcse_result else None,
                trajectory_projection_id=str(trajectory.projection_id) if trajectory else None,
                rationale=rationale,
                timestamp=str(datetime.now(UTC)),
                policy_id=self._policy_id,
                policy_version=self._policy_version,
                target_capability=target_capability,
                target_resource=target_resource,
            ),
            strict=False,
        )

    def de_escalate(self, agent_id: str) -> None:
        """Explicit de-escalation event (REQ-011.5). Resets escalation state for agent."""
        self._active_responses.pop(agent_id, None)
