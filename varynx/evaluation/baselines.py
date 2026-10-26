"""Baseline Comparisons B1–B3.

B1: Always-PERMIT baseline (never flags any event)
B2: Rule-based single-dimension baseline (only authorization_bypass)
B3: Session-average trust (compute trust at session end only)

Satisfies: REQ-015, H1
"""
from __future__ import annotations

from varynx.models.event import AgentActionEvent, AuthorizationResult


class BaselineB1AlwaysPermit:
    """B1: Always-PERMIT. No detection, no trust degradation.

    Represents the null hypothesis — every event is permitted regardless of content.
    """
    name = "B1_always_permit"

    def evaluate(self, event: AgentActionEvent) -> dict:
        return {
            "baseline": self.name,
            "response": "PERMIT",
            "anomaly_detected": False,
            "trust_score": 1.0,
        }


class BaselineB2SingleDimension:
    """B2: Single-dimension rule-based baseline.

    Only detects repeated authorization denials (AUTHORIZATION_BYPASS_ATTEMPT).
    Does not use behavioral evidence, trust scoring, or trajectory analysis.
    Threshold: 3 denials within a session.
    """
    name = "B2_single_dimension"

    def __init__(self) -> None:
        self._denial_counts: dict[str, int] = {}

    def evaluate(self, event: AgentActionEvent) -> dict:
        agent_id = event.agent_id
        if event.authorization_result == AuthorizationResult.DENIED:
            self._denial_counts[agent_id] = self._denial_counts.get(agent_id, 0) + 1

        count = self._denial_counts.get(agent_id, 0)
        detected = count >= 3
        return {
            "baseline": self.name,
            "response": "RESTRICT" if detected else "PERMIT",
            "anomaly_detected": detected,
            "anomaly_class": "AUTHORIZATION_BYPASS_ATTEMPT" if detected else None,
            "denial_count": count,
        }


class BaselineB3SessionAverage:
    """B3: Session-average trust scoring.

    Computes trust only at session end (average of event-level signals).
    Does not use per-event dynamic trust updates.
    """
    name = "B3_session_average"

    def __init__(self, denial_weight: float = 0.3) -> None:
        self.denial_weight = denial_weight
        self._session_signals: dict[str, list[float]] = {}

    def evaluate(self, event: AgentActionEvent) -> dict:
        agent_id = event.agent_id
        if agent_id not in self._session_signals:
            self._session_signals[agent_id] = []

        # Signal: 0.0 for denied, 1.0 for allowed
        signal = 0.0 if event.authorization_result == AuthorizationResult.DENIED else 1.0
        self._session_signals[agent_id].append(signal)

        return {
            "baseline": self.name,
            "response": "PERMIT",
            "anomaly_detected": False,
            "session_event_count": len(self._session_signals[agent_id]),
            "note": "Trust computed at session end only",
        }

    def finalize_session(self, agent_id: str) -> dict:
        """Compute final session-average trust score."""
        signals = self._session_signals.get(agent_id, [])
        if not signals:
            return {"agent_id": agent_id, "avg_trust": 1.0, "response": "PERMIT"}
        avg = sum(signals) / len(signals)
        return {
            "agent_id": agent_id,
            "avg_trust": round(avg, 4),
            "response": "RESTRICT" if avg < 0.5 else "PERMIT",
        }
