"""Adaptive response (Security_Decision) models.

Satisfies: REQ-009, REQ-011
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from varynx.models.trust import TrustLevel, TrustState


class ResponseType(str, Enum):
    """Enumerated response directives for the Enforcement_Boundary.

    Satisfies: REQ-009.2
    """

    PERMIT = "PERMIT"
    WARN = "WARN"
    RESTRICT = "RESTRICT"
    SUSPEND = "SUSPEND"
    TERMINATE = "TERMINATE"
    ESCALATE = "ESCALATE"


class ReasonCode(BaseModel):
    """Machine-readable basis for a Security_Decision.

    Satisfies: REQ-009.2
    """

    model_config = ConfigDict(strict=True)

    code: str
    """Enumerated reason code string (e.g. 'TRUST_LEVEL_CRITICAL')."""

    description: str
    contributing_evidence_ids: list[UUID] = Field(default_factory=list)
    """Only IDs resolvable in evidence store (REQ-008.3)."""

    trust_level_at_recommendation: TrustLevel
    severity: str
    """'INFO' | 'WARNING' | 'CRITICAL'"""


class ResponseRecommendation(BaseModel):
    """A Security_Decision: a recommendation to the Enforcement_Boundary.

    NEVER labeled as an enforcement outcome. Satisfies: REQ-009
    """

    model_config = ConfigDict(strict=True)

    recommendation_id: UUID
    agent_id: str
    correlation_id: UUID
    """Propagated from originating Behavioral_Event (REQ-012.1)."""

    response_type: ResponseType
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    evidence_bundle_id: UUID
    trust_state_snapshot: TrustState
    bcse_result_id: UUID | None = None
    trajectory_projection_id: UUID | None = None
    rationale: str
    """Natural language explanation; must cite Evidence_Record IDs (REQ-008.2)."""

    timestamp: datetime
    policy_id: str
    policy_version: str
    """Policy table version at decision time (REQ-011.6)."""

    target_capability: str | None = None
    """The specific capability that triggered this recommendation.

    Required for RESTRICT enforcement: the enforcement layer suspends only
    leases covering this capability rather than all agent leases.
    Required for ESCALATE: recorded in the escalation audit payload.
    None means the target was not specified; enforcement will record
    UNRESOLVED rather than claiming a false SUCCESS (REQ-022).
    """

    target_resource: str | None = None
    """The target resource involved in the triggering event.

    Carried for audit context. May be used by enforcement to narrow scope.
    """
