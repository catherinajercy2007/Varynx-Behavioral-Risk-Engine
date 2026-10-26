"""Capability Lease Manager.

Creates, evaluates, suspends, reinstates, revokes, and expires Capability_Lease
records. Enforces the four-state lifecycle. Cascades suspension and revocation
when triggered by ResponseRecommendation.

Satisfies: REQ-010
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from varynx.models.lease import CapabilityLease, LeaseEvaluation, LeaseState


class LeaseError(Exception):
    """Raised on invalid lease operations."""
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class LeaseManager:
    """In-memory Capability Lease Manager.

    Satisfies: REQ-010
    """

    def __init__(self) -> None:
        self._leases: dict[UUID, CapabilityLease] = {}

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def create_lease(
        self,
        agent_id: str,
        session_id: UUID,
        capability: str,
        resource_scope: dict,
        issuing_principal: str,
        issuing_policy_id: str,
        expiry_timestamp: datetime | None = None,
    ) -> CapabilityLease:
        """Create an ACTIVE capability lease (REQ-010.2)."""
        lease = CapabilityLease(
            lease_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            capability=capability,
            resource_scope=resource_scope,
            activation_timestamp=self._now(),
            expiry_timestamp=expiry_timestamp,
            issuing_principal=issuing_principal,
            issuing_policy_id=issuing_policy_id,
            state=LeaseState.ACTIVE,
            state_history=[
                {"state": "ACTIVE", "timestamp": self._now().isoformat(), "reason": "created"}
            ],
        )
        self._leases[lease.lease_id] = lease
        return lease

    def get_lease(self, lease_id: UUID) -> CapabilityLease | None:
        """Retrieve a lease by ID."""
        return self._leases.get(lease_id)

    def _transition(
        self, lease_id: UUID, new_state: LeaseState, reason: str
    ) -> CapabilityLease:
        """Apply a state transition to a lease, enforcing lifecycle rules."""
        lease = self._leases.get(lease_id)
        if lease is None:
            raise LeaseError("LEASE_NOT_FOUND", f"Lease {lease_id} not found")

        # REVOKED is terminal (REQ-010.6)
        if lease.state == LeaseState.REVOKED:
            raise LeaseError(
                "LEASE_REVOKED_TERMINAL",
                f"Lease {lease_id} is REVOKED; no further transitions permitted (REQ-010.6)",
            )

        history = list(lease.state_history) + [
            {"state": new_state.value, "timestamp": self._now().isoformat(), "reason": reason}
        ]
        updated = CapabilityLease.model_validate(
            {**lease.model_dump(), "state": new_state, "state_history": history},
            strict=False,
        )
        self._leases[lease_id] = updated
        return updated

    def suspend(self, lease_id: UUID, reason: str = "ResponseRecommendation:SUSPEND") -> CapabilityLease:
        """Suspend an ACTIVE lease (REQ-010.4)."""
        lease = self._leases.get(lease_id)
        if lease and lease.state != LeaseState.ACTIVE:
            raise LeaseError("INVALID_TRANSITION", f"Cannot suspend lease in state {lease.state}")
        return self._transition(lease_id, LeaseState.SUSPENDED, reason)

    def reinstate(self, lease_id: UUID, reason: str = "authorized_reinstatement") -> CapabilityLease:
        """Reinstate a SUSPENDED lease (REQ-010.7)."""
        lease = self._leases.get(lease_id)
        if lease and lease.state != LeaseState.SUSPENDED:
            raise LeaseError("INVALID_TRANSITION", f"Cannot reinstate lease in state {lease.state}")
        return self._transition(lease_id, LeaseState.ACTIVE, reason)

    def revoke(self, lease_id: UUID, reason: str = "ResponseRecommendation:TERMINATE") -> CapabilityLease:
        """Revoke a lease (REVOKED is terminal) (REQ-010.5, REQ-010.6)."""
        return self._transition(lease_id, LeaseState.REVOKED, reason)

    def expire(self, lease_id: UUID) -> CapabilityLease:
        """Expire a lease (REQ-010.3)."""
        return self._transition(lease_id, LeaseState.EXPIRED, "expiry_timestamp_reached")

    def check_expiry(self) -> list[CapabilityLease]:
        """Expire any ACTIVE leases past their expiry_timestamp. Returns expired leases."""
        now = self._now()
        expired = []
        for lease in list(self._leases.values()):
            if (
                lease.state == LeaseState.ACTIVE
                and lease.expiry_timestamp is not None
                and lease.expiry_timestamp <= now
            ):
                expired.append(self.expire(lease.lease_id))
        return expired

    def suspend_all_for_agent(self, agent_id: str) -> list[CapabilityLease]:
        """Suspend all ACTIVE leases for an agent (REQ-010.4).

        Used by SUSPEND enforcement — broad, affects every ACTIVE lease.
        See suspend_capability_for_agent() for the narrower RESTRICT path.
        """
        suspended = []
        for lease in list(self._leases.values()):
            if lease.agent_id == agent_id and lease.state == LeaseState.ACTIVE:
                suspended.append(self.suspend(lease.lease_id))
        return suspended

    def suspend_capability_for_agent(
        self, agent_id: str, capability: str
    ) -> list[CapabilityLease]:
        """Suspend ACTIVE leases whose capability matches the given capability string.

        Narrower than suspend_all_for_agent: only leases whose ``capability``
        field equals *capability* or for which *capability* starts with the
        lease's capability prefix are suspended.  Unrelated leases remain ACTIVE.

        Reuses the same capability-matching logic as ``evaluate()`` so the two
        stay consistent.

        Used by RESTRICT enforcement.  Returns the list of leases that were
        suspended (may be empty — callers must handle that case explicitly and
        must NOT return SUCCESS if the list is empty when a target was expected).
        """
        suspended = []
        for lease in list(self._leases.values()):
            if (
                lease.agent_id == agent_id
                and lease.state == LeaseState.ACTIVE
                and (
                    capability == lease.capability
                    or capability.startswith(lease.capability)
                )
            ):
                suspended.append(
                    self.suspend(
                        lease.lease_id,
                        reason=f"ResponseRecommendation:RESTRICT capability={capability}",
                    )
                )
        return suspended

    def revoke_all_for_agent(self, agent_id: str) -> list[CapabilityLease]:
        """Revoke all ACTIVE and SUSPENDED leases for an agent (REQ-010.5)."""
        revoked = []
        for lease in list(self._leases.values()):
            if lease.agent_id == agent_id and lease.state in (
                LeaseState.ACTIVE, LeaseState.SUSPENDED
            ):
                revoked.append(self.revoke(lease.lease_id))
        return revoked

    def evaluate(
        self,
        agent_id: str,
        capability: str,
        target_resource: str,
    ) -> LeaseEvaluation:
        """Evaluate whether a requested capability is covered by an ACTIVE lease.

        Satisfies: REQ-010
        """
        self.check_expiry()
        active_leases = [
            l for l in self._leases.values()
            if l.agent_id == agent_id and l.state == LeaseState.ACTIVE
        ]

        if not active_leases:
            return LeaseEvaluation(
                lease_id=None,
                is_active=False,
                capability_covered=False,
                reason="No ACTIVE leases found for agent",
            )

        for lease in active_leases:
            if capability == lease.capability or capability.startswith(lease.capability):
                return LeaseEvaluation(
                    lease_id=lease.lease_id,
                    is_active=True,
                    capability_covered=True,
                    reason=f"Covered by ACTIVE lease {lease.lease_id}",
                )

        return LeaseEvaluation(
            lease_id=None,
            is_active=True,
            capability_covered=False,
            reason=f"No ACTIVE lease covers capability '{capability}'",
        )

    def get_leases_for_agent(self, agent_id: str) -> list[CapabilityLease]:
        """List all leases for a given agent."""
        return [l for l in self._leases.values() if l.agent_id == agent_id]
