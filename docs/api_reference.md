# Varynx — API Reference Documentation

**Document:** T11.3 API Reference  
**Version:** 0.1.0  
**Base path:** `/api/v1`  
**Content-Type:** `application/json`

---

## Authentication

All endpoints require authentication. In Phase 1, the API accepts all requests (auth middleware placeholder). Production deployment requires a bearer token in `Authorization: Bearer <token>`.

---

## Common Response Envelope

### Success
```json
{
  "status": "success",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "data": { ... }
}
```

### Error
```json
{
  "status": "error",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "error_code": "REASON_CODE",
  "message": "Human-readable description"
}
```

---

## Event Ingestion

### POST /api/v1/events
Submit a single `AgentActionEvent`.

**Request body:**
```json
{
  "agent_id": "string",
  "session_id": "uuid",
  "timestamp": "ISO-8601 datetime",
  "action_type": "READ|WRITE|EXECUTE|DELETE|NETWORK_CALL|CREDENTIAL_ACCESS|CONFIGURATION_CHANGE|TOOL_INVOCATION|DELEGATION",
  "capability_requested": "string",
  "target_resource": "string",
  "authorization_result": "allowed|denied|pending",
  "is_simulated": true,
  "task_id": "string (optional)",
  "execution_context": {},
  "behavioral_signals": {},
  "trust_signal": 0.0
}
```

**Success response (200):**
```json
{
  "data": {
    "event_id": "uuid",
    "correlation_id": "uuid",
    "trust_score": 0.7,
    "trust_level": "ELEVATED",
    "response": "PERMIT",
    "anomalies": []
  }
}
```

**Error responses:**
- `422 TIMESTAMP_OUT_OF_RANGE` — timestamp not within ±300/60s of system clock
- `409 DUPLICATE_ACTION_ID` — action_id already seen for this agent
- `503 PIPELINE_ERROR` — internal pipeline failure

### POST /api/v1/events/batch
Submit up to 100 events atomically.

### GET /api/v1/events/{event_id}
Retrieve audit records for a stored event.

---

## Agent Management

### POST /api/v1/agents
Register an agent with known capability and resource scope.

### GET /api/v1/agents/{agent_id}
Retrieve agent context record.

### GET /api/v1/agents/{agent_id}/profile
Retrieve full security profile: agent record, current trust state, active leases.

---

## Session Management

### POST /api/v1/sessions
Create a session.

### GET /api/v1/sessions/{session_id}
Get session state including current trust.

### DELETE /api/v1/sessions/{session_id}
Terminate a session.

### GET /api/v1/sessions/{session_id}/leases
List all leases for a session.

---

## Capability Leases

### POST /api/v1/leases
Grant a capability lease.

**Request:**
```json
{
  "agent_id": "string",
  "session_id": "uuid",
  "capability": "string",
  "resource_scope": {},
  "issuing_principal": "string",
  "issuing_policy_id": "string",
  "expiry_timestamp": "ISO-8601 (optional)"
}
```

### GET /api/v1/leases/{lease_id}
Get lease record and state history.

### PATCH /api/v1/leases/{lease_id}/suspend
Suspend an ACTIVE lease.

### PATCH /api/v1/leases/{lease_id}/reinstate
Reinstate a SUSPENDED lease. Produces an audit record.

### DELETE /api/v1/leases/{lease_id}
Revoke a lease (terminal — cannot be undone).

---

## BCSE

### POST /api/v1/bcse/evaluate
Submit a proposed action for non-destructive BCSE evaluation.

**Request:**
```json
{
  "agent_id": "string",
  "proposed_action_type": "READ|...",
  "proposed_resource_scope": "string",
  "session_id": "uuid",
  "capability_requested": "string (optional)"
}
```

**Note (Phase 1):** Returns `is_stub: true`. Full counterfactual analysis requires Phase 2 engine.

---

## Audit & Evidence

### GET /api/v1/audit
Query audit records. Filters: `agent_id`, `correlation_id`, `record_type`, `limit`.

### GET /api/v1/audit/{record_id}
Get a single audit record.

### GET /api/v1/audit/provenance/{correlation_id}
Full traceability chain: event → evidence → decisions → audit records.

Returns `chain_integrity_violation: true` if any record is missing from the chain.

### GET /api/v1/audit/export
Export all audit records as JSON-L (newline-delimited JSON).

### GET /api/v1/audit/verify
Verify SHA-256 hash-chain integrity across all audit records.

---

## Evaluation

### POST /api/v1/evaluate/run
Execute a named scenario file.

### GET /api/v1/evaluate/scenarios
List available scenario files.

### GET /api/v1/evaluate/results/{run_id}
Retrieve a saved evaluation run result.

---

## System

### GET /api/v1/health
Storage subsystem availability and record counts.

### GET /api/v1/metrics
Operational metrics: events ingested, active sessions, active leases, audit records.

### GET /api/v1/config
Read-only active configuration snapshot. Secrets (database_url, redis_url) are excluded.

---

## Error Code Reference

| Code | HTTP | Meaning |
|------|------|---------|
| `DUPLICATE_ACTION_ID` | 409 | action_id already seen for agent |
| `TIMESTAMP_OUT_OF_RANGE` | 422 | Event timestamp outside allowed bounds |
| `PIPELINE_ERROR` | 503 | Internal pipeline failure |
| `BCSE_EVALUATION_FAILED` | 503 | BCSE evaluation error |
| `AGENT_NOT_FOUND` | 404 | Agent ID not registered |
| `SESSION_NOT_FOUND` | 404 | Session ID not found |
| `LEASE_NOT_FOUND` | 404 | Lease ID not found |
| `LEASE_REVOKED_TERMINAL` | 409 | Cannot transition a REVOKED lease |
| `INVALID_TRANSITION` | 409 | Invalid lease state transition |
| `CORRELATION_ID_NOT_FOUND` | 404 | No audit records for correlation_id |
| `SCENARIO_NOT_FOUND` | 404 | Scenario file not found |
| `EVALUATION_ERROR` | 503 | Scenario evaluation error |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded (1000 req/min default) |
| `INTERNAL_ERROR` | 503 | Unhandled internal error |