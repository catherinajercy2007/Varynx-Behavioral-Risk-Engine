"""Audit & Evidence API.

Satisfies: REQ-012, REQ-013, REQ-016
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from varynx.api.schemas import error_response, success_response

router = APIRouter()

def get_pipeline(request: Request):
    from varynx.api.app import get_pipeline as _gp
    return _gp()

@router.get("/audit", summary="Query audit records")
async def query_audit(
    request: Request,
    agent_id: str | None = Query(None),
    correlation_id: UUID | None = Query(None),
    record_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    pipeline = get_pipeline(request)
    records = pipeline.audit_store.all_records()
    if agent_id:
        records = [r for r in records if r.agent_id == agent_id]
    if correlation_id:
        records = [r for r in records if r.correlation_id == correlation_id]
    if record_type:
        records = [r for r in records if r.record_type.value == record_type]
    return success_response({"count": len(records[:limit]), "records": [r.model_dump() for r in records[:limit]]})

@router.get("/audit/verify", summary="Verify hash-chain integrity")
async def verify_chain(request: Request):
    pipeline = get_pipeline(request)
    valid, violations = pipeline.audit_store.verify_chain()
    return success_response({
        "chain_valid": valid,
        "record_count": len(pipeline.audit_store.all_records()),
        "violations": violations,
    })

@router.get("/audit/provenance/{correlation_id}", summary="Full traceability chain")
async def get_provenance(correlation_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    result = pipeline.tracer.trace(correlation_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=error_response("CORRELATION_ID_NOT_FOUND", f"No records for {correlation_id}"))
    return success_response(result)

@router.get("/audit/export", summary="Export audit records as JSON-L")
async def export_audit(request: Request):
    pipeline = get_pipeline(request)
    records = pipeline.audit_store.all_records()
    lines = "\n".join(json.dumps(r.model_dump(), default=str) for r in records)
    return StreamingResponse(iter([lines]), media_type="application/x-ndjson",
                              headers={"Content-Disposition": "attachment; filename=audit.jsonl"})

@router.get("/audit/{record_id}", summary="Get a single audit record")
async def get_audit_record(record_id: UUID, request: Request):
    pipeline = get_pipeline(request)
    record = pipeline.audit_store.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=error_response("RECORD_NOT_FOUND", f"Record {record_id} not found"))
    return success_response(record.model_dump())
