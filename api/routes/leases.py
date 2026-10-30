"""Capability Leases API.

Satisfies: REQ-010, REQ-016
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response
from varynx.engine.lease_manager import LeaseError
from varynx.models.audit import AuditRecordType

router = APIRouter()

def get_pipeline(request: Request):
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class LeaseCreateRequest(BaseModel):
    agent_id: str
    session_id: UUID
    capability: str
    resource_scope: dict = {}
    issuing_principal: str
    issuing_policy_id: str = "default"
    expiry_timestamp: datetime | None = None

@router.post("/leases", summary="Grant a capability lease")
async def create_lease(body: LeaseCreateRequest, request: Request):
    pipeline = get_pipeline(request)
    lease = pipeline.lease_manager.create_lease(
        agent_id=body.agent_id,
        session_id=body.session_id,
        capability=body.capability,
        resource_scope=body.resource_scope,
        issuing_principal=body.issuing_principal,
        issuing_policy_id=body.issuing_policy_id,
        expiry_timestamp=body.expiry_timestamp,
    )
    pipeline.audit_store.append(
        record_type=AuditRecordType.LEASE_STATE_CHANGED,
        source_entity_id=str(lease.lease_id),
        payload={"state": "ACTIVE", "capability": body.capability},
        agent_id=body.agent_id,
    )
    return success_response(lease.model_dump())

@router.get("/leases/{lease_id}", summary="Get lease record")
async def get_lease(lease_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    lease = pipeline.lease_manager.get_lease(lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail=error_response("LEASE_NOT_FOUND", f"Lease {lease_id} not found"))
    return success_response(lease.model_dump())

@router.patch("/leases/{lease_id}/suspend", summary="Suspend an ACTIVE lease")
async def suspend_lease(lease_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    try:
        lease = pipeline.lease_manager.suspend(lease_id)
    except LeaseError as e:
        raise HTTPException(status_code=409, detail=error_response(e.reason_code, str(e)))
    pipeline.audit_store.append(
        record_type=AuditRecordType.LEASE_STATE_CHANGED,
        source_entity_id=str(lease_id),
        payload={"state": "SUSPENDED"},
        agent_id=lease.agent_id,
    )
    return success_response(lease.model_dump())

@router.patch("/leases/{lease_id}/reinstate", summary="Reinstate a SUSPENDED lease")
async def reinstate_lease(lease_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    try:
        lease = pipeline.lease_manager.reinstate(lease_id, reason="API_REINSTATE")
    except LeaseError as e:
        raise HTTPException(status_code=409, detail=error_response(e.reason_code, str(e)))
    pipeline.audit_store.append(
        record_type=AuditRecordType.LEASE_STATE_CHANGED,
        source_entity_id=str(lease_id),
        payload={"state": "ACTIVE", "reason": "reinstatement"},
        agent_id=lease.agent_id,
    )
    return success_response(lease.model_dump())

@router.delete("/leases/{lease_id}", summary="Revoke a lease")
async def revoke_lease(lease_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    try:
        lease = pipeline.lease_manager.revoke(lease_id, reason="API_REVOKE")
    except LeaseError as e:
        raise HTTPException(status_code=409, detail=error_response(e.reason_code, str(e)))
    pipeline.audit_store.append(
        record_type=AuditRecordType.LEASE_STATE_CHANGED,
        source_entity_id=str(lease_id),
        payload={"state": "REVOKED"},
        agent_id=lease.agent_id,
    )
    return success_response({"lease_id": str(lease_id), "state": "REVOKED"})
