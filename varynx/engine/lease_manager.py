
"""Capability Lease Manager.

Creates, evaluates, suspends, reinstates, revokes, and expires Capability_Lease
records. Enforces the four-state lifecycle. Cascades suspension and revocation
when triggered by ResponseRecommendation.

Satisfies: REQ-010
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from varynx.engine.record_store import SQLiteRecordStore
from varynx.engine.resource_scope import (
    capability_is_covered,
    resource_is_within_scope,
    validate_resource_scope,
)
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

    def __init__(self, persistence_path: str | Path | None = None) -> None:
        self._leases: dict[UUID, CapabilityLease] = {}
        self._store = None
        if persistence_path is not None:
            root = Path(persistence_path)
            root.mkdir(parents=True, exist_ok=True)
            self._store = SQLiteRecordStore(root / "leases.sqlite3", "leases")
            self._leases = {
                UUID(key): CapabilityLease.model_validate_json(value)
                for key, value in self._store.load_all().items()
            }

    def _save_lease(self, lease: CapabilityLease) -> CapabilityLease:
        self._leases[lease.lease_id] = lease
        if self._store is not None:
            self._store.put(str(lease.lease_id), lease.model_dump_json())
        return lease

    def get_leases_for_session(self, session_id: UUID) -> list[CapabilityLease]:
        return [lease for lease in self._leases.values() if lease.session_id == session_id]

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

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
        """Create an ACTIVE capability lease (REQ-010.2).

        Invalid resource scopes are rejected before the lease is created.
        An empty resource scope is valid but grants access to no resources.
        """
        try:
            validate_resource_scope(resource_scope)
        except ValueError as exc:
            raise LeaseError(
                "INVALID_RESOURCE_SCOPE",
                str(exc),
            ) from exc

        now = self._now()

        lease = CapabilityLease(
            lease_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            capability=capability,
            resource_scope=resource_scope,
            activation_timestamp=now,
            expiry_timestamp=expiry_timestamp,
            issuing_principal=issuing_principal,
            issuing_policy_id=issuing_policy_id,
            state=LeaseState.ACTIVE,
            state_history=[
                {
                    "state": "ACTIVE",
                    "timestamp": now.isoformat(),
                    "reason": "created",
                }
            ],
        )

        return self._save_lease(lease)

    def get_lease(self, lease_id: UUID) -> CapabilityLease | None:
        """Retrieve a lease by ID."""
        return self._leases.get(lease_id)

    def _transition(
        self,
        lease_id: UUID,
        new_state: LeaseState,
        reason: str,
    ) -> CapabilityLease:
        """Apply a state transition to a lease, enforcing lifecycle rules."""
        lease = self._leases.get(lease_id)

        if lease is None:
            raise LeaseError(
                "LEASE_NOT_FOUND",
                f"Lease {lease_id} not found",
            )

        # REVOKED is terminal (REQ-010.6).
        if lease.state == LeaseState.REVOKED:
            raise LeaseError(
                "LEASE_REVOKED_TERMINAL",
                f"Lease {lease_id} is REVOKED; "
                "no further transitions permitted (REQ-010.6)",
            )

        history = list(lease.state_history) + [
            {
                "state": new_state.value,
                "timestamp": self._now().isoformat(),
                "reason": reason,
            }
        ]

        updated = CapabilityLease.model_validate(
            {
                **lease.model_dump(),
                "state": new_state,
                "state_history": history,
            },
            strict=False,
        )

        return self._save_lease(updated)

    def suspend(
        self,
        lease_id: UUID,
        reason: str = "ResponseRecommendation:SUSPEND",
    ) -> CapabilityLease:
        """Suspend an ACTIVE lease (REQ-010.4)."""
        lease = self._leases.get(lease_id)

        if lease and lease.state != LeaseState.ACTIVE:
            raise LeaseError(
                "INVALID_TRANSITION",
                f"Cannot suspend lease in state {lease.state}",
            )

        return self._transition(
            lease_id,
            LeaseState.SUSPENDED,
            reason,
        )

    def reinstate(
        self,
        lease_id: UUID,
        reason: str = "authorized_reinstatement",
    ) -> CapabilityLease:
        """Reinstate a SUSPENDED lease (REQ-010.7)."""
        lease = self._leases.get(lease_id)

        if lease and lease.state != LeaseState.SUSPENDED:
            raise LeaseError(
                "INVALID_TRANSITION",
                f"Cannot reinstate lease in state {lease.state}",
            )

        return self._transition(
            lease_id,
            LeaseState.ACTIVE,
            reason,
        )

    def revoke(
        self,
        lease_id: UUID,
        reason: str = "ResponseRecommendation:TERMINATE",
    ) -> CapabilityLease:
        """Revoke a lease (REQ-010.5, REQ-010.6)."""
        return self._transition(
            lease_id,
            LeaseState.REVOKED,
            reason,
        )

    def expire(self, lease_id: UUID) -> CapabilityLease:
        """Expire a lease (REQ-010.3)."""
        return self._transition(
            lease_id,
            LeaseState.EXPIRED,
            "expiry_timestamp_reached",
        )

    def check_expiry(self) -> list[CapabilityLease]:
        """Expire ACTIVE leases past their expiry timestamp.

        Returns the list of expired leases.
        """
        now = self._now()
        expired: list[CapabilityLease] = []

        for lease in list(self._leases.values()):
            if (
                lease.state == LeaseState.ACTIVE
                and lease.expiry_timestamp is not None
                and lease.expiry_timestamp <= now
            ):
                expired.append(self.expire(lease.lease_id))

        return expired

    def suspend_all_for_agent(
        self,
        agent_id: str,
    ) -> list[CapabilityLease]:
        """Suspend all ACTIVE leases for an agent (REQ-010.4).

        Used by SUSPEND enforcement. This broad operation affects every
        ACTIVE lease belonging to the specified agent.
        """
        suspended: list[CapabilityLease] = []

        for lease in list(self._leases.values()):
            if (
                lease.agent_id == agent_id
                and lease.state == LeaseState.ACTIVE
            ):
                suspended.append(self.suspend(lease.lease_id))

        return suspended

    def suspend_capability_for_agent(
        self,
        agent_id: str,
        capability: str,
    ) -> list[CapabilityLease]:
        """Suspend ACTIVE leases affected by a capability restriction.

        A lease is suspended when the restricted capability exactly matches
        its capability or is a delimiter-aware descendant of it.

        For example:
            Restriction: read:files
            Lease:       read:files          -> suspended
            Lease:       read:files:metadata -> suspended
            Lease:       read:filesX         -> not suspended

        This is narrower than suspend_all_for_agent().

        Used by RESTRICT enforcement. Returns the leases that were suspended.
        Callers must not report success when no expected target lease was
        suspended.
        """
        suspended: list[CapabilityLease] = []

        for lease in list(self._leases.values()):
            if (
                lease.agent_id == agent_id
                and lease.state == LeaseState.ACTIVE
                and capability_is_covered(capability, lease.capability)
            ):
                suspended.append(
                    self.suspend(
                        lease.lease_id,
                        reason=(
                            "ResponseRecommendation:RESTRICT "
                            f"capability={capability}"
                        ),
                    )
                )

        return suspended

    def revoke_all_for_agent(
        self,
        agent_id: str,
    ) -> list[CapabilityLease]:
        """Revoke ACTIVE and SUSPENDED leases for an agent (REQ-010.5)."""
        revoked: list[CapabilityLease] = []

        for lease in list(self._leases.values()):
            if (
                lease.agent_id == agent_id
                and lease.state in (
                    LeaseState.ACTIVE,
                    LeaseState.SUSPENDED,
                )
            ):
                revoked.append(self.revoke(lease.lease_id))

        return revoked

    def evaluate(
        self,
        agent_id: str,
        capability: str,
        target_resource: str,
        session_id: UUID | None = None,
    ) -> LeaseEvaluation:
        """Evaluate capability AND resource authorization.

        Authorization succeeds only when an ACTIVE, unexpired lease:

        1. Belongs to the requested agent.
        2. When supplied, belongs to the requested session.
        3. Covers the requested capability using delimiter-aware matching.
        4. Covers the target resource using delimiter-aware scope matching.

        Empty resource scopes, missing target resources, and unmatched
        capabilities or resources are denied.

        Satisfies: REQ-010
        """
        # Fail closed when no target resource is provided.
        if not target_resource:
            return LeaseEvaluation(
                lease_id=None,
                is_active=False,
                capability_covered=False,
                reason=(
                    "No target resource specified; "
                    "authorization denied"
                ),
            )

        # Expire overdue leases before evaluating authorization.
        self.check_expiry()

        active_leases = [
            lease
            for lease in self._leases.values()
            if (
                lease.agent_id == agent_id
                and lease.state == LeaseState.ACTIVE
                and (session_id is None or lease.session_id == session_id)
            )
        ]

        if not active_leases:
            return LeaseEvaluation(
                lease_id=None,
                is_active=False,
                capability_covered=False,
                reason="No ACTIVE leases found for agent",
            )

        for lease in active_leases:
            # 1. Capability must be covered.
            if not capability_is_covered(
                capability,
                lease.capability,
            ):
                continue

            # 2. Resource must be covered by the lease scope.
            scope = lease.resource_scope or {}

            roots = (
                scope.get("resources", [])
                if isinstance(scope, dict)
                else []
            )

            # Empty scope means deny-all.
            if not roots:
                continue

            if not resource_is_within_scope(
                target_resource,
                roots,
            ):
                continue

            # Both capability and resource are covered.
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
            reason=(
                f"No ACTIVE lease covers capability '{capability}' "
                f"and resource '{target_resource}'"
            ),
        )

    def get_leases_for_agent(
        self,
        agent_id: str,
    ) -> list[CapabilityLease]:
        """List all leases for a given agent."""
        return [
            lease
            for lease in self._leases.values()
            if lease.agent_id == agent_id
        ]
