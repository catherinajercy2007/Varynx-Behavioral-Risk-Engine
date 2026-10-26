"""Predictive Intelligence Layer — Phase 1 Stub.

Phase 1: Always returns TrendDirection.STABLE, is_stub=True, early_warning=False.
Phase 2: Window-based linear regression trend analysis over TrustHistoryEntry records.

Satisfies: REQ-021
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from varynx.models.prediction import TrajectoryProjection, TrendDirection
from varynx.models.trust import TrustState


class PredictiveEngine:
    """Phase 1 trajectory projection stub.

    Satisfies: REQ-021, design.md Section 10.3
    """

    # Minimum history entries before computing trend (Phase 2 threshold)
    MIN_HISTORY_FOR_TREND = 5

    def __init__(self, warning_threshold: float = 0.3) -> None:
        self.warning_threshold = warning_threshold

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def project(self, trust_state: TrustState) -> TrajectoryProjection:
        """Return a trajectory projection for the agent.

        Phase 1 stub always returns STABLE. Phase 2 implements trend analysis.
        Must never store results as Evidence_Records (REQ-021.7).
        All outputs labeled is_projected=True (REQ-021.6).

        Satisfies: REQ-021
        """
        history_depth = len(trust_state.history)
        low_history = history_depth < self.MIN_HISTORY_FOR_TREND

        return TrajectoryProjection.model_validate(
            dict(
                projection_id=str(uuid4()),
                session_id=str(trust_state.session_id),
                agent_id=trust_state.agent_id,
                trend=TrendDirection.STABLE.value,
                projected_trust_at_horizon=trust_state.current_score,  # Stub: no projection
                horizon_seconds=3600.0,
                confidence_interval=(0.0, 1.0),  # Full uncertainty in Phase 1
                early_warning=False,
                warning_threshold=self.warning_threshold,
                is_projected=True,
                is_stub=True,
                low_history_stub=low_history,
                computation_timestamp=str(self._now()),
            ),
            strict=False,
        )
