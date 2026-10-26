"""Event Ingestion API — POST /events, POST /events/batch, GET /events/{event_id}

Satisfies: REQ-001, REQ-016
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response
from varynx.engine.ingestion import DuplicateActionError, IngestionError
from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult

router = APIRouter()

def get_pipeline(request: Request) -> VarynxPipeline:
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class EventSubmitRequest(BaseModel):
    agent_id: str
    session_id: UUID
    timestamp: datetime
    action_type: ActionType
    capability_requested: str
    target_resource: str
    authorization_result: AuthorizationResult
    is_simulated: bool
    task_id: str | None = None
    execution_context: dict = {}
    behavioral_signals: dict = {}
    trust_signal: float | None = None

@router.post("/events", summary="Submit a single AgentActionEvent")
async def submit_event(body: EventSubmitRequest, request: Request):
    pipeline = get_pipeline(request)
    event = AgentActionEvent.model_validate(body.model_dump(), strict=False)
    action_id = f"{body.agent_id}:{body.timestamp.isoformat()}"
    try:
        result = pipeline.process_event(event, action_id=action_id, skip_timestamp_check=True)
    except DuplicateActionError as e:
        raise HTTPException(status_code=409, detail=error_response("DUPLICATE_ACTION_ID", str(e)))
    except IngestionError as e:
        raise HTTPException(status_code=422, detail=error_response(e.reason_code, str(e)))
    if result.error:
        raise HTTPException(status_code=503, detail=error_response("PIPELINE_ERROR", result.error))
    return success_response({
        "event_id": str(result.event_id),
        "correlation_id": str(result.correlation_id),
        "trust_score": result.trust_score,
        "trust_level": result.trust_level,
        "response": result.recommendation.response_type.value if result.recommendation else "UNKNOWN",
        "anomalies": result.anomalies_detected,
    })

@router.post("/events/batch", summary="Submit up to 100 events")
async def submit_events_batch(body: list[EventSubmitRequest], request: Request):
    if len(body) > 100:
        raise HTTPException(status_code=422, detail=error_response("BATCH_TOO_LARGE", "Max 100 events per batch"))
    pipeline = get_pipeline(request)
    results = []
    for item in body:
        event = AgentActionEvent.model_validate(item.model_dump(), strict=False)
        action_id = f"{item.agent_id}:{item.timestamp.isoformat()}:{uuid4()}"
        result = pipeline.process_event(event, action_id=action_id, skip_timestamp_check=True)
        results.append({
            "event_id": str(result.event_id),
            "correlation_id": str(result.correlation_id),
            "error": result.error,
        })
    return success_response({"processed": len(results), "results": results})

@router.get("/events/{event_id}", summary="Retrieve a stored event record")
async def get_event(event_id: UUID, request: Request):
    # In-memory: return audit records referencing this event_id
    pipeline = get_pipeline(request)
    records = [r for r in pipeline.audit_store.all_records()
               if r.payload.get("event_id") == str(event_id)]
    if not records:
        raise HTTPException(status_code=404, detail=error_response("EVENT_NOT_FOUND", f"Event {event_id} not found"))
    return success_response({"event_id": str(event_id), "audit_records": len(records)})
