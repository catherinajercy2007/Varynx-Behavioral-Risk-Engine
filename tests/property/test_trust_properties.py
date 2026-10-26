"""Property-based tests for Trust Score (T10.1).

Verifies invariants:
- Output always in [0.0, 1.0]
- Score never increases in Phase 1 (no recovery)
- Zero-evidence bundle produces only decay delta

Satisfies: T10.1, REQ-005.2, design.md Section 8.4
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from varynx.config import TrustConfig
from varynx.engine.trust import TrustScorer, clamp, classify_trust_level
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustLevel


def _now():
    return datetime.now(UTC)


def make_bundle(composite: float = 0.0, records=None):
    return EvidenceBundle.model_validate({
        "bundle_id": str(uuid4()),
        "session_id": str(uuid4()),
        "agent_id": "agent-prop-001",
        "correlation_id": str(uuid4()),
        "records": records or [],
        "composite_score": composite,
        "correlation_window_seconds": 300.0,
        "timestamp": str(_now()),
        "is_simulated": True,
    }, strict=False)


@given(
    initial_score=st.floats(min_value=0.0, max_value=1.0),
    composite=st.floats(min_value=0.0, max_value=1.0),
    sensitivity=st.floats(min_value=0.01, max_value=5.0),
    session_age=st.floats(min_value=0.0, max_value=86400.0),
)
@settings(max_examples=300)
def test_trust_score_always_in_0_1(initial_score, composite, sensitivity, session_age):
    """Trust score is always in [0.0, 1.0] regardless of inputs (REQ-005.2)."""
    config = TrustConfig(sensitivity=sensitivity, initial_score=initial_score)
    scorer = TrustScorer(config=config)
    # Pre-seed state
    from varynx.engine.trust import classify_trust_level
    from varynx.models.trust import TrustState
    scorer._states["agent-prop-001"] = TrustState.model_validate({
        "session_id": str(uuid4()),
        "agent_id": "agent-prop-001",
        "current_score": initial_score,
        "level": classify_trust_level(initial_score, config).value,
        "last_updated": str(_now()),
    }, strict=False)
    bundle = make_bundle(composite=composite)
    result = scorer.update("agent-prop-001", uuid4(), bundle, session_age)
    assert 0.0 <= result.current_score <= 1.0, (
        f"Score {result.current_score} out of [0,1] for initial={initial_score}, "
        f"composite={composite}, sensitivity={sensitivity}"
    )


@given(
    initial_score=st.floats(min_value=0.001, max_value=1.0),
    composite=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_trust_score_never_increases_phase1(initial_score, composite):
    """Phase 1: trust score never increases (no recovery factor)."""
    config = TrustConfig(sensitivity=1.0, temporal_decay_rate=0.0, initial_score=initial_score)
    scorer = TrustScorer(config=config)
    from varynx.models.trust import TrustState
    scorer._states["agent-prop-001"] = TrustState.model_validate({
        "session_id": str(uuid4()),
        "agent_id": "agent-prop-001",
        "current_score": initial_score,
        "level": classify_trust_level(initial_score, config).value,
        "last_updated": str(_now()),
    }, strict=False)
    bundle = make_bundle(composite=composite)
    result = scorer.update("agent-prop-001", uuid4(), bundle, session_age_seconds=0.0)
    assert result.current_score <= initial_score + 1e-9, (
        f"Score increased: {initial_score} -> {result.current_score}"
    )


@given(
    initial_score=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_zero_evidence_bundle_produces_only_decay(initial_score):
    """Zero-evidence bundle: only temporal decay affects score."""
    config = TrustConfig(sensitivity=1.0, temporal_decay_rate=0.01, initial_score=initial_score)
    scorer = TrustScorer(config=config)
    from varynx.models.trust import TrustState
    scorer._states["ag"] = TrustState.model_validate({
        "session_id": str(uuid4()),
        "agent_id": "ag",
        "current_score": initial_score,
        "level": classify_trust_level(initial_score, config).value,
        "last_updated": str(_now()),
    }, strict=False)
    # Zero composite score = no evidence contribution
    bundle = make_bundle(composite=0.0)
    result = scorer.update("ag", uuid4(), bundle, session_age_seconds=3600.0)
    # With session_age=3600s, decay = 0.01 * 3600/3600 = 0.01
    expected = clamp(initial_score - 0.01)
    assert abs(result.current_score - expected) < 1e-9, (
        f"Expected {expected}, got {result.current_score}"
    )


def test_history_grows_by_one_per_update():
    """History length = prior + 1 after each update (design.md Section 8.4 invariant)."""
    scorer = TrustScorer()
    sid = uuid4()
    scorer.get_or_create_state("ag-hist", sid)
    for i in range(5):
        bundle = make_bundle(composite=0.1)
        state = scorer.update("ag-hist", sid, bundle)
        assert len(state.history) == i + 1


def test_trust_level_classification():
    """TrustLevel classification matches documented thresholds."""
    config = TrustConfig()
    assert classify_trust_level(1.0, config) == TrustLevel.HIGH
    assert classify_trust_level(0.85, config) == TrustLevel.HIGH
    assert classify_trust_level(0.84, config) == TrustLevel.ELEVATED
    assert classify_trust_level(0.65, config) == TrustLevel.ELEVATED
    assert classify_trust_level(0.64, config) == TrustLevel.GUARDED
    assert classify_trust_level(0.40, config) == TrustLevel.GUARDED
    assert classify_trust_level(0.39, config) == TrustLevel.LOW
    assert classify_trust_level(0.20, config) == TrustLevel.LOW
    assert classify_trust_level(0.19, config) == TrustLevel.CRITICAL
    assert classify_trust_level(0.0, config) == TrustLevel.CRITICAL
