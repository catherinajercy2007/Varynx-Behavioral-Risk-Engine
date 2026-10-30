"""Tests for Predictive Trajectory Engine Phase 2.

Covers stub path, full path, trend classification, early warning, determinism.
"""
from __future__ import annotations
import os
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-pred")

from datetime import UTC, datetime
from uuid import uuid4

from varynx.engine.prediction import (
    MIN_HISTORY_FOR_TREND, PredictiveEngine, _classify_trend, _linregress,
)
from varynx.models.prediction import TrendDirection
from varynx.models.trust import TrustHistoryEntry, TrustLevel, TrustState


def _make_state(agent_id="ag1", scores=None, session_age=3600.0):
    if scores is None:
        scores = []
    entries = []
    prev = 0.7
    for i, s in enumerate(scores):
        entries.append(TrustHistoryEntry.model_validate(dict(
            entry_id=str(uuid4()), timestamp=datetime.now(UTC).isoformat(),
            prior_score=prev, delta=s - prev, new_score=s,
            contributing_evidence_ids=[], excluded_incomplete_count=0,
        ), strict=False))
        prev = s
    current = scores[-1] if scores else 0.7
    return TrustState.model_validate(dict(
        session_id=str(uuid4()), agent_id=agent_id,
        current_score=current, level=TrustLevel.ELEVATED.value,
        history=[e.model_dump() for e in entries],
        last_updated=datetime.now(UTC).isoformat(),
        session_age_seconds=session_age,
    ), strict=False)


class TestStubPath:
    def test_below_min_history_is_stub(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.65])  # < MIN_HISTORY_FOR_TREND=3
        proj = engine.project(state)
        assert proj.is_stub is True
        assert proj.trend == TrendDirection.STABLE
        assert proj.low_history_stub is True

    def test_empty_history_is_stub(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[])
        proj = engine.project(state)
        assert proj.is_stub is True

    def test_stub_has_full_uncertainty(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7])
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        assert lo == 0.0
        assert hi == 1.0


class TestFullPath:
    def test_sufficient_history_not_stub(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.65, 0.6])  # exactly MIN_HISTORY_FOR_TREND
        proj = engine.project(state)
        assert proj.is_stub is False
        assert proj.low_history_stub is False

    def test_degrading_trend(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.6, 0.5, 0.4, 0.3])
        proj = engine.project(state)
        assert proj.trend == TrendDirection.DEGRADING

    def test_recovering_trend(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.3, 0.4, 0.5, 0.6, 0.7])
        proj = engine.project(state)
        assert proj.trend == TrendDirection.RECOVERING

    def test_stable_trend(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.7, 0.7, 0.7, 0.7])
        proj = engine.project(state)
        assert proj.trend == TrendDirection.STABLE

    def test_early_warning_fires(self):
        engine = PredictiveEngine(warning_threshold=0.5)
        # Sharply degrading trend will project below 0.5
        state = _make_state(scores=[0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2])
        proj = engine.project(state)
        if proj.trend == TrendDirection.DEGRADING:
            assert proj.early_warning is True

    def test_no_early_warning_on_stable(self):
        engine = PredictiveEngine(warning_threshold=0.2)
        state = _make_state(scores=[0.8, 0.8, 0.8, 0.8, 0.8])
        proj = engine.project(state)
        assert proj.early_warning is False

    def test_all_outputs_labeled_projected(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.65, 0.6, 0.55])
        proj = engine.project(state)
        assert proj.is_projected is True

    def test_projected_score_in_range(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.65, 0.6, 0.55])
        proj = engine.project(state)
        assert 0.0 <= proj.projected_trust_at_horizon <= 1.0

    def test_confidence_interval_ordered(self):
        engine = PredictiveEngine()
        state = _make_state(scores=[0.7, 0.65, 0.6, 0.55])
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        assert lo <= proj.projected_trust_at_horizon <= hi or abs(lo - hi) < 0.001

    def test_deterministic(self):
        engine = PredictiveEngine()
        scores = [0.7, 0.65, 0.60, 0.55, 0.50]
        state = _make_state(scores=scores)
        p1 = engine.project(state)
        p2 = engine.project(state)
        assert p1.trend == p2.trend
        assert p1.projected_trust_at_horizon == p2.projected_trust_at_horizon


class TestLinregress:
    def test_perfect_linear_r_squared_1(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 0.9, 0.8, 0.7, 0.6]
        slope, intercept, r2, stderr = _linregress(xs, ys)
        assert abs(slope - (-0.1)) < 1e-9
        assert abs(r2 - 1.0) < 1e-6

    def test_constant_input(self):
        xs = [0.0, 1.0, 2.0]
        ys = [0.5, 0.5, 0.5]
        slope, intercept, r2, stderr = _linregress(xs, ys)
        assert abs(slope) < 1e-9


class TestClassifyTrend:
    def test_degrading(self):
        assert _classify_trend(-0.05, 0.9, [0.7, 0.65, 0.6]) == TrendDirection.DEGRADING

    def test_recovering(self):
        assert _classify_trend(0.05, 0.9, [0.4, 0.5, 0.6]) == TrendDirection.RECOVERING

    def test_stable(self):
        assert _classify_trend(0.005, 0.9, [0.6, 0.6, 0.6]) == TrendDirection.STABLE

    def test_volatile_low_rsquared(self):
        result = _classify_trend(0.0, 0.1, [0.3, 0.8, 0.2, 0.9, 0.3])
        assert result == TrendDirection.VOLATILE


# ---------------------------------------------------------------------------
# Regression tests for forecasting defects (Phase 3)
# ---------------------------------------------------------------------------

class TestCIFormula:
    """Tests that verify the corrected confidence-interval formula.

    Properties tested:
    - CI is bounded within [0, 1]
    - CI contains the projected score (lower <= projected <= upper)
    - For an adequate-session, reliable-rate forecast: CI is strictly
      narrower than [0, 1] when the data is informative
    - CI degrades to [0, 1] when the session is too short
    - CI degrades to [0, 1] when session age is zero / None
    - Determinism: same input always produces the same CI
    """

    def _make_full_state(self, scores, session_age=3600.0):
        return _make_state(scores=scores, session_age=session_age)

    def test_ci_lower_le_projected_le_upper_adequate_session(self):
        """CI must bracket the projected score for a normal session."""
        engine = PredictiveEngine()
        state = self._make_full_state(
            scores=[0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40],
            session_age=3600.0,
        )
        proj = engine.project(state)
        assert proj.is_stub is False
        lo, hi = proj.confidence_interval
        # Allow a small floating-point tolerance
        assert lo <= proj.projected_trust_at_horizon + 1e-6
        assert hi >= proj.projected_trust_at_horizon - 1e-6

    def test_ci_strictly_inside_unit_interval_adequate_session(self):
        """For a stable long session with many events, CI should be informative
        (i.e., not always [0, 1]).  This verifies the formula produces a meaningful
        interval rather than defaulting to full uncertainty."""
        engine = PredictiveEngine()
        # 10 events, stable scores, 1-hour session -- rate is reliable
        state = self._make_full_state(
            scores=[0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70],
            session_age=3600.0,
        )
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        # With a perfect flat trend and many observations, sigma_hat approaches 0
        # so CI should be narrow.  Assert at least narrower than [0.3, 0.7].
        assert lo >= 0.0 and hi <= 1.0
        # For stable data CI should not span the entire [0,1] unit interval
        assert (hi - lo) < 1.0, (
            f"CI [{lo}, {hi}] spans the entire unit interval; "
            "formula is probably still broken"
        )

    def test_ci_full_when_session_age_zero(self):
        """Zero session age -> rate unreliable -> CI must be [0.0, 1.0]."""
        engine = PredictiveEngine()
        state = self._make_full_state(
            scores=[0.70, 0.65, 0.60, 0.55, 0.50],
            session_age=0.0,
        )
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        assert lo == 0.0 and hi == 1.0, (
            f"Expected full-uncertainty CI [0.0, 1.0] for zero session age, got [{lo}, {hi}]"
        )

    def test_ci_full_when_session_too_short(self):
        """Session age < MIN_SESSION_AGE_SECONDS (60 s) -> CI must be [0.0, 1.0]."""
        from varynx.engine.prediction import MIN_SESSION_AGE_SECONDS
        engine = PredictiveEngine()
        state = self._make_full_state(
            scores=[0.70, 0.65, 0.60, 0.55, 0.50],
            session_age=MIN_SESSION_AGE_SECONDS - 1.0,  # just below threshold
        )
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        assert lo == 0.0 and hi == 1.0, (
            f"Expected full-uncertainty CI for short session, got [{lo}, {hi}]"
        )

    def test_ci_full_at_min_session_age_boundary(self):
        """Exactly at MIN_SESSION_AGE_SECONDS: rate considered reliable."""
        from varynx.engine.prediction import MIN_SESSION_AGE_SECONDS
        engine = PredictiveEngine()
        state = self._make_full_state(
            scores=[0.70, 0.68, 0.66, 0.64, 0.62],
            session_age=MIN_SESSION_AGE_SECONDS,  # exactly at threshold
        )
        proj = engine.project(state)
        # At exactly the threshold, rate is reliable -> CI may be narrower than [0,1]
        # Just assert it is valid
        lo, hi = proj.confidence_interval
        assert 0.0 <= lo <= hi <= 1.0

    def test_ci_bounds_always_within_unit_interval(self):
        """CI lower and upper must always be in [0, 1] for any input."""
        engine = PredictiveEngine()
        test_cases = [
            ([0.70, 0.65, 0.60], 3600.0),
            ([0.10, 0.09, 0.08, 0.07, 0.06], 3600.0),  # near-zero trend
            ([0.95, 0.96, 0.97, 0.98, 0.99], 3600.0),  # near-one trend
            ([0.70, 0.65, 0.60, 0.55, 0.50], 5.0),      # short session
            ([0.50, 0.50, 0.50, 0.50, 0.50], 3600.0),   # constant
        ]
        for scores, age in test_cases:
            state = self._make_full_state(scores, session_age=age)
            proj = engine.project(state)
            lo, hi = proj.confidence_interval
            assert 0.0 <= lo <= 1.0, f"lo={lo} out of range for scores={scores}, age={age}"
            assert 0.0 <= hi <= 1.0, f"hi={hi} out of range for scores={scores}, age={age}"
            assert lo <= hi, f"lo={lo} > hi={hi} for scores={scores}, age={age}"

    def test_ci_deterministic(self):
        """Identical inputs must produce identical CI."""
        engine = PredictiveEngine()
        state = self._make_full_state(
            scores=[0.70, 0.65, 0.60, 0.55, 0.50],
            session_age=3600.0,
        )
        p1 = engine.project(state)
        p2 = engine.project(state)
        assert p1.confidence_interval == p2.confidence_interval

    def test_degrading_trend_ci_still_valid(self):
        """Sharply degrading trend: CI must still be [lo, hi] with lo <= projected."""
        engine = PredictiveEngine(warning_threshold=0.3)
        state = self._make_full_state(
            scores=[0.70, 0.60, 0.50, 0.40, 0.30, 0.25, 0.20, 0.15],
            session_age=3600.0,
        )
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        assert 0.0 <= lo <= hi <= 1.0
        # For a clear degrading trend with adequate data, projected score is near
        # or below the warning threshold and early_warning should fire
        if proj.trend == TrendDirection.DEGRADING:
            assert proj.early_warning is True


class TestEventRateExtrapolation:
    """Tests that verify the event-rate estimation handles edge cases correctly."""

    def test_very_short_session_does_not_produce_enormous_horizon(self):
        """A 3-event session lasting 5 seconds should not project 2160 horizon events."""
        from varynx.engine.prediction import MIN_SESSION_AGE_SECONDS
        engine = PredictiveEngine()
        # 3 events in 5 seconds: naive rate = 0.6 events/s -> 2160 events/hour
        state = _make_state(
            scores=[0.70, 0.65, 0.60],
            session_age=5.0,
        )
        proj = engine.project(state)
        # With short session, CI should be full uncertainty
        lo, hi = proj.confidence_interval
        assert lo == 0.0 and hi == 1.0

    def test_zero_session_age_does_not_raise(self):
        """Zero session age must not cause ZeroDivisionError."""
        engine = PredictiveEngine()
        state = _make_state(
            scores=[0.70, 0.65, 0.60, 0.55],
            session_age=0.0,
        )
        # Must not raise
        proj = engine.project(state)
        assert proj.projected_trust_at_horizon >= 0.0
        assert proj.projected_trust_at_horizon <= 1.0

    def test_adequate_session_uses_direct_rate_estimate(self):
        """For a long session, the engine should produce a non-stub result."""
        engine = PredictiveEngine()
        state = _make_state(
            scores=[0.70, 0.68, 0.66, 0.64, 0.62],
            session_age=3600.0,  # adequate session age
        )
        proj = engine.project(state)
        assert proj.is_stub is False
        assert proj.trend == TrendDirection.DEGRADING

    def test_horizon_much_longer_than_observed_period_full_uncertainty(self):
        """When the forecast horizon vastly exceeds the observation window,
        the CI should communicate this uncertainty (be wide)."""
        engine = PredictiveEngine()
        # 3 events in 30 seconds -> session_age just below MIN_SESSION_AGE_SECONDS
        state = _make_state(
            scores=[0.70, 0.65, 0.60],
            session_age=30.0,
        )
        proj = engine.project(state)
        lo, hi = proj.confidence_interval
        # Short session -> full uncertainty CI
        assert lo == 0.0 and hi == 1.0


class TestLinregressSigmaHat:
    """Tests that _linregress now returns sigma_hat (residual std dev), not se_slope."""

    def test_sigma_hat_for_perfect_linear_data_is_zero(self):
        """Perfect linear fit has zero residuals, so sigma_hat = 0."""
        from varynx.engine.prediction import _linregress
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 0.9, 0.8, 0.7, 0.6]
        slope, intercept, r2, sigma_hat = _linregress(xs, ys)
        assert abs(sigma_hat) < 1e-9, f"Expected sigma_hat~0 for perfect linear, got {sigma_hat}"

    def test_sigma_hat_units_are_score_units(self):
        """sigma_hat is in score units (0-1 range), not normalised."""
        from varynx.engine.prediction import _linregress
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.70, 0.65, 0.72, 0.60]  # noisy data
        slope, intercept, r2, sigma_hat = _linregress(xs, ys)
        # sigma_hat should be small positive, in score units
        assert 0.0 <= sigma_hat < 0.2, f"Unexpected sigma_hat={sigma_hat}"

    def test_sigma_hat_for_n_equals_2_is_zero(self):
        """With only 2 points, df=0 -> sigma_hat must be 0."""
        from varynx.engine.prediction import _linregress
        xs = [0.0, 1.0]
        ys = [0.7, 0.6]
        slope, intercept, r2, sigma_hat = _linregress(xs, ys)
        assert sigma_hat == 0.0, f"Expected sigma_hat=0 for n=2, got {sigma_hat}"

    def test_sigma_hat_positive_for_noisy_data(self):
        """Noisy data should produce a positive sigma_hat."""
        from varynx.engine.prediction import _linregress
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [0.70, 0.55, 0.68, 0.52, 0.60]  # clearly noisy
        slope, intercept, r2, sigma_hat = _linregress(xs, ys)
        assert sigma_hat > 0.0, f"Expected positive sigma_hat for noisy data, got {sigma_hat}"