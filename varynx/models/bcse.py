"""BCSE (Behavioral Counterfactual Security Evaluation) models.

Satisfies: REQ-007, REQ-008
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from varynx.models.event import AgentActionEvent

# Forward-referenced imports resolved at runtime
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustState


class PolicyAlternative(BaseModel):
    """A hypothetical policy configuration for BCSE counterfactual analysis."""

    model_config = ConfigDict(strict=True)

    policy_id: str
    label: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    """Declarative delta from active policy."""


class ConsequenceProjection(BaseModel):
    """A single projected consequence for one policy configuration.

    ALL fields describe projections, never observed facts.
    Satisfies: REQ-007.4
    """

    model_config = ConfigDict(strict=True)

    policy_id: str
    projected_response: str
    """Projected ResponseType string (avoids circular import with response module)."""

    projected_trust_impact: float
    """Estimated delta to trust score."""

    risk_level: str
    """'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN'"""

    uncertainty_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    """Natural language explanation; must cite Evidence_Record IDs (REQ-008.1)."""

    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    """Only IDs that exist in the evidence store (REQ-008.3)."""

    is_projected: bool = True
    """ALWAYS True. Never an observed fact (REQ-007.4)."""

    projection_basis: str = ""
    """Description of historical window used for projection."""


class BCSeContext(BaseModel):
    """Input to BCSE evaluation. Read-only snapshot.

    Satisfies: REQ-007.3 — BCSE never modifies any of these.
    """

    model_config = ConfigDict(strict=True)

    context_id: UUID
    proposed_action: AgentActionEvent
    evidence_bundle: EvidenceBundle
    trust_state: TrustState
    active_policy_id: str
    alternative_policies: list[PolicyAlternative] = Field(default_factory=list)


class BCSeResult(BaseModel):
    """Output of BCSE evaluation.

    Satisfies: REQ-007.2
    """

    model_config = ConfigDict(strict=True)

    bcse_id: UUID
    context_id: UUID
    agent_id: str
    evaluation_timestamp: datetime
    active_consequence: ConsequenceProjection
    counterfactual_consequences: list[ConsequenceProjection] = Field(default_factory=list)
    """Empty in Phase 1 stub."""

    divergence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    """0.0 in Phase 1 stub."""

    analysis_timestamp: datetime
    is_stub: bool = True
    """True in Phase 1. Set to False in Phase 2 full implementation."""

    low_history_warning: bool = False
    """True when agent has fewer events than configured minimum (REQ-007.5)."""
