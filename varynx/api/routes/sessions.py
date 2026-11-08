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
    """Get the active Varynx pipeline."""
    from varynx.api.app import get_pipeline as _gp

    return _gp()


class SessionCreateRequest(BaseModel):
    """Request model for session creation."""

    agent_id: str
    session_id: UUID | None = None


@router.post("/sessions", summary="Create a session")
async def create_session(
    body: SessionCreateRequest,
    request: Request,
):
    """Create a session for an existing agent."""

    pipeline = get_pipeline(request)

    session_id = body.session_id or uuid4()

    now = datetime.now(UTC)

    session = SessionRecord.model_validate(
        {
            "session_id": str(session_id),
            "agent_id": body.agent_id,
            "started_at": str(now),
        },
        strict=False,
    )

    try:
        pipeline.registry.create_session(session)

    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=error_response(
                "SESSION_CONFLICT",
                str(exc),
            ),
        ) from exc

    pipeline.audit_store.append(
        record_type=AuditRecordType.SESSION_CREATED,
        source_entity_id=str(session_id),
        payload={
            "agent_id": body.agent_id,
        },
        agent_id=body.agent_id,
    )

    return success_response(session.model_dump())


@router.get(
    "/sessions/{session_id}",
    summary="Get session state",
)
async def get_session(
    session_id: UUID,
    request: Request,
):
    """Retrieve a session."""

    pipeline = get_pipeline(request)

    session = pipeline.registry.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=error_response(
                "SESSION_NOT_FOUND",
                f"Session {session_id} not found",
            ),
        )

    return success_response(session.model_dump())


@router.delete(
    "/sessions/{session_id}",
    summary="Terminate a session",
)
async def terminate_session(
    session_id: UUID,
    request: Request,
):
    """Terminate an active session."""

    pipeline = get_pipeline(request)

    session = pipeline.registry.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=error_response(
                "SESSION_NOT_FOUND",
                f"Session {session_id} not found",
            ),
        )

    try:
        pipeline.registry.terminate_session(session_id)

    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=error_response(
                "SESSION_STATE_ERROR",
                str(exc),
            ),
        ) from exc

    pipeline.audit_store.append(
        record_type=AuditRecordType.SESSION_TERMINATED,
        source_entity_id=str(session_id),
        payload={
            "agent_id": session.agent_id,
            "reason": "API_TERMINATE",
        },
        session_id=session_id,
        agent_id=session.agent_id,
    )

    return success_response(
        {
            "session_id": str(session_id),
            "state": "TERMINATED",
        }
    )


@router.get(
    "/sessions/{session_id}/leases",
    summary="List leases for session",
)
async def get_session_leases(
    session_id: UUID,
    request: Request,
):
    """Retrieve leases associated with a session."""

    pipeline = get_pipeline(request)

    leases = pipeline.lease_manager.get_leases_for_session(
        session_id
    )

    return success_response(
        {
            "leases": [
                lease.model_dump()
                for lease in leases
            ]
        }
    )
