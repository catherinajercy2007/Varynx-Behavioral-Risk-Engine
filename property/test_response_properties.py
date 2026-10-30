"""Property-based tests for Adaptive Response Engine (T10.3).

Satisfies: T10.3, REQ-009, REQ-011
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from varynx.engine.response import _SEVERITY_ORDER, AdaptiveResponseEngine
from varynx.models.evidence import EvidenceBundle
from varynx.models.response import ResponseType
from varynx.models.trust import TrustLevel, TrustState


def _now():
    return datetime.now(UTC)


def make_trust_state(score=0.7, level=TrustLevel.ELEVATED):
    return TrustState.model_validate({
        "session_id": str(uuid4()), "agent_id": "ag",
        "current_score": score, "level": level.value,
        "last_updated": str(_now()),
    }, strict=False)


def make_bundle(composite=0.0):
    return EvidenceBundle.model_validate({
        "bundle_id": str(uuid4()), "session_id": str(uuid4()),
        "agent_id": "ag", "correlation_id": str(uuid4()),
        "composite_score": composite, "correlation_window_seconds": 300.0,
        "timestamp": str(_now()), "is_simulated": True,
    }, strict=False)


def test_response_type_from_enumerated_set():
    """Every recommendation uses a ResponseType from the enumerated set (REQ-009.2)."""
    engine = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    bundle = make_bundle(0.0)
    for level in TrustLevel:
        ts = make_trust_state(score=0.5, level=level)
        rec = engine.recommend("ag", uuid4(), bundle, ts)
        assert rec.response_type in ResponseType


def test_determinism_identical_inputs():
    """Identical inputs produce identical outputs (REQ-009.3)."""
    engine1 = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    engine2 = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    bundle = make_bundle(0.3)
    ts = make_trust_state(0.15, TrustLevel.CRITICAL)
    rec1 = engine1.recommend("ag1", uuid4(), bundle, ts)
    rec2 = engine2.recommend("ag2", uuid4(), bundle, ts)
    # Same trust level + same policy → same response type
    assert rec1.response_type == rec2.response_type


def test_critical_trust_triggers_terminate():
    """CRITICAL trust level → TERMINATE response (policy rule 1)."""
    engine = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    ts = make_trust_state(score=0.05, level=TrustLevel.CRITICAL)
    rec = engine.recommend("ag-crit", uuid4(), make_bundle(0.9), ts)
    assert rec.response_type == ResponseType.TERMINATE


def test_escalation_monotonicity_never_de_escalates():
    """Engine never recommends lower severity without explicit de-escalation (REQ-011.5)."""
    engine = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    # First: get TERMINATE for CRITICAL
    ts_critical = make_trust_state(0.05, TrustLevel.CRITICAL)
    rec1 = engine.recommend("ag-mono", uuid4(), make_bundle(0.9), ts_critical)
    assert rec1.response_type == ResponseType.TERMINATE
    # Second: trust "recovers" — but without de-escalation event, must stay TERMINATE
    ts_good = make_trust_state(0.9, TrustLevel.HIGH)
    rec2 = engine.recommend("ag-mono", uuid4(), make_bundle(0.0), ts_good)
    terminate_ord = _SEVERITY_ORDER[ResponseType.TERMINATE.value]
    rec2_ord = _SEVERITY_ORDER[rec2.response_type.value]
    assert rec2_ord >= terminate_ord, f"De-escalated without explicit event: {rec2.response_type}"


def test_de_escalation_allowed_after_explicit_event():
    """After de_escalate(), response can fall below prior level."""
    engine = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    ts_critical = make_trust_state(0.05, TrustLevel.CRITICAL)
    engine.recommend("ag-deesc", uuid4(), make_bundle(0.9), ts_critical)
    engine.de_escalate("ag-deesc")
    ts_good = make_trust_state(0.9, TrustLevel.HIGH)
    rec = engine.recommend("ag-deesc", uuid4(), make_bundle(0.0), ts_good)
    assert rec.response_type in (ResponseType.PERMIT, ResponseType.WARN)


def test_policy_table_invalid_fallback():
    """Invalid policy → WARN (MONITOR) fallback and POLICY_TABLE_INVALID logged (REQ-011.7).

    REQ-011.7 requires MONITOR (mapped to WARN in this codebase) as the fallback,
    not PERMIT.  PERMIT was a defect -- it silently allowed all requests when the
    policy table was missing or corrupt.  WARN preserves operation continuity while
    making the policy failure visible in the recommendation's reason codes.
    """
    engine = AdaptiveResponseEngine(policy_path=None)
    engine._policy_invalid = True
    ts = make_trust_state(0.5, TrustLevel.GUARDED)
    rec = engine.recommend("ag-inv", uuid4(), make_bundle(0.0), ts)
    # Fallback is WARN per REQ-011.7 (MONITOR, not PERMIT)
    assert rec.response_type == ResponseType.WARN, (
        f"Expected WARN fallback per REQ-011.7, got {rec.response_type}"
    )
    assert any(rc.code == "POLICY_TABLE_INVALID" for rc in rec.reason_codes)


def test_recommendation_includes_required_fields():
    """ResponseRecommendation has all required fields (REQ-009.1)."""
    engine = AdaptiveResponseEngine(policy_path="config/default_policy.yaml")
    ts = make_trust_state(0.7, TrustLevel.ELEVATED)
    rec = engine.recommend("ag-fields", uuid4(), make_bundle(0.0), ts)
    assert rec.recommendation_id is not None
    assert rec.agent_id == "ag-fields"
    assert rec.correlation_id is not None
    assert rec.response_type is not None
    assert rec.rationale
    assert rec.policy_id
    assert rec.policy_version
    assert rec.timestamp is not None
