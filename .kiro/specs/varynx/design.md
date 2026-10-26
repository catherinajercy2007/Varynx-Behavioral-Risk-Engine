# Varynx — Behavioral Risk Control Engine for Autonomous AI Agents
## Technical Design Specification

**Version:** 1.0  
**Status:** Awaiting Approval  
**Companion Document:** `requirements.md` v1.0  
**Repository State at Authoring:** Empty workspace — all interfaces and designs are specified forward from the approved research direction.

---

## Overview

Varynx is a cloud-native behavioral risk control engine for autonomous AI agents. It operates on structured event streams — without access to model internals — to produce security-relevant signals: anomaly detection, dynamic trust scoring, and pre-action risk projection via the Behavioral Counterfactual Security Evaluation (BCSE) engine. Varynx is simultaneously a security infrastructure component and a research instrument.

The central research question is: can a behavioral evidence model, combined with dynamic trust quantification and bounded counterfactual analysis, produce more accurate, explainable, and timely security decisions for autonomous AI agents than static policy or threshold-based approaches? Four falsifiable hypotheses (H1–H4) guide empirical evaluation. No results are pre-claimed.

This document covers the full technical design for Phase 1 (core pipeline MVP through REST API and evaluation framework) and specifies stub interfaces for Phase 2 components (full BCSE engine, predictive trajectory analysis). It includes data models, component responsibilities, API contracts, database schema, correctness properties, error handling, and testing strategy. The repository is empty at the time of authoring; all content here is a forward specification.

---

## Architecture

Varynx is organized as a layered pipeline of independent, composable components. Each layer has a defined input interface, output contract, and can be independently tested, configured, and ablated.

```
┌──────────────────────────────────────────────────────────────────────┐
│  REST API  (FastAPI)                                                  │
│  /events  /agents  /sessions  /leases  /audit  /evaluate             │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  AgentActionEvent
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Ingestion & Validation Layer                                         │
│  Schema validation · Idempotency · Simulated-event labeling          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  ValidatedEvent
                          ▼
┌─────────────────────────────────┐  ┌───────────────────────────────┐
│  Identity & Session Registry    │  │  Capability Lease Manager     │
│  Agent records · Session state  │◄─┤  Grant · Suspend · Revoke     │
│  Lease association              │  │  Scope evaluation             │
└─────────────────────────┬───────┘  └───────────────────────────────┘
                          │  SessionContext + LeaseEvaluation
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Behavioral Evidence Engine                                           │
│  Detector pipeline · Anomaly scoring · Evidence correlation          │
│  Provenance tagging                                                   │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  EvidenceBundle
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Dynamic Trust Module                                                 │
│  Score update · Decay · Level classification · History               │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  TrustState
                          ▼
┌─────────────────┐       │       ┌────────────────────────────────────┐
│  BCSE Engine    │◄──────┤       │  Predictive Intelligence Layer     │
│  (Phase 2)      │       │       │  (Phase 2)                         │
│  Counterfactual │       │       │  Trajectory · Early warning        │
│  analysis       │       │       │                                    │
└────────┬────────┘       │       └──────────────┬─────────────────────┘
         │                │                      │
         └────────────────┼──────────────────────┘
                          │  BCSEResult? + TrajectoryProjection?
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Adaptive Response Engine                                             │
│  Policy evaluation · Response recommendation · Reason codes          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  ResponseRecommendation
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Runtime Enforcement Layer                                            │
│  Applies lease changes · Session terminations · Dry-run support      │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  EnforcementRecord
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Audit Log & Evidence Provenance Store                                │
│  Append-only · Hash-chained · Full provenance query                  │
└──────────────────────────────────────────────────────────────────────┘
         ▲
         │  All components emit audit records
         │
┌──────────────────────────────────────────────────────────────────────┐
│  Evaluation Framework                                                 │
│  Scenario runner · Baseline comparisons · Ablation · Statistics      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Research-friendly, rich ML/stats ecosystem |
| API framework | FastAPI | Async, automatic OpenAPI, Pydantic validation |
| Data validation | Pydantic v2 | Fast, declarative, IDE-friendly |
| Persistence | PostgreSQL 15 + TimescaleDB | Time-series evidence, provenance queries |
| Event store (optional) | Redis Streams | Lightweight replay for evaluation harness |
| Testing | pytest + Hypothesis | Unit, property-based, integration |
| Linting | ruff + mypy | Fast, strict |
| Container | Docker + docker-compose | Reproducible local environment |
| UI (Phase 3) | Next.js 14 + Tailwind CSS | Composable, fast, research dashboard |
| Database migration | Alembic | Schema version control |
| Configuration | Pydantic Settings + YAML | Environment-aware, validated |

---

## 3. Repository Layout

```
varynx/
├── varynx/                          # Core Python package
│   ├── __init__.py
│   ├── config.py                    # Pydantic Settings configuration
│   ├── models/                      # Shared Pydantic data models
│   │   ├── __init__.py
│   │   ├── agent.py                 # AgentRecord, SessionRecord
│   │   ├── event.py                 # AgentActionEvent, ValidatedEvent
│   │   ├── evidence.py              # EvidenceRecord, EvidenceBundle
│   │   ├── trust.py                 # TrustState, TrustHistoryEntry
│   │   ├── lease.py                 # CapabilityLease, LeaseEvaluation
│   │   ├── bcse.py                  # BCSeContext, BCSeResult (Phase 2 + stub)
│   │   ├── prediction.py            # TrajectoryProjection (Phase 2 + stub)
│   │   ├── response.py              # ResponseRecommendation, ReasonCode
│   │   ├── enforcement.py           # EnforcementRecord
│   │   └── audit.py                 # AuditRecord
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── validator.py             # Schema validation, idempotency check
│   │   └── normalizer.py            # Action type normalization
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── registry.py              # Agent + session registry
│   │   └── session.py               # Session lifecycle management
│   ├── evidence/
│   │   ├── __init__.py
│   │   ├── engine.py                # Detector pipeline orchestration
│   │   ├── detectors/               # One module per anomaly class
│   │   │   ├── __init__.py
│   │   │   ├── capability_escalation.py
│   │   │   ├── resource_anomaly.py
│   │   │   ├── action_frequency.py
│   │   │   ├── authorization_bypass.py
│   │   │   ├── context_deviation.py
│   │   │   └── temporal_anomaly.py
│   │   ├── correlator.py            # Evidence correlation and bundling
│   │   └── provenance.py            # Provenance chain construction
│   ├── trust/
│   │   ├── __init__.py
│   │   ├── scorer.py                # Trust score update logic
│   │   ├── decay.py                 # Decay functions
│   │   └── classifier.py           # Score → TrustLevel mapping
│   ├── bcse/
│   │   ├── __init__.py
│   │   ├── interface.py             # BCSeEngine protocol definition
│   │   ├── stub.py                  # Phase 1 stub implementation
│   │   └── engine.py               # Phase 2 full implementation (placeholder)
│   ├── prediction/
│   │   ├── __init__.py
│   │   ├── interface.py             # PredictiveEngine protocol definition
│   │   ├── stub.py                  # Phase 1 stub (always STABLE)
│   │   └── engine.py               # Phase 2 full implementation (placeholder)
│   ├── response/
│   │   ├── __init__.py
│   │   ├── engine.py                # Response recommendation logic
│   │   ├── policy.py               # Policy loading and evaluation
│   │   └── reason_codes.py         # Reason code catalog
│   ├── lease/
│   │   ├── __init__.py
│   │   ├── manager.py               # Lease CRUD and evaluation
│   │   └── evaluator.py             # Lease scope checking per event
│   ├── enforcement/
│   │   ├── __init__.py
│   │   └── enforcer.py              # Response → state change, dry-run
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── store.py                 # Append-only audit log
│   │   ├── hasher.py                # Hash-chain computation
│   │   └── provenance_query.py     # Full provenance retrieval
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── routers/
│   │   │   ├── events.py
│   │   │   ├── agents.py
│   │   │   ├── sessions.py
│   │   │   ├── leases.py
│   │   │   ├── audit.py
│   │   │   └── evaluate.py
│   │   └── middleware.py            # Request ID, timing, structured logging
│   └── pipeline/
│       ├── __init__.py
│       └── processor.py             # Top-level pipeline orchestration
├── evaluation/
│   ├── __init__.py
│   ├── runner.py                    # Scenario execution engine
│   ├── scenarios/                   # YAML scenario definitions
│   │   ├── baseline_normal.yaml
│   │   ├── capability_escalation.yaml
│   │   ├── authorization_bypass.yaml
│   │   └── ...
│   ├── baselines/
│   │   ├── policy_only.py           # B1
│   │   ├── risk_threshold.py        # B2
│   │   ├── behavioral_trust.py      # B3
│   │   └── full_system.py          # B4
│   ├── metrics.py                   # Detection rate, F1, latency, etc.
│   └── report.py                   # Report generation
├── tests/
│   ├── unit/
│   │   ├── test_ingestion.py
│   │   ├── test_evidence_engine.py
│   │   ├── test_trust_scorer.py
│   │   ├── test_bcse_stub.py
│   │   ├── test_response_engine.py
│   │   ├── test_lease_manager.py
│   │   ├── test_enforcement.py
│   │   └── test_audit_store.py
│   ├── property/
│   │   ├── test_evidence_properties.py   # Hypothesis
│   │   ├── test_trust_properties.py      # Hypothesis
│   │   └── test_response_properties.py   # Hypothesis
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   ├── test_api_events.py
│   │   └── test_audit_provenance.py
│   └── fixtures/
│       ├── events.py
│       ├── sessions.py
│       └── policies.py
├── ui/                              # Phase 3 — Next.js dashboard
│   └── (scaffolded in Phase 3)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── alembic/                         # Database migrations
├── config/
│   ├── default_policy.yaml
│   └── trust_thresholds.yaml
├── docs/
│   ├── research_questions.md
│   ├── evaluation_protocol.md
│   └── api_reference.md
├── reproduce.sh
├── pyproject.toml
└── README.md
```

---

## Data Models

All models are defined using Pydantic v2 with strict mode enabled.

### 4.1 AgentActionEvent

```python
class ActionType(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    DELETE = "DELETE"
    NETWORK_CALL = "NETWORK_CALL"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    TOOL_INVOCATION = "TOOL_INVOCATION"
    DELEGATION = "DELEGATION"

class AuthorizationResult(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    PENDING = "pending"

class AgentActionEvent(BaseModel):
    model_config = ConfigDict(strict=True)

    event_id: UUID
    agent_id: str                          # Stable agent identity
    session_id: UUID
    timestamp: datetime                    # UTC, ISO-8601
    task_id: Optional[str] = None
    action_type: ActionType
    capability_requested: str
    target_resource: str
    execution_context: Dict[str, Any] = Field(default_factory=dict)
    authorization_result: AuthorizationResult
    behavioral_signals: Dict[str, float] = Field(default_factory=dict)
    trust_signal: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_simulated: bool                     # REQUIRED; true for all test events
```

### 4.2 EvidenceRecord and EvidenceBundle

```python
class AnomalyClass(str, Enum):
    CAPABILITY_ESCALATION = "CAPABILITY_ESCALATION"
    RESOURCE_ANOMALY = "RESOURCE_ANOMALY"
    ACTION_FREQUENCY = "ACTION_FREQUENCY"
    AUTHORIZATION_BYPASS_ATTEMPT = "AUTHORIZATION_BYPASS_ATTEMPT"
    CONTEXT_DEVIATION = "CONTEXT_DEVIATION"
    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"

class EvidenceRecord(BaseModel):
    evidence_id: UUID
    event_id: UUID                         # Source event
    session_id: UUID
    agent_id: str
    anomaly_class: AnomalyClass
    score: float = Field(ge=0.0, le=1.0)   # Invariant: always in [0, 1]
    weight: float = Field(ge=0.0, le=1.0)
    detector_id: str                       # Which detector produced this
    contributing_signals: List[str]        # Signal keys from the event
    provenance: Dict[str, Any]             # Full derivation record
    timestamp: datetime
    is_simulated: bool

class EvidenceBundle(BaseModel):
    bundle_id: UUID
    session_id: UUID
    agent_id: str
    records: List[EvidenceRecord]
    composite_score: float = Field(ge=0.0, le=1.0)
    correlation_window_seconds: float
    timestamp: datetime
```

### 4.3 TrustState

```python
class TrustLevel(str, Enum):
    HIGH = "HIGH"           # [0.85, 1.00]
    ELEVATED = "ELEVATED"   # [0.65, 0.85)
    GUARDED = "GUARDED"     # [0.40, 0.65)
    LOW = "LOW"             # [0.20, 0.40)
    CRITICAL = "CRITICAL"   # [0.00, 0.20)

class TrustHistoryEntry(BaseModel):
    entry_id: UUID
    timestamp: datetime
    prior_score: float
    delta: float
    new_score: float
    contributing_evidence_id: UUID

class TrustState(BaseModel):
    session_id: UUID
    agent_id: str
    current_score: float = Field(ge=0.0, le=1.0)
    level: TrustLevel
    history: List[TrustHistoryEntry] = Field(default_factory=list)
    last_updated: datetime
    session_age_seconds: float
```

### 4.4 Trust Score Update Formula

The trust score is updated according to the following deterministic function:

```
new_score = clamp(
    current_score
    - (evidence_weight * anomaly_composite_score * sensitivity)
    - (temporal_decay_rate * session_age_seconds / 3600),
    0.0, 1.0
)
```

Where:
- `sensitivity` — configurable per-deployment (default: 1.0)
- `temporal_decay_rate` — configurable (default: 0.01 per hour)
- `anomaly_composite_score` — the `composite_score` from the `EvidenceBundle`
- `clamp(v, 0.0, 1.0)` — hard bounds enforcement

Positive reinforcement (score recovery) is NOT implemented in Phase 1. Phase 2 may introduce recovery factors for sustained nominal behavior.

### 4.5 BCSeContext and BCSeResult (Phase 1 Stub Interface)

```python
class PolicyAlternative(BaseModel):
    policy_id: str
    label: str
    overrides: Dict[str, Any]              # Declarative policy delta

class BCSeContext(BaseModel):
    context_id: UUID
    proposed_action: AgentActionEvent
    evidence_bundle: EvidenceBundle
    trust_state: TrustState
    active_policy_id: str
    alternative_policies: List[PolicyAlternative] = Field(default_factory=list)

class ConsequenceProjection(BaseModel):
    policy_id: str
    projected_response: ResponseType
    projected_trust_impact: float          # Delta to trust score
    risk_level: str                        # LOW / MEDIUM / HIGH / CRITICAL
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    is_projected: bool = True              # ALWAYS True — not an observed fact

class BCSeResult(BaseModel):
    result_id: UUID
    context_id: UUID
    active_consequence: ConsequenceProjection
    counterfactual_consequences: List[ConsequenceProjection]
    divergence_score: float = Field(ge=0.0, le=1.0)
    analysis_timestamp: datetime
    is_stub: bool                          # True in Phase 1 stub
```

### 4.6 TrajectoryProjection (Phase 1 Stub Interface)

```python
class TrendDirection(str, Enum):
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    RECOVERING = "RECOVERING"
    VOLATILE = "VOLATILE"

class TrajectoryProjection(BaseModel):
    projection_id: UUID
    session_id: UUID
    trend: TrendDirection
    projected_trust_at_horizon: float = Field(ge=0.0, le=1.0)
    horizon_seconds: float
    confidence_interval: Tuple[float, float]  # (lower, upper) at 95%
    early_warning: bool
    warning_threshold: float
    is_projected: bool = True              # ALWAYS True
    is_stub: bool                          # True in Phase 1 stub
```

### 4.7 ResponseRecommendation and ReasonCode

```python
class ResponseType(str, Enum):
    PERMIT = "PERMIT"
    WARN = "WARN"
    RESTRICT = "RESTRICT"
    SUSPEND = "SUSPEND"
    TERMINATE = "TERMINATE"
    ESCALATE = "ESCALATE"

class ReasonCode(BaseModel):
    code: str                              # e.g. "TRUST_LEVEL_CRITICAL"
    description: str
    contributing_evidence_ids: List[UUID]
    trust_level_at_recommendation: TrustLevel
    severity: str                          # INFO / WARNING / CRITICAL

class ResponseRecommendation(BaseModel):
    recommendation_id: UUID
    session_id: UUID
    agent_id: str
    event_id: UUID
    response_type: ResponseType
    reason_codes: List[ReasonCode]
    evidence_bundle_id: UUID
    trust_state_snapshot: TrustState
    bcse_result_id: Optional[UUID] = None
    trajectory_projection_id: Optional[UUID] = None
    timestamp: datetime
    policy_id: str
```

### 4.8 CapabilityLease

```python
class LeaseState(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"

class CapabilityLease(BaseModel):
    lease_id: UUID
    agent_id: str
    session_id: UUID
    capability: str
    scope: Dict[str, Any]                  # Resource pattern, action types, etc.
    granted_at: datetime
    expires_at: Optional[datetime] = None
    issuing_policy_id: str
    state: LeaseState
    state_history: List[Dict[str, Any]] = Field(default_factory=list)
```

### 4.9 AuditRecord

```python
class AuditRecordType(str, Enum):
    EVENT_INGESTED = "EVENT_INGESTED"
    EVIDENCE_PRODUCED = "EVIDENCE_PRODUCED"
    TRUST_UPDATED = "TRUST_UPDATED"
    RESPONSE_RECOMMENDED = "RESPONSE_RECOMMENDED"
    ENFORCEMENT_APPLIED = "ENFORCEMENT_APPLIED"
    LEASE_STATE_CHANGED = "LEASE_STATE_CHANGED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_TERMINATED = "SESSION_TERMINATED"

class AuditRecord(BaseModel):
    record_id: UUID
    timestamp: datetime
    record_type: AuditRecordType
    source_entity_id: str
    session_id: Optional[UUID] = None
    agent_id: Optional[str] = None
    payload: Dict[str, Any]
    prior_record_hash: Optional[str] = None  # SHA-256 of previous record
    record_hash: str                           # SHA-256 of this record's content
```

---

## Components and Interfaces

### 5.1 Detector Pipeline (Evidence Engine)

The evidence engine runs a configurable sequence of detectors. Each detector:

- Receives: `ValidatedEvent`, `SessionContext`, `LeaseEvaluation`
- Returns: `Optional[EvidenceRecord]` — `None` if no anomaly detected
- Is identified by a unique `detector_id`
- Is independently enable/disable-configurable

The pipeline orchestrates detectors, collects evidence records, runs correlation across the time window, and returns an `EvidenceBundle`.

**Detector interface (Protocol):**

```python
class AnomalyDetector(Protocol):
    detector_id: str
    anomaly_class: AnomalyClass
    enabled: bool

    def detect(
        self,
        event: ValidatedEvent,
        session_context: SessionContext,
        lease_evaluation: LeaseEvaluation,
        config: DetectorConfig,
    ) -> Optional[EvidenceRecord]: ...
```

### 5.2 Trust Scorer

Receives: `TrustState`, `EvidenceBundle`, `TrustConfig`  
Returns: updated `TrustState` with appended history entry

Key invariants (verified by property tests):
- Output score is always in [0.0, 1.0]
- Score never increases in Phase 1 (no recovery)
- A zero-evidence bundle produces only a decay delta
- History length = prior history length + 1

### 5.3 BCSE Engine — Phase 1 Stub

The stub always returns a `BCSeResult` with `is_stub=True` and a single `active_consequence` that mirrors the current policy recommendation with no divergence analysis. All `counterfactual_consequences` are an empty list. `divergence_score` is 0.0.

This allows the full pipeline to be integration-tested in Phase 1 without the Phase 2 engine.

**Phase 2 engine** will implement:
1. Policy simulation: evaluate the active policy and each alternative against the `BCSeContext`.
2. Consequence projection: for each policy, derive the projected `ResponseType` and `trust_impact`.
3. Divergence scoring: quantify how different the alternative projections are from the active consequence.
4. Confidence: based on evidence density and policy coverage.

### 5.4 Predictive Layer — Phase 1 Stub

The stub always returns a `TrajectoryProjection` with `trend=STABLE`, `early_warning=False`, and `is_stub=True`.

**Phase 2 engine** will implement a window-based trend analysis over `TrustHistoryEntry` records, using a configurable window size and horizon. Initial implementation will use linear regression over the trust history window.

### 5.5 Adaptive Response Engine

Policy-driven mapping from `(TrustLevel, [AnomalyClass])` → `ResponseType`.

Policy is a YAML file with a priority-ordered list of rules:

```yaml
rules:
  - if:
      trust_level: CRITICAL
    then:
      response: TERMINATE
      reason_codes: [TRUST_LEVEL_CRITICAL]
  - if:
      anomaly_class: AUTHORIZATION_BYPASS_ATTEMPT
      trust_level: [LOW, GUARDED]
    then:
      response: SUSPEND
      reason_codes: [BYPASS_ATTEMPT_DETECTED, TRUST_DEGRADED]
  - if:
      anomaly_class: CAPABILITY_ESCALATION
    then:
      response: RESTRICT
      reason_codes: [ESCALATION_DETECTED]
  - default:
      response: PERMIT
      reason_codes: []
```

Rules are evaluated in order; the first matching rule wins.

### 5.6 Audit Store

The store maintains an in-memory hash-chain pointer to the last written record's hash. On each `append`:

1. Compute the content hash of the new record (excluding `record_hash` and `prior_record_hash`).
2. Set `prior_record_hash` to the hash of the last record in the chain (`None` for the first).
3. Set `record_hash` to SHA-256(`prior_record_hash` + content_hash).
4. Persist.

Hash-chain integrity verification scans all records in insertion order and recomputes the chain.

### 5.7 Pipeline Processor

The top-level pipeline processor orchestrates all components for a single event:

```python
class EventProcessor:
    def process(self, event: AgentActionEvent) -> ProcessingResult:
        validated   = self.validator.validate(event)
        session_ctx = self.identity_registry.get_or_create_session(validated)
        lease_eval  = self.lease_manager.evaluate(validated, session_ctx)
        evidence    = self.evidence_engine.process(validated, session_ctx, lease_eval)
        trust       = self.trust_scorer.update(session_ctx.trust_state, evidence)
        bcse        = self.bcse_engine.analyze(BCSeContext(...))
        trajectory  = self.predictive_engine.project(trust)
        response    = self.response_engine.recommend(evidence, trust, bcse, trajectory)
        enforcement = self.enforcer.apply(response, session_ctx)
        self.audit_store.append_pipeline_records(...)
        return ProcessingResult(...)
```

All components are injected at construction time, enabling full mock-based unit testing of the processor itself.

---

## 6. API Design

Base path: `/api/v1`

### 6.1 Event Ingestion

| Method | Path | Description |
|---|---|---|
| `POST` | `/events` | Submit a single agent-action event |
| `POST` | `/events/batch` | Submit up to 100 events |
| `GET` | `/events/{event_id}` | Retrieve a processed event record |

### 6.2 Agent and Session Management

| Method | Path | Description |
|---|---|---|
| `POST` | `/agents` | Register an agent |
| `GET` | `/agents/{agent_id}` | Get agent record |
| `POST` | `/sessions` | Create a session |
| `GET` | `/sessions/{session_id}` | Get session state including trust |
| `DELETE` | `/sessions/{session_id}` | Terminate a session |

### 6.3 Capability Leases

| Method | Path | Description |
|---|---|---|
| `POST` | `/leases` | Grant a capability lease |
| `GET` | `/leases/{lease_id}` | Get lease record |
| `PATCH` | `/leases/{lease_id}/suspend` | Suspend a lease |
| `PATCH` | `/leases/{lease_id}/reinstate` | Reinstate a suspended lease |
| `DELETE` | `/leases/{lease_id}` | Revoke a lease |
| `GET` | `/sessions/{session_id}/leases` | List leases for a session |

### 6.4 Audit and Evidence

| Method | Path | Description |
|---|---|---|
| `GET` | `/audit` | Query audit records (filter by agent, session, type, time range) |
| `GET` | `/audit/{record_id}` | Get single audit record |
| `GET` | `/audit/provenance/{enforcement_id}` | Full provenance chain for an enforcement action |
| `GET` | `/audit/export` | Export audit records as JSON-L |
| `GET` | `/audit/verify` | Verify hash-chain integrity |

### 6.5 Evaluation

| Method | Path | Description |
|---|---|---|
| `POST` | `/evaluate/run` | Execute a named scenario |
| `GET` | `/evaluate/scenarios` | List available scenarios |
| `GET` | `/evaluate/results/{run_id}` | Get evaluation run results |

### 6.6 Common Response Envelope

```json
{
  "status": "success",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "data": { ... }
}
```

Error response:
```json
{
  "status": "error",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": [ ... ]
  }
}
```

---

## 7. Database Schema (PostgreSQL)

### 7.1 Core Tables

```sql
-- agents
CREATE TABLE agents (
    agent_id        TEXT PRIMARY KEY,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'
);

-- sessions
CREATE TABLE sessions (
    session_id      UUID PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at   TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    current_trust   FLOAT NOT NULL DEFAULT 0.7,
    trust_level     TEXT NOT NULL DEFAULT 'ELEVATED',
    state           TEXT NOT NULL DEFAULT 'ACTIVE'
);

-- events (TimescaleDB hypertable)
CREATE TABLE events (
    event_id            UUID NOT NULL,
    agent_id            TEXT NOT NULL,
    session_id          UUID NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    action_type         TEXT NOT NULL,
    capability_requested TEXT NOT NULL,
    target_resource     TEXT NOT NULL,
    execution_context   JSONB NOT NULL DEFAULT '{}',
    authorization_result TEXT NOT NULL,
    behavioral_signals  JSONB NOT NULL DEFAULT '{}',
    trust_signal        FLOAT,
    is_simulated        BOOLEAN NOT NULL,
    raw_payload         JSONB NOT NULL,
    PRIMARY KEY (event_id, timestamp)
);
SELECT create_hypertable('events', 'timestamp');

-- evidence_records
CREATE TABLE evidence_records (
    evidence_id         UUID PRIMARY KEY,
    event_id            UUID NOT NULL,
    session_id          UUID NOT NULL,
    agent_id            TEXT NOT NULL,
    anomaly_class       TEXT NOT NULL,
    score               FLOAT NOT NULL,
    weight              FLOAT NOT NULL,
    detector_id         TEXT NOT NULL,
    provenance          JSONB NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    is_simulated        BOOLEAN NOT NULL
);

-- trust_history
CREATE TABLE trust_history (
    entry_id            UUID PRIMARY KEY,
    session_id          UUID NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    prior_score         FLOAT NOT NULL,
    delta               FLOAT NOT NULL,
    new_score           FLOAT NOT NULL,
    contributing_evidence_id UUID
);

-- capability_leases
CREATE TABLE capability_leases (
    lease_id            UUID PRIMARY KEY,
    agent_id            TEXT NOT NULL,
    session_id          UUID NOT NULL,
    capability          TEXT NOT NULL,
    scope               JSONB NOT NULL DEFAULT '{}',
    granted_at          TIMESTAMPTZ NOT NULL,
    expires_at          TIMESTAMPTZ,
    issuing_policy_id   TEXT NOT NULL,
    state               TEXT NOT NULL DEFAULT 'ACTIVE',
    state_history       JSONB NOT NULL DEFAULT '[]'
);

-- response_recommendations
CREATE TABLE response_recommendations (
    recommendation_id   UUID PRIMARY KEY,
    session_id          UUID NOT NULL,
    agent_id            TEXT NOT NULL,
    event_id            UUID NOT NULL,
    response_type       TEXT NOT NULL,
    reason_codes        JSONB NOT NULL,
    evidence_bundle_id  UUID NOT NULL,
    trust_snapshot      JSONB NOT NULL,
    policy_id           TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL
);

-- enforcement_records
CREATE TABLE enforcement_records (
    enforcement_id      UUID PRIMARY KEY,
    recommendation_id   UUID NOT NULL,
    action_taken        TEXT NOT NULL,
    target_type         TEXT NOT NULL,
    target_id           TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    outcome             TEXT NOT NULL,
    dry_run             BOOLEAN NOT NULL DEFAULT FALSE
);

-- audit_log (append-only)
CREATE TABLE audit_log (
    record_id           UUID PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    record_type         TEXT NOT NULL,
    source_entity_id    TEXT NOT NULL,
    session_id          UUID,
    agent_id            TEXT,
    payload             JSONB NOT NULL,
    prior_record_hash   TEXT,
    record_hash         TEXT NOT NULL
);
-- No UPDATE or DELETE privileges should be granted on audit_log.
```

---

## 8. Configuration

All configuration is managed through Pydantic Settings, loadable from environment variables or YAML files.

```python
class TrustConfig(BaseModel):
    initial_score: float = 0.7
    sensitivity: float = 1.0
    temporal_decay_rate: float = 0.01   # per hour
    thresholds: Dict[str, float] = {
        "HIGH": 0.85,
        "ELEVATED": 0.65,
        "GUARDED": 0.40,
        "LOW": 0.20,
    }

class EvidenceConfig(BaseModel):
    correlation_window_seconds: float = 60.0
    enabled_detectors: List[str] = ["all"]   # ["all"] enables all
    detector_weights: Dict[str, float] = {}  # Overrides per detector_id

class VarynxConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VARYNX_")

    database_url: str
    trust: TrustConfig = TrustConfig()
    evidence: EvidenceConfig = EvidenceConfig()
    default_policy_path: str = "config/default_policy.yaml"
    dry_run_mode: bool = False
    log_level: str = "INFO"
    session_max_duration_seconds: float = 3600.0
```

---

## 9. Evaluation Framework Design

### 9.1 Scenario File Format (YAML)

```yaml
scenario_id: cap_escalation_01
label: "Capability escalation followed by authorization bypass"
description: >
  An agent with a lease for READ attempts WRITE then CREDENTIAL_ACCESS
  after a denial, exercising capability escalation and bypass detectors.
is_simulated: true
seed: 42

agents:
  - agent_id: agent-alpha
    leases:
      - capability: file:read
        scope: {resource_pattern: "/data/reports/*"}

events:
  - &e1
    event_id: "00000000-0000-0000-0000-000000000001"
    agent_id: agent-alpha
    action_type: READ
    capability_requested: "file:read"
    target_resource: "/data/reports/q3.csv"
    authorization_result: allowed
    is_simulated: true

  - <<: *e1
    event_id: "00000000-0000-0000-0000-000000000002"
    action_type: WRITE
    capability_requested: "file:write"
    target_resource: "/data/reports/q3.csv"
    authorization_result: denied
    is_simulated: true

  - <<: *e1
    event_id: "00000000-0000-0000-0000-000000000003"
    action_type: CREDENTIAL_ACCESS
    capability_requested: "credential:read"
    target_resource: "/secrets/api_keys"
    authorization_result: denied
    is_simulated: true

expected_outcomes:
  - event_id: "00000000-0000-0000-0000-000000000002"
    anomaly_classes: [CAPABILITY_ESCALATION]
    min_response: RESTRICT
  - event_id: "00000000-0000-0000-0000-000000000003"
    anomaly_classes: [AUTHORIZATION_BYPASS_ATTEMPT, CAPABILITY_ESCALATION]
    min_response: SUSPEND
```

### 9.2 Baseline Configurations

| Baseline | Evidence Engine | Trust Module | BCSE | Predictive |
|---|---|---|---|---|
| B1 — Policy-only | Disabled | Disabled | Disabled | Disabled |
| B2 — Risk threshold | Enabled | Disabled (static threshold) | Disabled | Disabled |
| B3 — Behavioral + Trust | Enabled | Enabled | Disabled | Disabled |
| B4 — Full system | Enabled | Enabled | Enabled (Phase 2) | Enabled (Phase 2) |

### 9.3 Metrics

| Metric | Definition |
|---|---|
| Detection Rate (DR) | TP / (TP + FN) |
| False Positive Rate (FPR) | FP / (FP + TN) |
| False Negative Rate (FNR) | FN / (FN + TP) |
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN) |
| F1 | 2 × Precision × Recall / (Precision + Recall) |
| Mean Time to Detection (MTTD) | Mean events between anomaly injection and first anomaly evidence |
| Mean Time to Response (MTTR) | Mean events between anomaly injection and enforcement action |
| Processing Latency P99 | 99th percentile of per-event pipeline duration (ms) |
| Computational Overhead | Additional CPU time per event vs. B1 baseline |

---

## 10. Dashboard UI Design (Phase 3)

### 10.1 Design Language

**Color System:**

| Token | Hex | Usage |
|---|---|---|
| `bg-base` | `#0B1120` | Application background |
| `bg-panel` | `#0F1A2E` | Cards, panels, sidebars |
| `bg-surface` | `#162237` | Table rows, inner panels |
| `bg-elevated` | `#1C2D45` | Hover states, selected rows |
| `accent-indigo` | `#6366F1` | Primary actions, active nav, selected state |
| `accent-indigo-dim` | `#4338CA` | Pressed states |
| `signal-cyan` | `#06B6D4` | Live data only — streaming indicators, active events |
| `state-nominal` | `#10B981` | Trust level HIGH, all-clear indicators |
| `state-elevated` | `#F59E0B` | Trust level GUARDED/ELEVATED, warnings |
| `state-critical` | `#EF4444` | Trust level LOW/CRITICAL, active threats |
| `text-primary` | `#F1F5F9` | Main text |
| `text-secondary` | `#94A3B8` | Labels, secondary data |
| `border-subtle` | `#1E3A5F` | Card borders, dividers |

Security state indicators MUST always combine color + icon + text label. Never use color alone.

**Typography:** Inter or Geist Sans. Monospace: JetBrains Mono for IDs, hashes, reason codes.

### 10.2 Page Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│  VARYNX                    [Live ●] [Evaluation] [Audit] [Settings]  │
│  ──────────────────────────────────────────────────────────────────  │
│  Sidebar                   │  Main Content Area                      │
│  ─ Overview                │                                         │
│  ─ Agents          ●3      │                                         │
│  ─ Sessions                │                                         │
│  ─ Evidence                │                                         │
│  ─ Trust                   │                                         │
│  ─ BCSE                    │                                         │
│  ─ Responses               │                                         │
│  ─ Leases                  │                                         │
│  ─ Audit                   │                                         │
│  ─ Evaluation              │                                         │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.3 Key Views

**Overview Dashboard:**
- System-wide trust distribution histogram (navy bars, indigo selected)
- Active sessions table: agent ID, trust level badge (colored + labeled), last event time, active lease count, action column
- Recent anomaly feed: scrolling list with anomaly class, session, score, timestamp
- Response recommendation summary: counts by type, sparkline of last 24h

**Session Detail:**
- Header: agent ID, session ID, trust score (large, color-coded), current level badge
- Trust history sparkline: full-width, midnight navy background, indigo line, cyan dot at current point
- Event timeline: chronological, color-coded by authorization result
- Evidence panel: collapsible per-event, shows detector outputs and scores
- Active leases table: capability, scope, state badge, expiry
- Response history: recommendation type, reason codes (expandable structured cards)
- BCSE results (Phase 2): side-by-side consequence comparison panels

**Counterfactual View (Phase 2):**
- Left: active policy consequence projection
- Right: alternative policy projections
- Divergence score meter
- Confidence badges per projection
- Clear "PROJECTED — not an observed fact" label on all outputs

**Audit View:**
- Filterable table: type, agent, session, time range
- Hash-chain verification status (green checkmark or red warning)
- Expandable provenance chain per enforcement action
- Export button (JSON-L)

**Evaluation View:**
- Scenario selector
- Baseline comparison matrix (B1–B4 metrics side by side)
- Metric cards: DR, FPR, F1, MTTD, MTTR with confidence intervals
- Per-run result history table
- Ablation toggle panel: enable/disable individual detectors and modules

---

## Error Handling

1. **Audit log append-only enforcement:** The PostgreSQL role for the application MUST NOT have UPDATE or DELETE privileges on `audit_log`. Hash-chain verification provides a second tamper-detection layer.

2. **Simulated event isolation:** `is_simulated` is a non-nullable required field at ingestion. All queries and reports MUST support filtering by this field. Evaluation reports MUST state whether they include simulated data.

3. **No live LLM dependency in Phase 1:** The framework-independent event model means the security engine never calls an LLM. Framework adapters (future) will be separate packages that translate LLM agent output into `AgentActionEvent` records.

4. **BCSE is advisory and separated from evidence:** BCSE results are stored separately from evidence records. The audit log records BCSE analysis as a distinct record type. No BCSE projected consequence is ever stored as an `EvidenceRecord` or used to update trust directly.

5. **Input validation boundary:** All API inputs are validated by Pydantic before reaching any internal component. Internal components assume validated data and do not re-validate.

6. **Configuration-driven, not code-driven policy:** Security policy lives in YAML files, not in Python logic. Changing a policy does not require a code change, enabling rapid experimentation.

---

## 12. Interface Stability Contract

The following interfaces are considered stable after Phase 1 completion and MUST NOT be changed without a version bump:

- `AgentActionEvent` — the primary ingestion schema
- `EvidenceRecord` and `EvidenceBundle`
- `TrustState` and `TrustHistoryEntry`
- `ResponseRecommendation` and `ReasonCode`
- `AuditRecord`
- The `AnomalyDetector` Protocol
- The `BCSeEngine` Protocol (stub or real)
- The `PredictiveEngine` Protocol (stub or real)

Phase 2 implementations of BCSE and predictive engines must conform to the Phase 1 protocol without breaking existing tests.

---

## Correctness Properties

*Property-based testing (PBT) verifies universal invariants that hold across all valid inputs. The following properties define the formal correctness contract for Varynx. All properties are PROPOSED — Not Yet Implemented; no property has been verified by a passing test suite at the time of authoring. Property tests will be implemented using Hypothesis alongside the component implementations.*

---

### Property 1: Trust score is always in [0.0, 1.0]

*For any* combination of current trust score, evidence bundle composite score, evidence weight, sensitivity parameter, temporal decay rate, and session age, the trust score update formula SHALL produce a value in [0.0, 1.0] inclusive. No input combination may yield a value outside this range.

**Validates: Requirements 4.4**

---

### Property 2: Evidence scores are always in [0.0, 1.0]

*For any* agent action event and detector configuration, each `EvidenceRecord.score`, `EvidenceRecord.weight`, and `EvidenceBundle.composite_score` SHALL be in [0.0, 1.0] inclusive.

**Validates: Requirements 4.3**

---

### Property 3: BCSE evaluation is non-interfering

*For any* `BCSeContext` submitted to the BCSE engine, the behavioral event log, evidence store, agent context records, and capability lease records SHALL be identical before and after the BCSE evaluation call. BCSE SHALL NOT create, modify, or delete any record in those stores.

**Validates: Requirements 4.5**

---

### Property 4: Response recommendations are deterministic

*For any* `(EvidenceBundle, TrustState, active_policy)` triple, the Adaptive Response Engine SHALL produce identical `ResponseType` and `ReasonCode` list on repeated invocations under identical configuration.

**Validates: Requirements 4.7**

---

### Property 5: REVOKED capability leases are a terminal state

*For any* `CapabilityLease` in `REVOKED` state, no event sequence SHALL cause a transition to `ACTIVE`, `SUSPENDED`, or `EXPIRED`. Revocation is terminal.

**Validates: Requirements 4.8**

---

### Property 6: Enforcement is idempotent

*For any* `ResponseRecommendation`, applying the same recommendation twice SHALL produce the same final state. The second application produces an `EnforcementRecord` with `outcome=SKIPPED` and `outcome_reason=DUPLICATE_ENFORCEMENT`.

**Validates: Requirements 4.9**

---

### Property 7: Audit log is append-only with hash-chain integrity

*For any* `AuditRecord` after creation, no `UPDATE` or `DELETE` operation SHALL succeed against the `audit_log` table. The hash-chain integrity verification SHALL return `TAMPER_DETECTED` for any modified record.

**Validates: Requirements 4.10**

---

### Property 8: Simulated events are clearly labeled throughout the pipeline

*For any* event with `is_simulated = true` at ingestion, the flag SHALL be preserved through storage, evidence derivation, trust scoring, response recommendation, and all evaluation outputs. Simulated events SHALL NOT be mixed with live events in evaluation metrics without explicit configuration.

**Validates: Requirements 6.1**

---

### Property 9: Correlation identifiers are unique and propagated end-to-end

*For any* batch of accepted events, all assigned `correlation_id` values SHALL be distinct. The `correlation_id` SHALL be propagated unchanged to all associated evidence records, response recommendations, enforcement records, and audit records.

**Validates: Requirements 4.10**

---

### Property 10: API serialization round-trip preserves all fields

*For any* valid API request object (including `AgentActionEvent`, `BCSeContext`, and all response models), `deserialize(serialize(obj)) == obj` SHALL hold — no field loss or type coercion SHALL occur.

**Validates: Requirements 4.7**

---

*End of Correctness Properties. All 10 properties are PROPOSED — Not Yet Implemented.*

---

## Testing Strategy

All testing uses **pytest** as the test runner and **Hypothesis** for property-based testing. Core behavioral analysis components are independently unit-testable without a running database or external services — all storage and external dependencies are injectable and replaceable with in-memory stubs.

### Test Layers

| Layer | Scope | Key Invariants |
|-------|-------|----------------|
| Unit tests | Individual components (evidence detectors, trust scorer, response engine, lease manager, audit store, enforcement layer) | Each component's acceptance criteria verified in isolation with injected mocks |
| Property-based tests | Hypothesis-generated inputs across all public interfaces | Trust score range [0.0, 1.0], evidence score range [0.0, 1.0], response determinism, lease state machine terminal state, correlation_id uniqueness, API serialization round-trip |
| Integration tests | Full event-to-enforcement pipeline using the evaluation harness | Dry-run mode, audit chain integrity, provenance queries, BCSE non-interference, pipeline resilience to malformed events |
| Benchmark tests | Performance thresholds (NFR-PERF-001/002/003) | Single-event P99 ≤ 50ms, batch throughput ≥ 100 events/second, BCSE ≤ 200ms for 50-evidence context |

### Determinism and Reproducibility

All deterministic components (evidence engine, trust module, BCSE, response engine) SHALL produce identical output for identical input and configuration, regardless of execution environment. The `reproduce.sh` script enables any reviewer to install dependencies, run the full evaluation harness, and reproduce evaluation reports from published scenario files.

### Status

All testing is PROPOSED — Not Yet Implemented. No test has been written or executed at the time of authoring. Test implementation is scheduled in Phases 1–12 of `tasks.md`, with property-based tests concentrated in Phase 10.
