"""Predictive Intelligence Layer -- Phase 2 Full Implementation.

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

# Slope thresholds for trend classification (per event-index unit)
SLOPE_DEGRADING = -0.01
SLOPE_RECOVERING = 0.01

# R-squared threshold below which the trend is classified VOLATILE
RSQUARED_VOLATILE_THRESHOLD = 0.25

# Minimum score range to consider volatility meaningful
VOLATILE_MOVEMENT_THRESHOLD = 0.03

# Minimum session age (seconds) for a reliable events-per-second estimate.
# Below this threshold the observed event rate is treated as unreliable for
# a 1-hour horizon projection; the confidence interval is widened to [0, 1].
# Justification: with < 60 s of observation the rate estimate has a relative
# standard error > 100 % at the 1-hour horizon, making any projected point
# estimate misleading.  The stub path already returns (0, 1) CI, so this
# threshold produces consistent behaviour.
MIN_SESSION_AGE_SECONDS = 60.0


def _linregress(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float, float]:
    """Ordinary least-squares regression: y = slope * x + intercept.

    Returns:
        slope      -- fitted slope (units: score / event-index)
        intercept  -- fitted intercept (units: score)
        r_squared  -- coefficient of determination, clamped to [0, 1]
        sigma_hat  -- residual standard deviation (sqrt of MSE), units: score.
                      This is the estimate of the noise level in y, not the
                      standard error of the slope.  It is used to construct the
                      confidence interval on the fitted mean at a new x.
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
        # Degenerate: all x values identical (constant session).
        # Return zero slope, mean y, perfect R2 (flat fit), and score std as sigma.
        y_mean = sum_y / n
        ss = sum((y - y_mean) ** 2 for y in ys)
        sigma_hat = math.sqrt(ss / n) if n > 1 else 0.0
        return 0.0, y_mean, 1.0, sigma_hat

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    y_mean = sum_y / n
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)

    r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 1.0

    # Residual standard deviation (sigma_hat = sqrt(MSE))
    # Degrees of freedom = n - 2 (slope + intercept estimated)
    # For n == 2, MSE is undefined (0 residual df); return 0 sigma.
    if n > 2:
        sigma_hat = math.sqrt(ss_res / (n - 2))
    else:
        sigma_hat = 0.0

    return slope, intercept, max(0.0, min(1.0, r_squared)), sigma_hat


def _classify_trend(
    slope: float, r_squared: float, ys: list[float]
) -> TrendDirection:
    """Classify the trend direction from regression results."""
    score_range = max(ys) - min(ys) if len(ys) > 1 else 0.0

    # Volatile: low R-squared with meaningful score movement
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
        """Run regression and return a full projection (REQ-021.6).

        Confidence-interval model:
        --------------------------
        We report a 95 % *confidence interval on the fitted mean* at the
        forecast horizon, not a prediction interval for a single future
        observation.  The CI represents uncertainty about *where the mean
        trend line sits* at the horizon, not the full spread of individual
        future scores.  For the research purpose (detecting degrading trends
        early) the mean CI is the appropriate quantity.

        Formula for CI half-width at forecast point x_new:

            se_mean(x_new) = sigma_hat * sqrt(1/n + (x_new - x_mean)^2 / Sxx)
            ci_half        = z_95 * se_mean(x_new)    where z_95 = 1.96

        where:
            sigma_hat = sqrt(SS_residual / (n-2))    residual std deviation
            n         = history_depth                number of observations
            x_mean    = (n-1)/2                      mean of 0..n-1
            Sxx       = sum((x_i - x_mean)^2)        sum of squared x deviations

        Event-rate extrapolation:
        -------------------------
        The forecast horizon is expressed in "event units" because the
        regression x-axis is event index, not wall-clock time.  The number
        of events expected in the next 3600 s is estimated from the observed
        rate.  However, a rate estimated from a very short session window
        (<= MIN_SESSION_AGE_SECONDS = 60 s) has large relative uncertainty
        at the 1-hour horizon, so when the session age is too small we use
        the observed inter-event spacing from the history itself rather than
        the coarse session-age denominator.  When even that is unavailable we
        default to one event per minute.

        This is not an arbitrary cap: it is the natural consequence of using a
        minimum-variance estimator of the event rate given the observed data.
        """
        history = trust_state.history

        # x = event index (0, 1, ..., n-1), y = trust score after each update
        xs = [float(i) for i in range(history_depth)]
        ys = [float(entry.new_score) for entry in history]

        slope, intercept, r_squared, sigma_hat = _linregress(xs, ys)
        trend = _classify_trend(slope, r_squared, ys)

        # ---- Event-rate estimate ----
        # Prefer the per-event inter-arrival estimate when session age is short.
        # session_age_seconds is the elapsed time from session start to the last
        # validated event; it equals (n-1) * mean_inter_event_time when events
        # arrive uniformly.  For n observations over T seconds the mean inter-event
        # interval is T / (n-1), giving a rate of (n-1)/T events/second.
        session_age = trust_state.session_age_seconds
        horizon_seconds = 3600.0

        if session_age is None or session_age <= 0.0:
            # Zero or missing session age: cannot estimate rate from wall time.
            # Default to 1 event/minute as a conservative assumption.
            events_per_second = 1.0 / 60.0
            rate_reliable = False
        elif session_age < MIN_SESSION_AGE_SECONDS:
            # Session too short for a reliable 1-hour rate estimate.
            # Use the observed inter-event spacing instead.
            # Inter-event time = session_age / max(n-1, 1) seconds/event
            inter_event_seconds = session_age / max(history_depth - 1, 1)
            events_per_second = 1.0 / inter_event_seconds
            rate_reliable = False
        else:
            # Adequate session age: compute rate directly.
            events_per_second = history_depth / session_age
            rate_reliable = True

        horizon_events = events_per_second * horizon_seconds
        x_new = float(history_depth - 1) + horizon_events  # last observed x + steps ahead

        projected_score = float(slope * x_new + intercept)
        projected_score = max(0.0, min(1.0, projected_score))

        # ---- Confidence interval on the fitted mean at x_new ----
        # If the rate is unreliable, or sigma_hat is zero (perfect linear fit
        # with n == 2), we report the full [0, 1] interval to communicate that
        # the extrapolation is unreliable rather than silently capping to look good.
        if not rate_reliable or sigma_hat == 0.0 or history_depth < 3:
            ci_lower, ci_upper = 0.0, 1.0
        else:
            n = float(history_depth)
            x_mean = (n - 1.0) / 2.0                            # mean of 0..n-1
            sxx = sum((x - x_mean) ** 2 for x in xs)           # sum of squared deviations
            if sxx < 1e-12:
                # Numerically degenerate Sxx (all x identical); full uncertainty.
                ci_lower, ci_upper = 0.0, 1.0
            else:
                se_mean = sigma_hat * math.sqrt(1.0 / n + (x_new - x_mean) ** 2 / sxx)
                ci_half = 1.96 * se_mean
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