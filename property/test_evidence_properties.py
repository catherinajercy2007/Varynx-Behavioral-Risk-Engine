"""Property-based tests for Evidence Engine (T10.2).

Satisfies: T10.2, REQ-003, REQ-004
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from varynx.engine.evidence import (
    EvidenceEngine,
    compute_content_hash,
    make_evidence_record_with_hash,
    verify_record_integrity,
)
from varynx.models.evidence import AnomalyClass, EvidenceRecord


def _now():
    return datetime.now(UTC)


def make_evidence_record(score=0.5, weight=0.5, status="COMPLETE"):
    """Create an EvidenceRecord with a correct content_hash via canonical serialization."""
    data = dict(
        evidence_id=str(uuid4()), event_id=str(uuid4()), session_id=str(uuid4()),
        agent_id="ag", correlation_id=str(uuid4()),
        anomaly_class=AnomalyClass.ACTION_FREQUENCY.value,
        score=score, weight=weight, detector_id="test",
        timestamp=str(_now()), is_simulated=True, derivation_status=status,
    )
    return make_evidence_record_with_hash(data)


@given(
    score=st.floats(min_value=0.0, max_value=1.0),
    weight=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=200)
def test_evidence_record_score_weight_in_range(score, weight):
    """All score/weight fields are in [0.0, 1.0]."""
    rec = make_evidence_record(score=score, weight=weight)
    assert 0.0 <= rec.score <= 1.0
    assert 0.0 <= rec.weight <= 1.0


@given(
    score=st.floats(min_value=0.0, max_value=1.0),
    weight=st.floats(min_value=0.001, max_value=1.0),
)
@settings(max_examples=100)
def test_content_hash_is_deterministic(score, weight):
    """Same content always produces same hash (determinism)."""
    data = {
        "evidence_id": "fixed-id",
        "score": score,
        "weight": weight,
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    h1 = compute_content_hash(data)
    h2 = compute_content_hash(data)
    assert h1 == h2


def test_integrity_check_passes_on_unmodified_record():
    """verify_record_integrity returns True for an unmodified record."""
    rec = make_evidence_record()
    assert verify_record_integrity(rec) is True, (
        f"Hash verification failed. stored={rec.content_hash}"
    )


def test_integrity_check_fails_on_tampered_score():
    """verify_record_integrity returns False when score is changed without rehashing."""
    rec = make_evidence_record(score=0.3)
    tampered_data = rec.model_dump(mode="json")
    tampered_data["score"] = 0.9  # Changed without updating hash
    tampered = EvidenceRecord.model_validate(tampered_data, strict=False)
    assert verify_record_integrity(tampered) is False


def test_incomplete_records_excluded_from_composite():
    """EVIDENCE_DERIVATION_INCOMPLETE records do not contribute to composite score."""
    engine = EvidenceEngine()
    complete = [make_evidence_record(score=0.8, weight=1.0, status="COMPLETE")]
    score = engine._compute_composite_score(complete)
    assert score == pytest.approx(0.8, abs=1e-6)


def test_composite_score_in_range():
    """Composite score always in [0.0, 1.0]."""
    engine = EvidenceEngine()
    records = [make_evidence_record(score=s, weight=w)
               for s, w in [(0.9, 0.8), (0.5, 0.5), (0.1, 0.3)]]
    score = engine._compute_composite_score(records)
    assert 0.0 <= score <= 1.0


def test_six_detectors_registered():
    """Evidence engine has exactly 6 detectors."""
    engine = EvidenceEngine()
    assert len(engine._detectors) == 6
    detector_ids = {d.detector_id for d in engine._detectors}
    expected = {"capability_escalation", "resource_anomaly", "action_frequency",
                "authorization_bypass", "context_deviation", "temporal_anomaly"}
    assert detector_ids == expected
