"""Sessions API.

Satisfies: REQ-002, REQ-016
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response
from varynx.engine.pipeline import VarynxPipeline
from varynx.models.agent import SessionRecord
from varynx.models.audit import AuditRecordType

router = APIRouter()

def get_pipeline(request: Request) -> VarynxPipeline:
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class SessionCreateRequest(BaseModel):
    agent_id: str
    session_id: UUID | None = None

@router.post("/sessions", summary="Create a session")
async def create_session(body: SessionCreateRequest, request: Request):
    pipeline = get_pipeline(request)
    session_id = body.session_id or uuid4()
    now = datetime.now(UTC)
    session = SessionRecord.model_validate({
        "session_id": str(session_id),
        "agent_id": body.agent_id,
        "started_at": str(now),
    }, strict=False)
    pipeline.registry._sessions[session_id] = session
    pipeline.audit_store.append(
        record_type=AuditRecordType.SESSION_CREATED,
        source_entity_id=str(session_id),
        payload={"agent_id": body.agent_id},
        agent_id=body.agent_id,
    )
    return success_response(session.model_dump())

@router.get("/sessions/{session_id}", summary="Get session state")
async def get_session(session_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    session = pipeline.registry._sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=error_response("SESSION_NOT_FOUND", f"Session {session_id} not found"))
    return success_response(session.model_dump())

@router.delete("/sessions/{session_id}", summary="Terminate a session")
async def terminate_session(session_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    session = pipeline.registry._sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=error_response("SESSION_NOT_FOUND", f"Session {session_id} not found"))
    from datetime import datetime
    updated = SessionRecord.model_validate({**session.model_dump(), "state": "TERMINATED", "ended_at": str(datetime.now(UTC))}, strict=False)
    pipeline.registry._sessions[session_id] = updated
    pipeline.audit_store.append(
        record_type=AuditRecordType.SESSION_TERMINATED,
        source_entity_id=str(session_id),
        payload={"agent_id": session.agent_id, "reason": "API_TERMINATE"},
        session_id=session_id,
        agent_id=session.agent_id,
    )
    return success_response({"session_id": str(session_id), "state": "TERMINATED"})

@router.get("/sessions/{session_id}/leases", summary="List leases for session")
async def get_session_leases(session_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    leases = [l for l in pipeline.lease_manager._leases.values() if l.session_id == session_id]
    return success_response({"leases": [l.model_dump() for l in leases]})
