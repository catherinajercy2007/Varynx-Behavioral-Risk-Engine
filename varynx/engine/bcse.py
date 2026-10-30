"""BCSE Engine Phase 2 Full Implementation.

Phase 1 stub: is_stub=True when no alternative policies provided.
Phase 2 full: evaluates PolicyAlternatives, computes divergence.

Satisfies: REQ-007, REQ-008
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from varynx.config import BCSeConfig
from varynx.models.bcse import BCSeContext, BCSeResult, ConsequenceProjection

logger = logging.getLogger(__name__)

_RESPONSE_SEVERITY: dict[str, int] = {
    "PERMIT": 0, "WARN": 1, "RESTRICT": 2,
    "ESCALATE": 3, "SUSPEND": 4, "TERMINATE": 5,
}
_MAX_SEVERITY_DISTANCE = 5


def _projected_response(composite: float, overrides: dict) -> str:
    t = float(overrides.get("terminate_threshold", 0.85))
    s = float(overrides.get("suspend_threshold", 0.65))
    r = float(overrides.get("restrict_threshold", 0.40))
    w = float(overrides.get("warn_threshold", 0.20))
    if composite >= t: return "TERMINATE"
    if composite >= s: return "SUSPEND"
    if composite >= r: return "RESTRICT"
    if composite >= w: return "WARN"
    return "PERMIT"


def _risk_level(composite: float, overrides: dict, low_history: bool) -> str:
    if low_history:
        return "UNKNOWN"
    h = float(overrides.get("high_risk_threshold", 0.65))
    m = float(overrides.get("medium_risk_threshold", 0.40))
    l = float(overrides.get("low_risk_threshold", 0.20))
    if composite >= h: return "HIGH"
    if composite >= m: return "MEDIUM"
    if composite >= l: return "LOW"
    return "NONE"


_TRUST_IMPACT = {"PERMIT": 0.0, "WARN": -0.02, "RESTRICT": -0.05,
                  "ESCALATE": -0.08, "SUSPEND": -0.12, "TERMINATE": -0.20}


def _confidence(evidence_bundle, history_depth: int) -> float:
    total = len(evidence_bundle.records)
    if total == 0 or history_depth == 0:
        return 0.0
    complete = sum(1 for r in evidence_bundle.records if r.derivation_status == "COMPLETE")
    return round(min(1.0, (complete / total) * min(1.0, history_depth / 20.0)), 4)


def _divergence(active: str, counterfactuals: list[str]) -> float:
    if not counterfactuals:
        return 0.0
    a = _RESPONSE_SEVERITY.get(active, 0)
    return round(max(abs(a - _RESPONSE_SEVERITY.get(c, 0)) for c in counterfactuals)
                 / _MAX_SEVERITY_DISTANCE, 4)


def _build_consequence(policy_id, evidence_bundle, trust_score, history_depth,
                        overrides, low_history, prefix="") -> ConsequenceProjection:
    comp = evidence_bundle.composite_score
    resp = _projected_response(comp, overrides)
    risk = _risk_level(comp, overrides, low_history)
    conf = _confidence(evidence_bundle, history_depth)
    top3 = sorted(evidence_bundle.records, key=lambda r: r.score, reverse=True)[:3]
    top_ids = [str(r.evidence_id) for r in top3]
    top_cls = [str(getattr(r, "anomaly_class", "?")) for r in top3]
    rationale = " | ".join(filter(None, [
        prefix,
        f"composite={comp:.3f} projected={resp} confidence={conf:.2f} depth={history_depth}",
        ("Top: " + ", ".join(top_cls)) if top_cls else "",
    ]))
    return ConsequenceProjection.model_validate(dict(
        policy_id=policy_id,
        projected_response=resp,
        projected_trust_impact=_TRUST_IMPACT.get(resp, 0.0),
        risk_level=risk,
        uncertainty_score=max(0.0, 1.0 - conf),
        confidence=conf,
        rationale=rationale,
        supporting_evidence_ids=top_ids,
        is_projected=True,
        projection_basis=f"Phase2;depth={history_depth};composite={comp:.3f}",
    ), strict=False)


class BCSeEngine:
    """BCSE Engine — Phase 2 when alternatives provided, Phase 1 stub otherwise.

    Satisfies: REQ-007, REQ-008
    """

    def __init__(self, config: BCSeConfig | None = None) -> None:
        self.config = config or BCSeConfig()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def analyze(self, context: BCSeContext) -> BCSeResult:
        """Evaluate proposed action. Non-destructive (REQ-007.3)."""
        agent_id = context.proposed_action.agent_id
        history_depth = len(context.trust_state.history)
        low_history = history_depth < self.config.min_history_events
        try:
            return self._run(context, agent_id, history_depth, low_history)
        except Exception:
            logger.exception("BCSE_EVALUATION_FAILED for agent %s", agent_id)
            return self._emergency_stub(context, agent_id, low_history)

    def _run(self, context, agent_id, history_depth, low_history) -> BCSeResult:
        trust_score = context.trust_state.current_score
        active = _build_consequence(
            context.active_policy_id, context.evidence_bundle,
            trust_score, history_depth, {}, low_history, "Active policy")

        if not context.alternative_policies:
            # Phase 1 stub path
            return BCSeResult.model_validate(dict(
                bcse_id=str(uuid4()), context_id=str(context.context_id),
                agent_id=agent_id, evaluation_timestamp=str(self._now()),
                active_consequence=active.model_dump(),
                counterfactual_consequences=[], divergence_score=0.0,
                analysis_timestamp=str(self._now()),
                is_stub=True, low_history_warning=low_history,
            ), strict=False)

        # Phase 2 full path
        cfs = []
        for alt in context.alternative_policies:
            cf = _build_consequence(
                alt.policy_id, context.evidence_bundle,
                trust_score, history_depth, alt.overrides, low_history,
                f"Alt: {alt.label}")
            cfs.append(cf)

        return BCSeResult.model_validate(dict(
            bcse_id=str(uuid4()), context_id=str(context.context_id),
            agent_id=agent_id, evaluation_timestamp=str(self._now()),
            active_consequence=active.model_dump(),
            counterfactual_consequences=[cf.model_dump() for cf in cfs],
            divergence_score=_divergence(active.projected_response,
                                          [cf.projected_response for cf in cfs]),
            analysis_timestamp=str(self._now()),
            is_stub=False, low_history_warning=low_history,
        ), strict=False)

    def _emergency_stub(self, context, agent_id, low_history) -> BCSeResult:
        stub_c = ConsequenceProjection.model_validate(dict(
            policy_id=context.active_policy_id, projected_response="PERMIT",
            projected_trust_impact=0.0, risk_level="UNKNOWN",
            uncertainty_score=1.0, confidence=0.0,
            rationale="BCSE_EVALUATION_FAILED", supporting_evidence_ids=[],
            is_projected=True, projection_basis="error-recovery",
        ), strict=False)
        return BCSeResult.model_validate(dict(
            bcse_id=str(uuid4()), context_id=str(context.context_id),
            agent_id=agent_id, evaluation_timestamp=str(self._now()),
            active_consequence=stub_c.model_dump(),
            counterfactual_consequences=[], divergence_score=0.0,
            analysis_timestamp=str(self._now()),
            is_stub=True, low_history_warning=low_history,
        ), strict=False)
