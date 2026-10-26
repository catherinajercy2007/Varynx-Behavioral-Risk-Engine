"""BCSE Engine — Phase 1 Stub.

Phase 1 stub returns is_stub=True with no counterfactuals.
Phase 2 full implementation: policy simulation, consequence projection, divergence scoring.

Satisfies: REQ-007, REQ-008
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from varynx.config import BCSeConfig
from varynx.models.bcse import BCSeContext, BCSeResult, ConsequenceProjection


class BCSeEngine:
    """Phase 1 BCSE stub.

    Returns a stub result with is_stub=True, no counterfactuals, divergence_score=0.0.
    Satisfies: REQ-007, design.md Section 9.3
    """

    def __init__(self, config: BCSeConfig | None = None) -> None:
        self.config = config or BCSeConfig()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def analyze(self, context: BCSeContext) -> BCSeResult:
        """Evaluate a proposed action and return a projected consequence (Phase 1 stub).

        MUST be non-destructive: never writes to any store (REQ-007.3).
        Returns HTTP 503 on internal failure, never a partial result (REQ-007.8).

        Phase 1 stub behavior (design.md Section 9.3):
        - is_stub=True
        - active_consequence mirrors current policy recommendation
        - counterfactual_consequences is []
        - divergence_score is 0.0
        - uncertainty reflects history depth
        """
        agent_id = context.proposed_action.agent_id
        history_depth = len(context.trust_state.history)
        low_history = history_depth < self.config.min_history_events

        uncertainty = 1.0 if low_history else max(0.1, 1.0 - history_depth / 100.0)
        risk_level = "UNKNOWN" if low_history else self._derive_risk_level(context)

        active_consequence = ConsequenceProjection(
            policy_id=context.active_policy_id,
            projected_response="PERMIT",  # Stub: mirrors current policy outcome
            projected_trust_impact=0.0,
            risk_level=risk_level,
            uncertainty_score=uncertainty,
            confidence=0.0 if low_history else 0.5,
            rationale=(
                "Phase 1 BCSE stub. This is a placeholder projection. "
                "Phase 2 will implement full policy simulation and consequence projection. "
                "Evidence IDs are referenced from the provided evidence bundle."
            ),
            supporting_evidence_ids=[r.evidence_id for r in context.evidence_bundle.records[:3]],
            is_projected=True,
            projection_basis=f"Phase 1 stub; history_depth={history_depth}",
        )

        return BCSeResult.model_validate(
            dict(
                bcse_id=str(uuid4()),
                context_id=str(context.context_id),
                agent_id=agent_id,
                evaluation_timestamp=str(self._now()),
                active_consequence=active_consequence.model_dump(),
                counterfactual_consequences=[],
                divergence_score=0.0,
                analysis_timestamp=str(self._now()),
                is_stub=True,
                low_history_warning=low_history,
            ),
            strict=False,
        )

    def _derive_risk_level(self, context: BCSeContext) -> str:
        """Derive risk level from current trust score (Phase 1 stub heuristic)."""
        score = context.trust_state.current_score
        if score >= 0.65:
            return "LOW"
        if score >= 0.40:
            return "MEDIUM"
        if score >= 0.20:
            return "HIGH"
        return "CRITICAL"
