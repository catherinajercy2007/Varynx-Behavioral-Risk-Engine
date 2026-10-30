"""BCSE API — POST /bcse/evaluate

Satisfies: REQ-007, REQ-016
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response
from varynx.models.bcse import BCSeContext, PolicyAlternative
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustLevel, TrustState

router = APIRouter()

def get_pipeline(request: Request):
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class BCSeEvaluateRequest(BaseModel):
    agent_id: str
    proposed_action_type: ActionType
    proposed_resource_scope: str
    session_id: UUID
    capability_requested: str = "evaluate"
    # When supplied, Phase 2 engine runs; returns is_stub=False with counterfactuals.
    # When omitted, Phase 1 stub runs; returns is_stub=True.
    alternative_policies: list[dict] = []

@router.post("/bcse/evaluate", summary="Submit a proposed action for BCSE evaluation")
async def bcse_evaluate(body: BCSeEvaluateRequest, request: Request):
    pipeline = get_pipeline(request)
    now = datetime.now(UTC)

    # Build a proposed event (not stored — BCSE is non-destructive, REQ-007.3)
    proposed_event = AgentActionEvent.model_validate({
        "agent_id": body.agent_id,
        "session_id": str(body.session_id),
        "timestamp": str(now),
        "action_type": body.proposed_action_type.value,
        "capability_requested": body.capability_requested,
        "target_resource": body.proposed_resource_scope,
        "authorization_result": AuthorizationResult.PENDING.value,
        "is_simulated": True,
    }, strict=False)

    # Get current trust state or use default
    trust_state = pipeline.trust_scorer._states.get(body.agent_id)
    if trust_state is None:
        session_id = body.session_id
        trust_state = TrustState.model_validate({
            "session_id": str(session_id),
            "agent_id": body.agent_id,
            "current_score": 0.7,
            "level": TrustLevel.ELEVATED.value,
            "last_updated": str(now),
        }, strict=False)

    # Create empty evidence bundle for context
    empty_bundle = EvidenceBundle.model_validate({
        "bundle_id": str(uuid4()),
        "session_id": str(body.session_id),
        "agent_id": body.agent_id,
        "correlation_id": str(uuid4()),
        "composite_score": 0.0,
        "correlation_window_seconds": 300.0,
        "timestamp": str(now),
        "is_simulated": True,
    }, strict=False)

    context = BCSeContext.model_validate({
        "context_id": str(uuid4()),
        "proposed_action": proposed_event.model_dump(),
        "evidence_bundle": empty_bundle.model_dump(),
        "trust_state": trust_state.model_dump(),
        "active_policy_id": pipeline.response_engine._policy_id,
        "alternative_policies": [
            PolicyAlternative.model_validate(a, strict=False).model_dump()
            for a in body.alternative_policies
        ],
    }, strict=False)

    try:
        result = pipeline.bcse_engine.analyze(context)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=error_response("BCSE_EVALUATION_FAILED", str(exc)))

    return success_response(result.model_dump())
