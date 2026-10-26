"""Agent & Session APIs.

Satisfies: REQ-002, REQ-016
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response
from varynx.engine.pipeline import VarynxPipeline

router = APIRouter()

def get_pipeline(request: Request) -> VarynxPipeline:
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class AgentRegisterRequest(BaseModel):
    agent_id: str
    owning_principal: str
    declared_capability_scope: list[str] = []
    authorized_resource_scope: list[str] = []

@router.post("/agents", summary="Register an agent")
async def register_agent(body: AgentRegisterRequest, request: Request):
    pipeline = get_pipeline(request)
    agent = pipeline.registry.register_agent(
        agent_id=body.agent_id,
        owning_principal=body.owning_principal,
        declared_capability_scope=body.declared_capability_scope,
        authorized_resource_scope=body.authorized_resource_scope,
    )
    return success_response(agent.model_dump())

@router.get("/agents/{agent_id}", summary="Get agent context record")
async def get_agent(agent_id: str, request: Request):
    pipeline = get_pipeline(request)
    agent = pipeline.registry._agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=error_response("AGENT_NOT_FOUND", f"Agent {agent_id} not found"))
    return success_response(agent.model_dump())

@router.get("/agents/{agent_id}/profile", summary="Get full agent security profile")
async def get_agent_profile(agent_id: str, request: Request):
    pipeline = get_pipeline(request)
    agent = pipeline.registry._agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=error_response("AGENT_NOT_FOUND", f"Agent {agent_id} not found"))
    trust_state = pipeline.trust_scorer._states.get(agent_id)
    leases = pipeline.lease_manager.get_leases_for_agent(agent_id)
    return success_response({
        "agent": agent.model_dump(),
        "trust": trust_state.model_dump() if trust_state else None,
        "leases": [l.model_dump() for l in leases],
    })
