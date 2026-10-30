"""Health, Metrics, and Config APIs.

Satisfies: REQ-016, REQ-017, REQ-019
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from varynx.api.schemas import success_response

router = APIRouter()

def get_pipeline(request: Request):
    from varynx.api.app import get_pipeline as _gp
    return _gp()

@router.get("/health", summary="Storage subsystem availability and counts")
async def health(request: Request):
    pipeline = get_pipeline(request)
    audit_count = len(pipeline.audit_store.all_records())
    agent_count = len(pipeline.registry._agents)
    session_count = len(pipeline.registry._sessions)
    lease_count = len(pipeline.lease_manager._leases)
    return success_response({
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "storage": {
            "agents": agent_count,
            "sessions": session_count,
            "leases": lease_count,
            "audit_records": audit_count,
        },
        "subsystems": {
            "ingestion": "ok",
            "evidence_engine": "ok",
            "trust_scorer": "ok",
            "audit_store": "ok",
            "enforcement": "ok",
            "bcse_stub": "ok (Phase 1 stub)",
            "predictive_stub": "ok (Phase 1 stub)",
        },
    })

@router.get("/metrics", summary="Operational metrics")
async def metrics(request: Request):
    pipeline = get_pipeline(request)
    return success_response({
        "events_ingested": len([r for r in pipeline.audit_store.all_records()
                                if r.record_type.value == "EVENT_INGESTED"]),
        "agents_tracked": len(pipeline.registry._agents),
        "sessions_active": len([s for s in pipeline.registry._sessions.values()
                                 if s.state == "ACTIVE"]),
        "audit_records": len(pipeline.audit_store.all_records()),
        "leases_active": len([l for l in pipeline.lease_manager._leases.values()
                               if l.state.value == "ACTIVE"]),
    })

@router.get("/config", summary="Read-only active configuration snapshot")
async def get_config(request: Request):
    pipeline = get_pipeline(request)
    cfg = pipeline.config
    # Never expose secrets (database_url, redis_url)
    return success_response({
        "dry_run_mode": cfg.dry_run_mode,
        "trust": {
            "initial_score": cfg.trust.initial_score,
            "sensitivity": cfg.trust.sensitivity,
            "temporal_decay_rate": cfg.trust.temporal_decay_rate,
        },
        "evidence": {
            "authz_denial_threshold": cfg.evidence.authz_denial_threshold,
            "resource_spread_threshold": cfg.evidence.resource_spread_threshold,
        },
        "policy": {
            "escalation_threshold": cfg.policy.escalation_threshold,
            "critical_threshold": cfg.policy.critical_threshold,
        },
        "note": "Secrets (database_url, redis_url) are excluded from this response.",
    })
