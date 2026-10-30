import pathlib
import os

BASE = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx")

files = {}

# ============================================================
# PREDICTIVE ENGINE -- PHASE 2
# ============================================================
files["varynx/engine/prediction.py"] = r'''"""Predictive Intelligence Layer -- Phase 2 Full Implementation.

Phase 1: Falls back to STABLE stub when history < MIN_HISTORY_FOR_TREND.
Phase 2: Window-based linear regression over TrustHistoryEntry records.

Pure-Python implementation (no numpy/scipy dependency).

Satisfies: REQ-021
"""
from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from uuid import uuid4

from varynx.models.prediction import TrajectoryProjection, TrendDirection
from varynx.models.trust import TrustState

logger = logging.getLogger(__name__)

# Minimum history required before trend computation
MIN_HISTORY_FOR_TREND = 3
# Slope thresholds for trend classification
SLOPE_DEGRADING = -0.01    # per event
SLOPE_RECOVERING = 0.01    # per event
# R-squared threshold below which we call the trend VOLATILE
RSQUARED_VOLATILE_THRESHOLD = 0.25
# Minimum score movement to consider volatility meaningful
VOLATILE_MOVEMENT_THRESHOLD = 0.03


def _linregress(xs: list[float], ys: list[float]) -> tuple[float, float, float, float]:
    """Pure-Python simple linear regression: y = slope * x + intercept.

    Returns (slope, intercept, r_squared, stderr).
    """
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.5, 0.0, 1.0

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))

    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0, sum_y / n, 0.0, 1.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R-squared
    y_mean = sum_y / n
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)

    r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 1.0

    # Standard error of the slope
    if n > 2 and abs(ss_tot) > 1e-12:
        mse = ss_res / (n - 2)
        var_x = (sum_xx / n) - (sum_x / n) ** 2
        stderr = math.sqrt(mse / (n * var_x)) if var_x > 1e-12 else 0.0
    else:
        stderr = 0.0

    return slope, intercept, max(0.0, min(1.0, r_squared)), stderr


def _classify_trend(slope: float, r_squared: float, ys: list[float]) -> TrendDirection:
    """Classify the trend direction from regression results."""
    score_range = max(ys) - min(ys) if len(ys) > 1 else 0.0

    # Volatile: low R-squared with meaningful movement
    if r_squared < RSQUARED_VOLATILE_THRESHOLD and score_range > VOLATILE_MOVEMENT_THRESHOLD:
        return TrendDirection.VOLATILE

    if slope <= SLOPE_DEGRADING:
        return TrendDirection.DEGRADING
    if slope >= SLOPE_RECOVERING:
        return TrendDirection.RECOVERING
    return TrendDirection.STABLE


class PredictiveEngine:
    """Predictive trajectory engine.

    Phase 1 stub when history < MIN_HISTORY_FOR_TREND.
    Phase 2 full engine when sufficient history is available.

    Satisfies: REQ-021, design.md Section 10
    """

    def __init__(self, warning_threshold: float = 0.3) -> None:
        self.warning_threshold = warning_threshold

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def project(self, trust_state: TrustState) -> TrajectoryProjection:
        """Return a trajectory projection for the agent.

        Must never store results as EvidenceRecords (REQ-021.7).
        All outputs labeled is_projected=True (REQ-021.6).

        Satisfies: REQ-021
        """
        history = trust_state.history
        history_depth = len(history)
        low_history = history_depth < MIN_HISTORY_FOR_TREND

        # Stub path -- insufficient history
        if low_history:
            return TrajectoryProjection.model_validate(dict(
                projection_id=str(uuid4()),
                session_id=str(trust_state.session_id),
                agent_id=trust_state.agent_id,
                trend=TrendDirection.STABLE.value,
                projected_trust_at_horizon=trust_state.current_score,
                horizon_seconds=3600.0,
                confidence_interval=(0.0, 1.0),
                early_warning=False,
                warning_threshold=self.warning_threshold,
                is_projected=True,
                is_stub=True,
                low_history_stub=True,
                computation_timestamp=str(self._now()),
            ), strict=False)

        # Phase 2 full path -- run regression over trust score history
        try:
            return self._compute(trust_state, history_depth)
        except Exception:
            logger.exception(
                "TRAJECTORY_COMPUTATION_ERROR for agent %s; falling back to STABLE stub",
                trust_state.agent_id,
            )
            return TrajectoryProjection.model_validate(dict(
                projection_id=str(uuid4()),
                session_id=str(trust_state.session_id),
                agent_id=trust_state.agent_id,
                trend=TrendDirection.STABLE.value,
                projected_trust_at_horizon=trust_state.current_score,
                horizon_seconds=3600.0,
                confidence_interval=(0.0, 1.0),
                early_warning=False,
                warning_threshold=self.warning_threshold,
                is_projected=True,
                is_stub=True,
                low_history_stub=False,
                computation_timestamp=str(self._now()),
            ), strict=False)

    def _compute(self, trust_state: TrustState, history_depth: int) -> TrajectoryProjection:
        """Run regression and return a full projection (REQ-021.6)."""
        history = trust_state.history

        # x = event index (0, 1, 2, ...), y = trust score after each update
        xs = [float(i) for i in range(history_depth)]
        ys = [float(entry.new_score) for entry in history]

        slope, intercept, r_squared, stderr = _linregress(xs, ys)
        trend = _classify_trend(slope, r_squared, ys)

        # Project to horizon (default 1 hour = ~3600s; estimate events/hour from session age)
        session_age = trust_state.session_age_seconds or 3600.0
        events_per_second = history_depth / session_age if session_age > 0 else 1.0 / 60.0
        horizon_seconds = 3600.0
        horizon_events = events_per_second * horizon_seconds

        projected_score = float(slope * (history_depth + horizon_events) + intercept)
        projected_score = max(0.0, min(1.0, projected_score))

        # 95% confidence interval using 1.96 * stderr of regression (per-event)
        ci_half = 1.96 * stderr * math.sqrt(1.0 + 1.0 / history_depth + horizon_events)
        ci_lower = max(0.0, projected_score - ci_half)
        ci_upper = min(1.0, projected_score + ci_half)

        early_warning = projected_score < self.warning_threshold

        return TrajectoryProjection.model_validate(dict(
            projection_id=str(uuid4()),
            session_id=str(trust_state.session_id),
            agent_id=trust_state.agent_id,
            trend=trend.value,
            projected_trust_at_horizon=round(projected_score, 4),
            horizon_seconds=horizon_seconds,
            confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
            early_warning=early_warning,
            warning_threshold=self.warning_threshold,
            is_projected=True,
            is_stub=False,
            low_history_stub=False,
            computation_timestamp=str(self._now()),
        ), strict=False)
'''

for rel, content in files.items():
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"Written: {rel} ({p.stat().st_size} bytes)")

print("DONE")