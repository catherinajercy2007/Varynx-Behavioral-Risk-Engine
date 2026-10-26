"""Runtime enforcement models.

Satisfies: REQ-022
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EnforcementOutcome(str, Enum):
    """Result of a runtime enforcement action."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EnforcementRecord(BaseModel):
    """Record of what the enforcement layer did with a ResponseRecommendation.

    Satisfies: REQ-022.3
    """

    model_config = ConfigDict(strict=True)

    enforcement_id: UUID
    source_recommendation_id: UUID
    """Links back to ResponseRecommendation (REQ-012.1)."""

    action_taken: str
    target_agent_id: str
    target_resource_scope: str | None = None
    action_timestamp: datetime
    outcome: EnforcementOutcome
    outcome_reason: str | None = None
    """e.g. 'POLICY_VALIDATION_REJECTED', 'DUPLICATE_ENFORCEMENT' (REQ-022.7, REQ-022.8)."""

    dry_run: bool = False
    """True in dry-run mode. Dry-run records never used for trust computation (REQ-022.4)."""
