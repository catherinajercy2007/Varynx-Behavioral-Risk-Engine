"""Behavioral Evidence Engine and Detector Protocol.

Orchestrates the configurable detector pipeline, derives EvidenceRecord instances,
correlates records, computes composite_score, bundles into EvidenceBundle,
and computes cryptographic hash per record.

Satisfies: REQ-003, REQ-004
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from varynx.config import EvidenceConfig
from varynx.models.agent import SessionContext
from varynx.models.event import AuthorizationResult, ValidatedEvent
from varynx.models.evidence import AnomalyClass, EvidenceBundle, EvidenceRecord
from varynx.models.lease import LeaseEvaluation

logger = logging.getLogger(__name__)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Hash utilities (T3.3 Ã¢â‚¬â€ Evidence Integrity Hashing)
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def compute_content_hash(record_data: dict) -> str:
    """Compute SHA-256 of a record's canonical JSON representation.

    Canonical = sorted keys, no whitespace (deterministic).
    Satisfies: REQ-003.6
    """
    canonical = json.dumps(record_data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_record_hash(record: EvidenceRecord) -> str:
    """Compute content hash from an EvidenceRecord using normalized JSON serialization.

    Uses model_dump(mode="json") so UUID/datetime types are consistently serialized
    as strings matching the canonical JSON format.
    """
    data = record.model_dump(mode="json")
    data.pop("content_hash", None)  # exclude the hash field itself
    return compute_content_hash(data)


def verify_record_integrity(record: EvidenceRecord) -> bool:
    """Verify EvidenceRecord content hash.

    Recomputes hash from stored content and compares against stored content_hash.
    Returns False on mismatch (INTEGRITY_VIOLATION). Satisfies: REQ-014
    """
    stored_hash = record.content_hash
    recomputed = compute_record_hash(record)
    return recomputed == stored_hash


def make_evidence_record_with_hash(data: dict) -> EvidenceRecord:
    """Create an EvidenceRecord with a correct content_hash.

    Creates the record first (without hash), then computes the hash from the
    normalized model_dump, then updates content_hash. This ensures the hash
    is always computed from the same canonical representation that verify uses.
    """
    data["content_hash"] = "pending"  # placeholder
    record = EvidenceRecord.model_validate(data, strict=False)
    correct_hash = compute_record_hash(record)
    # Update the record with the correct hash
    updated_data = record.model_dump(mode="json")
    updated_data["content_hash"] = correct_hash
    return EvidenceRecord.model_validate(updated_data, strict=False)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Per-agent state (needed for sliding window detectors)
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class AgentEventHistory:
    """Lightweight rolling history for sliding-window detectors."""

    def __init__(self) -> None:
        self.denial_timestamps: list[datetime] = []
        self.action_timestamps: list[datetime] = []
        self.task_ids: set[str] = set()


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Detector implementations (T3.2 Ã¢â‚¬â€ Six Anomaly Detectors)
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class CapabilityEscalationDetector:
    """Detects capability escalation: action outside declared scope.

    Satisfies: REQ-002.4, design.md Section 4.4 (capability_escalation detector)
    """
    detector_id = "capability_escalation"
    anomaly_class = AnomalyClass.CAPABILITY_ESCALATION
    enabled = True

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
    ) -> EvidenceRecord | None:
        if not config.enable_capability_escalation:
            return None
        if not session_context.capability_escalation_detected:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=0.8,
            weight=0.9,
            detector_id=self.detector_id,
            contributing_signals=["action_type", "declared_capability_scope"],
            provenance={
                "method": "scope_comparison",
                "action_type": event.action_type.value,
                "declared_scope": session_context.agent_record.declared_capability_scope,
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


class ResourceAnomalyDetector:
    """Detects resource spread exceeding domain threshold within time window.

    Satisfies: REQ-004.3, REQ-006.4
    """
    detector_id = "resource_anomaly"
    anomaly_class = AnomalyClass.RESOURCE_ANOMALY
    enabled = True

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
    ) -> EvidenceRecord | None:
        if not config.enable_resource_anomaly:
            return None
        spread_count = len(session_context.session_record.resource_spread)
        if spread_count <= config.resource_spread_threshold:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=min(1.0, (spread_count - config.resource_spread_threshold) / config.resource_spread_threshold),
            weight=0.7,
            detector_id=self.detector_id,
            contributing_signals=["target_resource", "resource_spread"],
            provenance={
                "method": "spread_threshold_check",
                "spread_count": spread_count,
                "threshold": config.resource_spread_threshold,
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


class ActionFrequencyDetector:
    """Detects action rate exceeding threshold within sliding window.

    Satisfies: REQ-004
    """
    detector_id = "action_frequency"
    anomaly_class = AnomalyClass.ACTION_FREQUENCY
    enabled = True

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
        history: AgentEventHistory | None = None,
    ) -> EvidenceRecord | None:
        if not config.enable_action_frequency:
            return None
        if history is None:
            return None

        now = event.timestamp
        window_start = now.timestamp() - config.action_frequency_window_seconds
        recent = [t for t in history.action_timestamps if t.timestamp() >= window_start]
        count = len(recent) + 1  # +1 for current event

        if count <= config.action_frequency_threshold:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=min(1.0, count / config.action_frequency_threshold - 1.0),
            weight=0.6,
            detector_id=self.detector_id,
            contributing_signals=["timestamp", "action_count"],
            provenance={
                "method": "sliding_window_frequency",
                "action_count": count,
                "window_seconds": config.action_frequency_window_seconds,
                "threshold": config.action_frequency_threshold,
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


class AuthorizationBypassDetector:
    """Detects repeated authorization denials within a configurable window.

    Satisfies: REQ-004.2
    """
    detector_id = "authorization_bypass"
    anomaly_class = AnomalyClass.AUTHORIZATION_BYPASS_ATTEMPT
    enabled = True

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
        history: AgentEventHistory | None = None,
    ) -> EvidenceRecord | None:
        if not config.enable_authorization_bypass:
            return None

        if event.authorization_result != AuthorizationResult.DENIED:
            return None  # Not a denial event

        if history is None:
            return None

        now = event.timestamp
        window_start = now.timestamp() - config.authz_denial_window_seconds
        recent_denials = [t for t in history.denial_timestamps if t.timestamp() >= window_start]
        count = len(recent_denials) + 1  # +1 for current denial

        if count < config.authz_denial_threshold:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=min(1.0, count / config.authz_denial_threshold * 0.8),
            weight=0.9,
            detector_id=self.detector_id,
            contributing_signals=["authorization_result"],
            provenance={
                "method": "denial_window_count",
                "denial_count": count,
                "window_seconds": config.authz_denial_window_seconds,
                "threshold": config.authz_denial_threshold,
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


class ContextDeviationDetector:
    """Detects cross-context behavioral correlation: same agent correlated to 2+ task contexts.

    Satisfies: REQ-004.4
    """
    detector_id = "context_deviation"
    anomaly_class = AnomalyClass.CONTEXT_DEVIATION
    enabled = True

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
        history: AgentEventHistory | None = None,
    ) -> EvidenceRecord | None:
        if not config.enable_context_deviation:
            return None
        if history is None or event.task_id is None:
            return None

        history.task_ids.add(event.task_id)
        if len(history.task_ids) < 2:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=min(1.0, len(history.task_ids) / 5.0),
            weight=0.75,
            detector_id=self.detector_id,
            contributing_signals=["task_id"],
            provenance={
                "method": "cross_context_correlation",
                "distinct_task_ids": len(history.task_ids),
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


class TemporalAnomalyDetector:
    """Detects actions at statistically unusual times relative to historical pattern.

    Phase 1: simple hour-of-day heuristic. Phase 2: statistical model.
    Satisfies: design.md Section 4.4 (temporal_anomaly detector)
    """
    detector_id = "temporal_anomaly"
    anomaly_class = AnomalyClass.TEMPORAL_ANOMALY
    enabled = True

    # "Business hours" heuristic: 00:00-06:00 UTC is off-hours
    OFF_HOURS = frozenset(range(0, 6))

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: EvidenceConfig,
    ) -> EvidenceRecord | None:
        if not config.enable_temporal_anomaly:
            return None

        hour = event.timestamp.hour
        if hour not in self.OFF_HOURS:
            return None

        data = dict(
            evidence_id=str(uuid4()),
            event_id=str(event.event_id),
            session_id=str(event.session_id),
            agent_id=event.agent_id,
            correlation_id=str(event.correlation_id),
            anomaly_class=self.anomaly_class.value,
            score=0.3,  # Low score; heuristic-only in Phase 1
            weight=0.4,
            detector_id=self.detector_id,
            contributing_signals=["timestamp"],
            provenance={
                "method": "off_hours_heuristic",
                "hour_utc": hour,
                "off_hours_range": "00:00-06:00 UTC",
                "note": "Phase 1 heuristic. Phase 2 will use statistical model.",
            },
            timestamp=str(datetime.now(UTC)),
            is_simulated=event.is_simulated,
            derivation_status="COMPLETE",
        )
        data["content_hash"] = compute_content_hash(data)
        return EvidenceRecord.model_validate(data, strict=False)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Evidence Engine orchestrator
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class EvidenceEngine:
    """Orchestrates all six anomaly detectors and produces an EvidenceBundle.

    Satisfies: REQ-003, REQ-004, design.md Section 4.4
    """

    def __init__(self, config: EvidenceConfig | None = None) -> None:
        self.config = config or EvidenceConfig()
        self._agent_histories: dict[str, AgentEventHistory] = {}
        self._detectors = [
            CapabilityEscalationDetector(),
            ResourceAnomalyDetector(),
            ActionFrequencyDetector(),
            AuthorizationBypassDetector(),
            ContextDeviationDetector(),
            TemporalAnomalyDetector(),
        ]

    def _get_history(self, agent_id: str) -> AgentEventHistory:
        if agent_id not in self._agent_histories:
            self._agent_histories[agent_id] = AgentEventHistory()
        return self._agent_histories[agent_id]

    def _update_history(self, event: ValidatedEvent, history: AgentEventHistory) -> None:
        history.action_timestamps.append(event.timestamp)
        if event.authorization_result == AuthorizationResult.DENIED:
            history.denial_timestamps.append(event.timestamp)

    def process(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
    ) -> EvidenceBundle:
        """Run all detectors, collect evidence records, produce an EvidenceBundle.

        Satisfies: REQ-004.7 Ã¢â‚¬â€ detector errors are logged and skipped, never propagated.
        Satisfies: REQ-003.4 Ã¢â‚¬â€ EVIDENCE_DERIVATION_INCOMPLETE records excluded from scoring.
        """
        history = self._get_history(event.agent_id)
        records: list[EvidenceRecord] = []

        for detector in self._detectors:
            try:
                result: EvidenceRecord | None = None
                if detector.detector_id in ("action_frequency", "authorization_bypass", "context_deviation"):
                    result = detector.detect(  # type: ignore[call-arg]
                        event, session_context, lease_evaluation, self.config, history
                    )
                else:
                    result = detector.detect(event, session_context, lease_evaluation, self.config)

                if result is not None:
                    records.append(result)
            except Exception as exc:
                logger.error(
                    "Detector %s raised exception for event %s: %s",
                    detector.detector_id,
                    event.event_id,
                    exc,
                    exc_info=True,
                )
                # Create EVIDENCE_DERIVATION_INCOMPLETE record (REQ-004.7, REQ-003.4)
                data = dict(
                    evidence_id=str(uuid4()),
                    event_id=str(event.event_id),
                    session_id=str(event.session_id),
                    agent_id=event.agent_id,
                    correlation_id=str(event.correlation_id),
                    anomaly_class=AnomalyClass.ACTION_FREQUENCY.value,  # placeholder
                    score=0.0,
                    weight=0.0,
                    detector_id=detector.detector_id,
                    contributing_signals=[],
                    provenance={"error": str(exc), "method": "error_fallback"},
                    timestamp=str(datetime.now(UTC)),
                    is_simulated=event.is_simulated,
                    derivation_status="EVIDENCE_DERIVATION_INCOMPLETE",
                )
                data["content_hash"] = compute_content_hash(data)
                records.append(EvidenceRecord.model_validate(data, strict=False))

        self._update_history(event, history)

        # Compute composite score from complete records only (REQ-003.4)
        complete_records = [r for r in records if r.derivation_status == "COMPLETE"]
        composite_score = self._compute_composite_score(complete_records)

        return EvidenceBundle.model_validate(
            dict(
                bundle_id=str(uuid4()),
                session_id=str(event.session_id),
                agent_id=event.agent_id,
                correlation_id=str(event.correlation_id),
                records=[r.model_dump() for r in records],
                composite_score=composite_score,
                correlation_window_seconds=self.config.correlation_window_seconds,
                timestamp=str(datetime.now(UTC)),
                is_simulated=event.is_simulated,
            ),
            strict=False,
        )

    def _compute_composite_score(self, records: list[EvidenceRecord]) -> float:
        """Weighted composite score normalized to [0.0, 1.0].

        Formula: sum(score * weight) / max(sum(weight), 1.0)
        """
        if not records:
            return 0.0
        total_weight = sum(r.weight for r in records)
        if total_weight == 0.0:
            return 0.0
        weighted_sum = sum(r.score * r.weight for r in records)
        return min(1.0, weighted_sum / total_weight)
