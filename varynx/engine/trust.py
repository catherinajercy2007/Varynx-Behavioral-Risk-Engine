"""Dynamic Trust Module.

Maintains TrustState per agent; updates score using the deterministic formula;
classifies score into TrustLevel; appends TrustHistoryEntry per update.

Satisfies: REQ-005, REQ-021
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from varynx.config import TrustConfig
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustHistoryEntry, TrustLevel, TrustState

logger = logging.getLogger(__name__)


def classify_trust_level(score: float, config: TrustConfig) -> TrustLevel:
    """Map a trust score to a TrustLevel using configured thresholds.

    Satisfies: REQ-005.5
    """
    if score >= config.threshold_high:
        return TrustLevel.HIGH
    if score >= config.threshold_elevated:
        return TrustLevel.ELEVATED
    if score >= config.threshold_guarded:
        return TrustLevel.GUARDED
    if score >= config.threshold_low:
        return TrustLevel.LOW
    return TrustLevel.CRITICAL


def clamp(value: float) -> float:
    """Clamp a float value to [0.0, 1.0]. Logs if clamping occurs."""
    if value < 0.0:
        logger.warning("Trust score clamped from %f to 0.0", value)
        return 0.0
    if value > 1.0:
        logger.warning("Trust score clamped from %f to 1.0", value)
        return 1.0
    return value


class TrustScorer:
    """Computes and maintains TrustState per agent.

    Satisfies: REQ-005
    """

    def __init__(self, config: TrustConfig | None = None) -> None:
        self.config = config or TrustConfig()
        self._states: dict[str, TrustState] = {}

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def get_or_create_state(self, agent_id: str, session_id) -> TrustState:
        """Get or create a TrustState for the given agent."""
        if agent_id not in self._states:
            now = self._now()
            self._states[agent_id] = TrustState.model_validate(
                dict(
                    session_id=str(session_id),
                    agent_id=agent_id,
                    current_score=self.config.initial_score,
                    level=classify_trust_level(self.config.initial_score, self.config).value,
                    history=[],
                    last_updated=str(now),
                    session_age_seconds=0.0,
                ),
                strict=False,
            )
        return self._states[agent_id]

    def update(
        self,
        agent_id: str,
        session_id,
        evidence_bundle: EvidenceBundle,
        session_age_seconds: float = 0.0,
    ) -> TrustState:
        """Apply deterministic trust score update formula.

        Formula (design.md Section 8.4):
            new_score = clamp(
                current_score
                - (evidence_weight * anomaly_composite_score * sensitivity)
                - (temporal_decay_rate * session_age_seconds / 3600),
                0.0, 1.0
            )

        Invariants enforced:
        - Output always in [0.0, 1.0] (REQ-005.2)
        - Score never increases in Phase 1 (no recovery)
        - A zero-evidence bundle produces only a decay delta

        Satisfies: REQ-005
        """
        state = self.get_or_create_state(agent_id, session_id)

        # Compute evidence contribution (exclude EVIDENCE_DERIVATION_INCOMPLETE records)
        complete_records = [
            r for r in evidence_bundle.records
            if r.derivation_status == "COMPLETE"
        ]
        excluded_count = len(evidence_bundle.records) - len(complete_records)

        evidence_weight = sum(r.score * r.weight for r in complete_records)
        anomaly_composite = evidence_bundle.composite_score

        # Phase 1 deterministic formula
        delta = -(
            evidence_weight * anomaly_composite * self.config.sensitivity
            + self.config.temporal_decay_rate * session_age_seconds / 3600.0
        )

        new_score = clamp(state.current_score + delta)
        new_level = classify_trust_level(new_score, self.config)

        entry = TrustHistoryEntry.model_validate(
            dict(
                entry_id=str(uuid4()),
                timestamp=str(self._now()),
                prior_score=state.current_score,
                delta=delta,
                new_score=new_score,
                contributing_evidence_ids=[str(r.evidence_id) for r in complete_records],
                excluded_incomplete_count=excluded_count,
            ),
            strict=False,
        )

        new_history = list(state.history) + [entry]
        updated_state = TrustState.model_validate(
            dict(
                session_id=str(state.session_id),
                agent_id=agent_id,
                current_score=new_score,
                level=new_level.value,
                history=[h.model_dump() for h in new_history],
                last_updated=str(self._now()),
                session_age_seconds=session_age_seconds,
            ),
            strict=False,
        )
        self._states[agent_id] = updated_state
        return updated_state
