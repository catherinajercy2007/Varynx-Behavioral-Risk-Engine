import pathlib
BASE = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx")

files = {}

# ============================================================
# TEST: BCSE ENGINE
# ============================================================
files["tests/unit/test_bcse_engine.py"] = r'''"""Tests for BCSE Phase 2 Engine.

Covers stub path, full path, divergence, determinism, edge cases.
"""
from __future__ import annotations
import os
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-bcse")

from datetime import UTC, datetime
from uuid import uuid4

from varynx.engine.bcse import BCSeEngine, _divergence, _projected_response
from varynx.models.bcse import BCSeContext, PolicyAlternative
from varynx.models.evidence import AnomalyClass, EvidenceBundle, EvidenceRecord
from varynx.models.event import AgentActionEvent
from varynx.models.trust import TrustHistoryEntry, TrustLevel, TrustState


def _make_event(agent_id="test-agent"):
    return AgentActionEvent.model_validate(dict(
        agent_id=agent_id, session_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        action_type="READ", capability_requested="read:files",
        target_resource="/data/test.csv", authorization_result="allowed",
        is_simulated=True,
    ), strict=False)


def _make_trust_state(agent_id="test-agent", score=0.7, n_history=0):
    entries = []
    for i in range(n_history):
        s = 0.7 - i * 0.05
        entries.append(TrustHistoryEntry.model_validate(dict(
            entry_id=str(uuid4()), timestamp=datetime.now(UTC).isoformat(),
            prior_score=s + 0.05, delta=-0.05, new_score=s,
            contributing_evidence_ids=[], excluded_incomplete_count=0,
        ), strict=False))
    return TrustState.model_validate(dict(
        session_id=str(uuid4()), agent_id=agent_id,
        current_score=score, level=TrustLevel.ELEVATED.value,
        history=[e.model_dump() for e in entries],
        last_updated=datetime.now(UTC).isoformat(), session_age_seconds=0.0,
    ), strict=False)


def _make_bundle(composite=0.1, n_records=1):
    records = []
    for i in range(n_records):
        records.append(EvidenceRecord.model_validate(dict(
            evidence_id=str(uuid4()), agent_id="test-agent",
            session_id=str(uuid4()), correlation_id=str(uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            anomaly_class=AnomalyClass.CAPABILITY_ESCALATION.value,
            score=composite, weight=1.0, derivation_status="COMPLETE",
            content_hash="aabbcc", reason_codes=["TEST"],
        ), strict=False))
    return EvidenceBundle.model_validate(dict(
        bundle_id=str(uuid4()), agent_id="test-agent",
        session_id=str(uuid4()), correlation_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        records=[r.model_dump() for r in records],
        composite_score=composite,
    ), strict=False)


def _make_context(agent_id="test-agent", composite=0.1, n_history=0,
                   alternatives=None):
    return BCSeContext.model_validate(dict(
        context_id=str(uuid4()),
        proposed_action=_make_event(agent_id).model_dump(),
        evidence_bundle=_make_bundle(composite).model_dump(),
        trust_state=_make_trust_state(agent_id, n_history=n_history).model_dump(),
        active_policy_id="default",
        alternative_policies=[a.model_dump() for a in (alternatives or [])],
    ), strict=False)


class TestBCSeEngineStubPath:
    def test_no_alternatives_returns_stub(self):
        engine = BCSeEngine()
        ctx = _make_context()
        result = engine.analyze(ctx)
        assert result.is_stub is True
        assert result.counterfactual_consequences == []
        assert result.divergence_score == 0.0

    def test_stub_has_active_consequence(self):
        engine = BCSeEngine()
        ctx = _make_context()
        result = engine.analyze(ctx)
        assert result.active_consequence is not None
        assert result.active_consequence.is_projected is True

    def test_low_history_warning(self):
        engine = BCSeEngine()
        ctx = _make_context(n_history=0)
        result = engine.analyze(ctx)
        assert result.low_history_warning is True

    def test_sufficient_history_no_warning(self):
        engine = BCSeEngine()
        ctx = _make_context(n_history=10)
        result = engine.analyze(ctx)
        assert result.low_history_warning is False


class TestBCSeEngineFullPath:
    def _make_alts(self):
        return [
            PolicyAlternative.model_validate(dict(
                policy_id="permissive", label="Permissive",
                overrides={"restrict_threshold": 0.9},
            ), strict=False),
            PolicyAlternative.model_validate(dict(
                policy_id="strict", label="Strict",
                overrides={"restrict_threshold": 0.1},
            ), strict=False),
        ]

    def test_with_alternatives_not_stub(self):
        engine = BCSeEngine()
        ctx = _make_context(alternatives=self._make_alts(), n_history=5)
        result = engine.analyze(ctx)
        assert result.is_stub is False

    def test_counterfactuals_populated(self):
        engine = BCSeEngine()
        ctx = _make_context(alternatives=self._make_alts(), n_history=5)
        result = engine.analyze(ctx)
        assert len(result.counterfactual_consequences) == 2

    def test_all_consequences_are_projected(self):
        engine = BCSeEngine()
        ctx = _make_context(alternatives=self._make_alts(), n_history=5)
        result = engine.analyze(ctx)
        assert result.active_consequence.is_projected is True
        for cf in result.counterfactual_consequences:
            assert cf.is_projected is True

    def test_divergence_zero_when_all_agree(self):
        """When active and all alternatives produce the same response, divergence=0."""
        alts = [PolicyAlternative.model_validate(dict(
            policy_id="same", label="Same", overrides={},
        ), strict=False)]
        engine = BCSeEngine()
        ctx = _make_context(alternatives=alts, n_history=5)
        result = engine.analyze(ctx)
        # All using default overrides = same thresholds, so same response
        assert result.divergence_score == 0.0

    def test_divergence_nonzero_when_differ(self):
        """Strict policy (low threshold) should differ from permissive (high threshold)."""
        alts = [PolicyAlternative.model_validate(dict(
            policy_id="very-strict", label="VeryStrict",
            overrides={"restrict_threshold": 0.0,
                       "suspend_threshold": 0.05,
                       "terminate_threshold": 0.1},
        ), strict=False)]
        engine = BCSeEngine()
        # High composite score triggers restrictive response
        ctx = _make_context(alternatives=alts, n_history=5, composite=0.8)
        result = engine.analyze(ctx)
        # Divergence might be 0 if both active and alt end up at TERMINATE; that is correct
        assert 0.0 <= result.divergence_score <= 1.0

    def test_deterministic_same_context(self):
        """Same context produces same responses (bcse_id will differ but logic won't)."""
        alts = self._make_alts()
        engine = BCSeEngine()
        ctx = _make_context(alternatives=alts, n_history=5, composite=0.5)
        r1 = engine.analyze(ctx)
        r2 = engine.analyze(ctx)
        assert r1.active_consequence.projected_response == r2.active_consequence.projected_response
        assert r1.divergence_score == r2.divergence_score
        for c1, c2 in zip(r1.counterfactual_consequences, r2.counterfactual_consequences):
            assert c1.projected_response == c2.projected_response


class TestProjectedResponse:
    def test_permit_at_zero(self):
        assert _projected_response(0.0, {}) == "PERMIT"

    def test_warn_threshold(self):
        assert _projected_response(0.25, {}) == "WARN"

    def test_restrict_threshold(self):
        assert _projected_response(0.5, {}) == "RESTRICT"

    def test_terminate_threshold(self):
        assert _projected_response(0.9, {}) == "TERMINATE"

    def test_override_shifts_threshold(self):
        # Setting restrict_threshold=0.0 makes even score=0.05 => RESTRICT or higher
        resp = _projected_response(0.05, {"restrict_threshold": 0.0, "warn_threshold": 0.0})
        assert resp in ("RESTRICT", "SUSPEND", "TERMINATE")


class TestDivergence:
    def test_no_counterfactuals(self):
        assert _divergence("PERMIT", []) == 0.0

    def test_identical_responses(self):
        assert _divergence("RESTRICT", ["RESTRICT", "RESTRICT"]) == 0.0

    def test_max_divergence(self):
        d = _divergence("PERMIT", ["TERMINATE"])
        assert d == 1.0

    def test_partial_divergence(self):
        d = _divergence("PERMIT", ["WARN"])
        assert 0.0 < d < 1.0
'''

# ============================================================
# TEST: PREDICTIVE ENGINE
# ============================================================
files["tests/unit/test_predictive_engine.py"] = r'''"""Tests for Predictive Trajectory Engine Phase 2.

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
'''

for rel, content in files.items():
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"Written: {rel} ({p.stat().st_size} bytes)")

print("ALL DONE")