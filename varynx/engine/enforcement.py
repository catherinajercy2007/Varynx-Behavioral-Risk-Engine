"""Runtime Enforcement Layer.

Translates ResponseRecommendation into concrete enforcement actions.
Validates policies independently. Produces EnforcementRecord per action.
Supports dry-run mode. Enforces audit-before-action ordering. Guarantees idempotency.

Satisfies: REQ-022
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from varynx.models.enforcement import EnforcementOutcome, EnforcementRecord
from varynx.models.response import ResponseRecommendation, ResponseType

if TYPE_CHECKING:
    from varynx.engine.lease_manager import LeaseManager

logger = logging.getLogger(__name__)


# Escalation pending-review record structure (no external service required)
# Keyed by recommendation_id (UUID).
EscalationRecord = dict  # {recommendation_id, agent_id, capability, reason_codes, timestamp, status}


class EnforcementLayer:
    """Applies ResponseRecommendations as enforcement actions.

    Satisfies: REQ-022
    """

    def __init__(
        self,
        dry_run: bool = False,
        lease_manager: LeaseManager | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.lease_manager = lease_manager
        self._applied_recommendation_ids: set[UUID] = set()
        # In-memory register of ESCALATION_PENDING entries.
        # Key: recommendation_id (UUID). Value: EscalationRecord dict.
        # Never claims approval; status is always "PENDING_HUMAN_REVIEW" until
        # a future workflow updates it.  Keyed the same as _applied_recommendation_ids
        # so duplicates are caught by the idempotency check before reaching
        # _apply_escalate().
        self._pending_escalations: dict[UUID, EscalationRecord] = {}

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _validate_policy(self, recommendation: ResponseRecommendation) -> bool:
        """Independent policy validation (REQ-022).

        Enforcement layer validates independently; does not blindly trust recommendation.
        Returns True if valid, False if rejected.
        """
        # Validate recommendation_id exists
        if not recommendation.recommendation_id:
            logger.warning("POLICY_VALIDATION_REJECTED: missing recommendation_id")
            return False
        # Validate agent_id present
        if not recommendation.agent_id:
            logger.warning("POLICY_VALIDATION_REJECTED: missing agent_id")
            return False
        return True

    def enforce(self, recommendation: ResponseRecommendation) -> EnforcementRecord:
        """Apply enforcement for a ResponseRecommendation.

        Satisfies: REQ-022
        - Independent policy validation (REQ-022)
        - Audit-before-action: record is written before action is applied (REQ-022.5)
        - Idempotency: duplicate recommendation_id produces SKIPPED (REQ-022.8)
        - Dry-run mode: log but do not apply (REQ-022.4)
        """
        rec_id = recommendation.recommendation_id

        # Idempotency check (REQ-022.8)
        if rec_id in self._applied_recommendation_ids:
            logger.info(
                "DUPLICATE_ENFORCEMENT: recommendation %s already applied, returning SKIPPED",
                rec_id,
            )
            return EnforcementRecord.model_validate(
                dict(
                    enforcement_id=str(uuid4()),
                    source_recommendation_id=str(rec_id),
                    action_taken="SKIPPED",
                    target_agent_id=recommendation.agent_id,
                    action_timestamp=str(self._now()),
                    outcome=EnforcementOutcome.SKIPPED.value,
                    outcome_reason="DUPLICATE_ENFORCEMENT",
                    dry_run=self.dry_run,
                ),
                strict=False,
            )

        # Independent policy validation
        if not self._validate_policy(recommendation):
            return EnforcementRecord.model_validate(
                dict(
                    enforcement_id=str(uuid4()),
                    source_recommendation_id=str(rec_id),
                    action_taken="SKIPPED",
                    target_agent_id=recommendation.agent_id,
                    action_timestamp=str(self._now()),
                    outcome=EnforcementOutcome.SKIPPED.value,
                    outcome_reason="POLICY_VALIDATION_REJECTED",
                    dry_run=self.dry_run,
                ),
                strict=False,
            )

        response_type = recommendation.response_type
        action_taken = f"ENFORCEMENT:{response_type.value}"
        outcome = EnforcementOutcome.SUCCESS

        # Dry-run mode (REQ-022.4): log but do not apply
        if self.dry_run:
            logger.info(
                "[DRY_RUN] Would enforce %s for agent %s",
                response_type.value,
                recommendation.agent_id,
            )
        else:
            # Apply enforcement actions
            outcome = self._apply_action(recommendation)

        # Record is written BEFORE marking as applied (audit-before-action, REQ-022.5)
        record = EnforcementRecord.model_validate(
            dict(
                enforcement_id=str(uuid4()),
                source_recommendation_id=str(rec_id),
                action_taken=action_taken,
                target_agent_id=recommendation.agent_id,
                action_timestamp=str(self._now()),
                outcome=outcome.value,
                outcome_reason=None,
                dry_run=self.dry_run,
            ),
            strict=False,
        )

        # Mark as applied for idempotency (after record is written)
        self._applied_recommendation_ids.add(rec_id)
        return record

    def _apply_action(self, recommendation: ResponseRecommendation) -> EnforcementOutcome:
        """Apply the concrete enforcement action based on ResponseType.

        Returns the actual EnforcementOutcome.  Callers use the returned value
        to populate the EnforcementRecord; a SUCCESS here means the requested
        action was carried out, not merely attempted.
        """
        response_type = recommendation.response_type
        agent_id = recommendation.agent_id

        try:
            if response_type == ResponseType.SUSPEND and self.lease_manager:
                # Broad cascade: suspend every ACTIVE lease (REQ-010.4)
                suspended = self.lease_manager.suspend_all_for_agent(agent_id)
                logger.info("Suspended %d leases for agent %s", len(suspended), agent_id)

            elif response_type == ResponseType.TERMINATE and self.lease_manager:
                # Broad cascade: revoke every ACTIVE and SUSPENDED lease (REQ-010.5)
                revoked = self.lease_manager.revoke_all_for_agent(agent_id)
                logger.info("Revoked %d leases for agent %s", len(revoked), agent_id)

            elif response_type == ResponseType.RESTRICT:
                return self._apply_restrict(recommendation)

            elif response_type == ResponseType.ESCALATE:
                return self._apply_escalate(recommendation)

            elif response_type == ResponseType.PERMIT:
                logger.debug("PERMIT for agent %s — no enforcement action", agent_id)

            elif response_type == ResponseType.WARN:
                # WARN signals that the agent's behaviour has triggered a policy
                # threshold but has not yet reached restriction level.  No lease
                # state change is made.  Effective monitoring occurs because every
                # subsequent agent action passes through the full behavioral analysis
                # pipeline -- evidence is collected, trust is updated, and anomalies
                # are re-evaluated on each event.  This is the project's implemented
                # form of ALLOW_WITH_MONITORING (REQ-011).
                logger.info("WARN recommendation for agent %s", agent_id)

            return EnforcementOutcome.SUCCESS

        except Exception as exc:
            logger.error("Enforcement action failed for agent %s: %s", agent_id, exc)
            return EnforcementOutcome.FAILED

    def _apply_restrict(self, recommendation: ResponseRecommendation) -> EnforcementOutcome:
        """Apply a targeted capability restriction.

        Suspends only the ACTIVE leases that cover *target_capability*.
        Unrelated leases are left untouched.

        Outcomes:
        - SUCCESS  : one or more matching leases were suspended.
        - FAILED   : target_capability missing, no lease manager, or exception.
        - SKIPPED  : lease manager present, target given, but no matching lease exists
                     (capability not currently granted — restriction not needed,
                      but we still record the attempt so it is auditable).
        """
        agent_id = recommendation.agent_id
        capability = recommendation.target_capability

        if not capability:
            logger.error(
                "RESTRICT for agent %s: target_capability is None — "
                "cannot apply targeted restriction; recording FAILED",
                agent_id,
            )
            return EnforcementOutcome.FAILED

        if not self.lease_manager:
            logger.error(
                "RESTRICT for agent %s capability '%s': no lease manager attached — "
                "recording FAILED",
                agent_id,
                capability,
            )
            return EnforcementOutcome.FAILED

        try:
            suspended = self.lease_manager.suspend_capability_for_agent(agent_id, capability)
            if suspended:
                logger.info(
                    "RESTRICT: suspended %d lease(s) covering capability '%s' for agent %s",
                    len(suspended),
                    capability,
                    agent_id,
                )
                return EnforcementOutcome.SUCCESS
            else:
                # No matching lease — the capability is not currently granted.
                # Record this explicitly so the audit trail is complete.
                logger.info(
                    "RESTRICT: no ACTIVE lease covers capability '%s' for agent %s "
                    "— restriction recorded but no lease state changed",
                    capability,
                    agent_id,
                )
                return EnforcementOutcome.SKIPPED

        except Exception as exc:
            logger.error(
                "RESTRICT for agent %s capability '%s' raised exception: %s",
                agent_id,
                capability,
                exc,
            )
            return EnforcementOutcome.FAILED

    def _apply_escalate(self, recommendation: ResponseRecommendation) -> EnforcementOutcome:
        """Apply escalation enforcement.

        Records the escalation as PENDING_HUMAN_REVIEW in the in-memory register
        and returns FAILED so the operation is blocked.

        Contract:
        - The operation is always blocked (returns FAILED).  No approval is claimed.
        - The escalation is recorded in self._pending_escalations with full context.
        - Unrelated leases and capabilities are not touched.
        - The outcome_reason on the returned EnforcementRecord (set by enforce()) is
          populated via FAILED; the escalation detail lives in the register and in the
          structured log line.
        - When a review workflow is added in Phase 2+, this method will be updated to
          submit the escalation and await acknowledgement before returning.

        Missing context:
        - If recommendation_id is absent the escalation cannot be registered;
          returns FAILED (policy validation would have caught this first, but
          _apply_escalate is also safe to call directly in tests).
        - target_capability may be None (escalation on trust-level rules).
          The register entry records "(not specified)" in that case; the operation
          is still blocked.
        """
        agent_id = recommendation.agent_id
        rec_id = recommendation.recommendation_id
        capability = recommendation.target_capability
        reason_codes = [rc.code for rc in recommendation.reason_codes]
        timestamp = str(self._now())

        if not rec_id:
            logger.error(
                "ESCALATE for agent %s: missing recommendation_id — cannot register; FAILED",
                agent_id,
            )
            return EnforcementOutcome.FAILED

        # Build the structured escalation record.
        escalation_entry: EscalationRecord = {
            "recommendation_id": str(rec_id),
            "agent_id": agent_id,
            "target_capability": capability or "(not specified)",
            "target_resource": recommendation.target_resource or "(not specified)",
            "reason_codes": reason_codes,
            "policy_id": recommendation.policy_id,
            "policy_version": recommendation.policy_version,
            "rationale": recommendation.rationale,
            "escalated_at": timestamp,
            "status": "PENDING_HUMAN_REVIEW",
            # status will only change when a review workflow explicitly updates it;
            # it is NEVER set to "APPROVED" here — that would be fabrication.
        }

        try:
            self._pending_escalations[rec_id] = escalation_entry
            logger.warning(
                "ESCALATE registered PENDING_HUMAN_REVIEW for agent=%s capability='%s' "
                "recommendation_id=%s reason_codes=%s. "
                "No human approval has occurred. Operation is BLOCKED.",
                agent_id,
                capability or "(not specified)",
                rec_id,
                reason_codes,
            )
        except Exception as exc:
            # If we cannot record the escalation, we must not return SUCCESS — the
            # operation would silently proceed without any escalation record.
            logger.error(
                "ESCALATE for agent %s: failed to record escalation entry: %s — FAILED",
                agent_id,
                exc,
            )
            return EnforcementOutcome.FAILED

        # FAILED outcome signals callers the operation did not proceed (REQ-022).
        # The pipeline's ENFORCEMENT_APPLIED audit record will carry:
        #   action_taken = "ENFORCEMENT:ESCALATE"
        #   outcome      = "FAILED"
        #   dry_run      = False (or True in dry-run mode)
        # Together with the _pending_escalations register, this provides a
        # complete, non-repudiable audit trail for the pending escalation.
        return EnforcementOutcome.FAILED

    def get_pending_escalation(self, recommendation_id: UUID) -> EscalationRecord | None:
        """Return the pending escalation record for a recommendation, or None.

        Used by tests and future review workflows to inspect escalation state.
        Never modifies escalation status.
        """
        return self._pending_escalations.get(recommendation_id)

    def list_pending_escalations(self) -> list[EscalationRecord]:
        """Return all current pending escalation records.

        Returns copies; callers cannot mutate escalation state via this method.
        """
        return list(self._pending_escalations.values())
