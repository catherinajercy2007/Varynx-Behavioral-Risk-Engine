"""Fail-closed simulated resource gateway for Varynx.

This gateway performs in-memory READ/WRITE/DELETE operations only. It does not
access the host filesystem, S3, AWS, or external services.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from enum import Enum
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from varynx.engine.audit import AuditStore
from varynx.engine.lease_manager import LeaseManager
from varynx.models.audit import AuditRecordType


class ResourceOperation(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"


class ResourceOperationRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    agent_id: str
    capability: str
    target_resource: str
    operation: ResourceOperation
    value: Any = None
    request_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID | None = None
    session_id: UUID | None = None


class ResourceOperationResult(BaseModel):
    model_config = ConfigDict(strict=True)

    request_id: UUID
    authorized: bool
    executed: bool
    status: str
    reason: str
    value: Any = None


class SQLiteIdempotencyStore:
    """Durable request ledger for replay protection.

    IN_PROGRESS records are not automatically retried. Call
    recover_incomplete() only during controlled startup after confirming that
    no previous worker can still be executing; those records become
    INDETERMINATE and require reconciliation or a fresh request ID.
    """

    def __init__(self, database_path: str) -> None:
        import sqlite3
        from pathlib import Path

        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self.database_path, timeout=30.0, check_same_thread=False
        )
        self._connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_records (
                request_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('IN_PROGRESS', 'COMPLETED', 'INDETERMINATE')
                ),
                result_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._connection.commit()

    def claim(self, request_id: UUID, fingerprint: str) -> tuple[str, ResourceOperationResult | None]:
        """Claim a new ID or return its durable existing state."""
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    """
                    SELECT fingerprint, status, result_json
                    FROM idempotency_records WHERE request_id = ?
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    self._connection.execute(
                        """
                        INSERT INTO idempotency_records
                            (request_id, fingerprint, status)
                        VALUES (?, ?, 'IN_PROGRESS')
                        """,
                        (str(request_id), fingerprint),
                    )
                    self._connection.commit()
                    return "NEW", None

                stored_fingerprint, status, result_json = row
                self._connection.commit()
                if stored_fingerprint != fingerprint:
                    return "CONFLICT", None
                if status == "COMPLETED":
                    return (
                        "COMPLETED",
                        ResourceOperationResult.model_validate_json(result_json),
                    )
                return status, None
            except Exception:
                self._connection.rollback()
                raise

    def complete(
        self, request_id: UUID, fingerprint: str, result: ResourceOperationResult
    ) -> None:
        """Persist the terminal result for a claimed request."""
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'COMPLETED', result_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND fingerprint = ? AND status = 'IN_PROGRESS'
                """,
                (result.model_dump_json(), str(request_id), fingerprint),
            )
            self._connection.commit()
            if cursor.rowcount != 1:
                raise RuntimeError("IDEMPOTENCY_STATE_CONFLICT: request was not in progress")

    def mark_indeterminate(self, request_id: UUID, fingerprint: str) -> None:
        """Mark an operation whose completion could not be durably confirmed."""
        with self._lock:
            self._connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'INDETERMINATE', updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND fingerprint = ? AND status = 'IN_PROGRESS'
                """,
                (str(request_id), fingerprint),
            )
            self._connection.commit()

    def recover_incomplete(self) -> int:
        """Mark abandoned in-progress requests indeterminate; never replay them."""
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'INDETERMINATE', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'IN_PROGRESS'
                """
            )
            self._connection.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class SimulatedResourceGateway:
    """Execute operations against an explicitly seeded in-memory catalogue.

    A request must pass BOTH independent gates:
    1. An active lease must cover the requested capability and resource.
    2. The caller must explicitly pass behavioral_permit=True.

    The gateway intentionally does not infer behavioral approval from a
    missing value. This keeps the default fail-closed.
    """

    def __init__(
        self,
        lease_manager: LeaseManager,
        audit_store: AuditStore,
        resources: dict[str, Any] | None = None,
        idempotency_store: SQLiteIdempotencyStore | None = None,
    ) -> None:
        self.lease_manager = lease_manager
        self.audit_store = audit_store
        self._resources = deepcopy(resources or {})
        self._request_lock = RLock()
        self._request_results: dict[UUID, tuple[str, ResourceOperationResult]] = {}
        self.idempotency_store = idempotency_store

    def snapshot(self) -> dict[str, Any]:
        """Return a defensive copy of the simulated resource catalogue."""
        return deepcopy(self._resources)

    def execute(
        self,
        request: ResourceOperationRequest,
        *,
        behavioral_permit: bool = False,
    ) -> ResourceOperationResult:
        """Execute once per request ID with optional durable replay protection.

        The durable ledger is at-most-once: an interrupted operation is never
        automatically retried. A result may be INDETERMINATE if execution may
        have started but completion was not durably recorded.
        """
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "request": request.model_dump(mode="json"),
                    "behavioral_permit": behavioral_permit,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        with self._request_lock:
            if self.idempotency_store is None:
                previous = self._request_results.get(request.request_id)
                if previous is not None:
                    previous_fingerprint, previous_result = previous
                    if previous_fingerprint == fingerprint:
                        self._audit(
                            request,
                            "RESOURCE_REQUEST_REPLAYED",
                            "IDEMPOTENT_RESULT_RETURNED",
                        )
                        return previous_result.model_copy(deep=True)

                    reason = "REQUEST_ID_REUSED_WITH_DIFFERENT_PAYLOAD"
                    self._audit(request, "RESOURCE_REQUEST_REPLAY_CONFLICT", reason)
                    return ResourceOperationResult(
                        request_id=request.request_id,
                        authorized=False,
                        executed=False,
                        status="REPLAY_CONFLICT",
                        reason=reason,
                    )

                result = self._execute_once(
                    request, behavioral_permit=behavioral_permit
                )
                self._request_results[request.request_id] = (
                    fingerprint, result.model_copy(deep=True)
                )
                return result

            claim_status, stored_result = self.idempotency_store.claim(
                request.request_id, fingerprint
            )
            if claim_status == "COMPLETED" and stored_result is not None:
                self._audit(
                    request,
                    "RESOURCE_REQUEST_REPLAYED",
                    "DURABLE_IDEMPOTENT_RESULT_RETURNED",
                )
                return stored_result.model_copy(deep=True)
            if claim_status == "CONFLICT":
                reason = "REQUEST_ID_REUSED_WITH_DIFFERENT_PAYLOAD"
                self._audit(request, "RESOURCE_REQUEST_REPLAY_CONFLICT", reason)
                return ResourceOperationResult(
                    request_id=request.request_id,
                    authorized=False,
                    executed=False,
                    status="REPLAY_CONFLICT",
                    reason=reason,
                )
            if claim_status == "IN_PROGRESS":
                reason = "REQUEST_ALREADY_IN_PROGRESS: outcome is not yet available"
                self._audit(request, "RESOURCE_REQUEST_IN_PROGRESS", reason)
                return ResourceOperationResult(
                    request_id=request.request_id,
                    authorized=False,
                    executed=False,
                    status="IN_PROGRESS",
                    reason=reason,
                )
            if claim_status == "INDETERMINATE":
                reason = (
                    "OPERATION_OUTCOME_UNKNOWN: reconcile before issuing "
                    "a new request"
                )
                self._audit(request, "RESOURCE_REQUEST_INDETERMINATE", reason)
                return ResourceOperationResult(
                    request_id=request.request_id,
                    authorized=False,
                    executed=False,
                    status="INDETERMINATE",
                    reason=reason,
                )
            if claim_status != "NEW":
                raise RuntimeError(f"UNKNOWN_IDEMPOTENCY_STATE: {claim_status}")

            try:
                result = self._execute_once(
                    request, behavioral_permit=behavioral_permit
                )
                self.idempotency_store.complete(
                    request.request_id, fingerprint, result
                )
                return result
            except Exception:
                self.idempotency_store.mark_indeterminate(
                    request.request_id, fingerprint
                )
                raise

    def _execute_once(
        self,
        request: ResourceOperationRequest,
        *,
        behavioral_permit: bool,
    ) -> ResourceOperationResult:
        """Authorize, audit, and optionally execute one new operation."""
        self.audit_store.append(
            record_type=AuditRecordType.ENFORCEMENT_APPLIED,
            source_entity_id=str(request.request_id),
            payload={
                "stage": "RESOURCE_REQUEST_RECEIVED",
                "operation": request.operation.value,
            },
            correlation_id=request.correlation_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
        )

        if request.session_id is None:
            reason = "SESSION_REQUIRED: resource operations must identify a session"
            self._audit(request, "RESOURCE_ACCESS_DENIED", reason)
            return ResourceOperationResult(
                request_id=request.request_id,
                authorized=False,
                executed=False,
                status="DENIED",
                reason=reason,
            )

        lease_eval = self.lease_manager.evaluate(
            agent_id=request.agent_id,
            capability=request.capability,
            target_resource=request.target_resource,
            session_id=request.session_id,
        )
        authorized = bool(
            lease_eval.is_active and lease_eval.capability_covered
        )

        if not authorized:
            reason = f"LEASE_DENIED: {lease_eval.reason}"
            self._audit(request, "RESOURCE_ACCESS_DENIED", reason)
            return ResourceOperationResult(
                request_id=request.request_id,
                authorized=False,
                executed=False,
                status="DENIED",
                reason=reason,
            )

        if not behavioral_permit:
            reason = "BEHAVIORAL_GATE_DENIED: explicit behavioral approval required"
            self._audit(request, "RESOURCE_ACCESS_HELD", reason)
            return ResourceOperationResult(
                request_id=request.request_id,
                authorized=True,
                executed=False,
                status="HELD",
                reason=reason,
            )

        # Audit the authorization before touching simulated resource state.
        self._audit(request, "RESOURCE_ACCESS_AUTHORIZED", "LEASE_AND_BEHAVIORAL_GATES_PASSED")

        if request.target_resource not in self._resources:
            reason = "RESOURCE_NOT_FOUND"
            self._audit(request, "RESOURCE_OPERATION_FAILED", reason)
            return ResourceOperationResult(
                request_id=request.request_id,
                authorized=True,
                executed=False,
                status="NOT_FOUND",
                reason=reason,
            )

        try:
            if request.operation == ResourceOperation.READ:
                value = deepcopy(self._resources[request.target_resource])
            elif request.operation == ResourceOperation.WRITE:
                self._resources[request.target_resource] = deepcopy(request.value)
                value = None
            elif request.operation == ResourceOperation.DELETE:
                del self._resources[request.target_resource]
                value = None
            else:  # Defensive; Pydantic enum validation should make this unreachable.
                raise ValueError("UNSUPPORTED_OPERATION")
        except Exception as exc:
            reason = f"OPERATION_FAILED: {type(exc).__name__}"
            self._audit(request, "RESOURCE_OPERATION_FAILED", reason)
            return ResourceOperationResult(
                request_id=request.request_id,
                authorized=True,
                executed=False,
                status="FAILED",
                reason=reason,
            )

        self._audit(request, "RESOURCE_OPERATION_EXECUTED", "SUCCESS")
        return ResourceOperationResult(
            request_id=request.request_id,
            authorized=True,
            executed=True,
            status="EXECUTED",
            reason="AUTHORIZED_AND_EXECUTED",
            value=value,
        )

    def _audit(
        self,
        request: ResourceOperationRequest,
        stage: str,
        reason: str,
    ) -> None:
        self.audit_store.append(
            record_type=AuditRecordType.ENFORCEMENT_APPLIED,
            source_entity_id=str(request.request_id),
            payload={
                "stage": stage,
                "operation": request.operation.value,
                "reason": reason,
            },
            correlation_id=request.correlation_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
        )
