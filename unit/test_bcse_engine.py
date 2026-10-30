"""Tests for BCSE Phase 2 Engine.

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
        s = max(0.1, 0.7 - i * 0.05)
        entries.append(TrustHistoryEntry.model_validate(dict(
            entry_id=str(uuid4()), timestamp=datetime.now(UTC).isoformat(),
            prior_score=min(1.0, s + 0.05), delta=-0.05, new_score=s,
            contributing_evidence_ids=[], excluded_incomplete_count=0,
        ), strict=False))
    cur = max(0.1, 0.7 - (n_history - 1) * 0.05) if n_history > 0 else score
    return TrustState.model_validate(dict(
        session_id=str(uuid4()), agent_id=agent_id,
        current_score=cur, level=TrustLevel.ELEVATED.value,
        history=[e.model_dump() for e in entries],
        last_updated=datetime.now(UTC).isoformat(), session_age_seconds=0.0,
    ), strict=False)


def _make_record(composite=0.1, agent_id="test-agent"):
    uid = str(uuid4())
    return EvidenceRecord.model_validate(dict(
        evidence_id=uid, event_id=str(uuid4()),
        session_id=str(uuid4()), agent_id=agent_id,
        correlation_id=str(uuid4()),
        anomaly_class=AnomalyClass.CAPABILITY_ESCALATION.value,
        score=composite, weight=1.0,
        detector_id="capability_escalation_detector",
        contributing_signals=[], provenance={},
        timestamp=datetime.now(UTC).isoformat(),
        is_simulated=True,
        content_hash="aabbccdd",
        derivation_status="COMPLETE",
    ), strict=False)


def _make_bundle(composite=0.1, n_records=1, agent_id="test-agent"):
    records = [_make_record(composite, agent_id) for _ in range(n_records)]
    return EvidenceBundle.model_validate(dict(
        bundle_id=str(uuid4()), agent_id=agent_id,
        session_id=str(uuid4()), correlation_id=str(uuid4()),
        records=[r.model_dump() for r in records],
        composite_score=composite,
        correlation_window_seconds=300.0,
        timestamp=datetime.now(UTC).isoformat(),
        is_simulated=True,
    ), strict=False)


def _make_context(agent_id="test-agent", composite=0.1, n_history=0,
                   alternatives=None):
    return BCSeContext.model_validate(dict(
        context_id=str(uuid4()),
        proposed_action=_make_event(agent_id).model_dump(),
        evidence_bundle=_make_bundle(composite, agent_id=agent_id).model_dump(),
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
        """When active and all alternatives use identical thresholds, same response => div=0."""
        alts = [PolicyAlternative.model_validate(dict(
            policy_id="same", label="Same", overrides={},
        ), strict=False)]
        engine = BCSeEngine()
        ctx = _make_context(alternatives=alts, n_history=5)
        result = engine.analyze(ctx)
        # Same overrides as active => same response => divergence=0
        assert result.divergence_score == 0.0

    def test_divergence_in_range(self):
        """Divergence is always [0.0, 1.0]."""
        alts = [PolicyAlternative.model_validate(dict(
            policy_id="very-strict", label="VeryStrict",
            overrides={"restrict_threshold": 0.0,
                       "suspend_threshold": 0.05,
                       "terminate_threshold": 0.1},
        ), strict=False)]
        engine = BCSeEngine()
        ctx = _make_context(alternatives=alts, n_history=5, composite=0.8)
        result = engine.analyze(ctx)
        assert 0.0 <= result.divergence_score <= 1.0

    def test_deterministic_same_context(self):
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
