# Varynx — Behavioral Risk Control Engine for Autonomous AI Agents
## Technical Design Specification

**Version:** 1.0  
**Status:** PROPOSED — Not Yet Implemented  
**Companion Document:** `requirements.md` (REQ-001 through REQ-027)  
**Repository State at Authoring:** Empty workspace — all interfaces and designs are specified forward from the approved research direction. No component described below has been implemented or verified.

---

## Overview

### 1.1 Central Research Question

> Can a cloud-native behavioral risk control engine — operating on structured event streams from autonomous AI agents without access to model internals — produce security-relevant signals (anomaly detection, trust scoring, and pre-action risk projection) that are measurably more informative than static rule-based baselines, while maintaining auditability and reproducibility?

This question drives all design decisions. Varynx is simultaneously a security infrastructure component and a research instrument. Every pipeline stage must support both operational use and reproducible experimental evaluation.

### 1.2 Hypotheses

The following four falsifiable hypotheses guide empirical evaluation. No results are pre-claimed. All hypotheses are defined prior to any experimental execution per REQ-024.

**H1 — Behavioral Evidence Utility**  
Multi-dimensional behavioral evidence (combining authorization events, resource scope, capability spread, and cross-context correlation) will detect anomalous agent behavior with higher F1 score than a single-dimension rule-based baseline on the same synthetic scenario datasets.

**H2 — Dynamic Trust Score Responsiveness**  
A Behavioral_Trust_Score updated after each event will reflect behavioral changes within a measurably shorter number of events than a session-averaged score computed only at session end.

**H3 — BCSE Predictive Value**  
BCSE projected risk levels (LOW/MEDIUM/HIGH/CRITICAL) for proposed actions will agree with the ground-truth anomaly classification of those actions in scenario files at a rate greater than chance and greater than a naive always-LOW prior.

**H4 — Adaptive Response Proportionality**  
The Adaptive_Response_Engine will escalate Response_Recommendations in proportion to Behavioral_Trust_Score decline rate: scenarios with faster score decline will receive escalated recommendations in fewer events than scenarios with slower decline rates.

### 1.3 Phase Scope

| Phase | Name | Scope |
|-------|------|-------|
| **Phase 1 — MVP** | Core pipeline | Event ingestion and validation; agent context and session registry; behavioral evidence engine (all 6 detector types); dynamic trust scoring; adaptive response engine; capability lease lifecycle; runtime enforcement (with dry-run); audit log and hash-chain; evaluation framework (B1–B3 baselines, scenario runner, metrics); REST API; BCSE stub; predictive stub |
| **Phase 2 — Research Depth** | Full intelligence | BCSE engine (policy simulation, consequence projection, divergence scoring); predictive trajectory engine (trend analysis, early-warning signals); cross-session trust aggregation; baseline B4; framework adapter contract; advanced ablation and statistical analysis |
| **Phase 3 — Platform** | Analyst dashboard | Next.js analyst dashboard; multi-agent federation; production SLA hardening; multi-tenancy |

**Out of scope (all phases):** formal proof or model checking, LLM-required operation, guaranteed attacker prediction, production access control enforcement (Varynx provides recommendations only), real-time detection SLA guarantees for adversarial environments.

---

## 2. Architectural Principles and Explicit Non-Goals

### 2.1 Core Principles

**Framework-Independent Core (REQ-023)**  
The Varynx core engine never imports or calls any AI agent framework. All framework coupling lives in separately packaged adapters. The `AgentActionEvent` model is the stable ingestion boundary.

**Determinism and Reproducibility (REQ-015, REQ-025)**  
Given identical input events, configuration snapshot, random seed, and software version, every pipeline component must produce identical outputs. Non-determinism from clocks and network is isolated and documented. This principle enables hypothesis testing and independent replication.

**Strict Separation of Record Types**  
The following record types are distinct, never mixed, and stored in separate subsystems (REQ-017):

| Record Type | Store | Description |
|-------------|-------|-------------|
| `Behavioral_Event` | Behavioral event log | Immutable observed fact: an agent performed an action |
| `Evidence_Record` | Evidence store | Derived signal: a detector's interpretation of one or more events |
| `Projected consequence` (BCSE) | In-memory / response store only | Forward estimate; NEVER stored as Evidence_Record |
| `Security_Decision` | Decision store | Recommendation to enforcement; NOT an enforcement outcome |
| `Enforcement_Record` | Audit log | Record of what enforcement layer did with a recommendation |
| `Audit_Record` | Audit log | Tamper-evident ledger entry; references other records by ID only |

**No Silent Evidence Fabrication (REQ-003, REQ-014)**  
When source Behavioral_Event data is absent or an Evidence_Record fails integrity verification, the system records `EVIDENCE_DERIVATION_INCOMPLETE` or `INTEGRITY_VIOLATION` status and excludes the record from all downstream computation. Nothing is invented or estimated as a substitute.

**No Metric Fabrication (REQ-015, REQ-026)**  
All evaluation metrics are derived exclusively from pipeline outputs on real dataset inputs. No interpolation, smoothing, or manual adjustment is permitted at any stage.

**BCSE is Advisory and Non-Interfering (REQ-007)**  
BCSE evaluation is a read-and-project operation. It never writes to the behavioral event log, evidence store, agent context records, or capability lease states. BCSE results are never stored as Evidence_Records and never directly update trust scores.

**Dashboard Authorization Parity (REQ-018)**  
The analyst dashboard has no privileged API surface. Every dashboard action is executed via the same authenticated REST API endpoints available to any API_Consumer, subject to identical authorization rules.

### 2.2 Explicit Non-Goals

- **Not a formal proof system.** Trust scores and BCSE projections are heuristic model outputs, not mathematical proofs of agent behavior.
- **Not a model checker.** Varynx does not verify agent program logic or state space.
- **Not a statistical potential-outcomes model.** BCSE is not a causal inference framework; it does not compute counterfactual distributions.
- **Not an exact attacker predictor.** No BCSE output constitutes a definitive security verdict. All projections carry uncertainty quantification.
- **Not an enforcement engine.** Varynx transmits recommendations to enforcement infrastructure. It does not apply access control decisions itself.
- **Not LLM-dependent.** The core engine operates entirely on structured `AgentActionEvent` records without requiring a live LLM or agent runtime.

---

## 3. Repository Status

**At the time this document was authored, the repository workspace is empty.** No source files, configuration files, test files, migrations, or Docker assets have been created. This design document is a forward specification. All data models, component designs, database schemas, API contracts, and configuration structures described below are proposals awaiting implementation.

### 3.1 Proposed Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.11+ | Research-friendly; rich statistical and testing ecosystem |
| API framework | FastAPI | Async, automatic OpenAPI generation, Pydantic-native validation |
| Data validation | Pydantic v2 (strict mode) | Fast, declarative, IDE-friendly; strict=True eliminates type coercion surprises |
| Primary persistence | PostgreSQL 15 + TimescaleDB | Time-series hypertables for event streams; ACID guarantees for audit log |
| Event replay cache | Redis Streams (optional) | Lightweight replay buffer for evaluation harness |
| Testing | pytest + Hypothesis | Unit, property-based, and integration testing |
| Linting / type checking | ruff + mypy | Fast, strict |
| Containerization | Docker + docker-compose | Reproducible local and CI environments |
| Dashboard (Phase 3) | Next.js 14 + Tailwind CSS | Composable, performant, research analyst dashboard |
| Database migrations | Alembic | Schema version control |
| Configuration | Pydantic Settings + YAML | Environment-aware, schema-validated |

---

## Components and Interfaces

Each component entry specifies: name, primary responsibility, inputs, outputs, failure mode, security invariant, and delivery phase.

---

### 4.1 Ingestion & Validation Layer
**Satisfies:** REQ-001, REQ-023, REQ-027

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Accept inbound `AgentActionEvent` payloads; validate schema completeness and field constraints; enforce idempotency via `action_id`; label `is_simulated`; assign `correlation_id`; reject invalid payloads with structured errors |
| **Inputs** | Raw API request body |
| **Outputs** | `ValidatedEvent` with assigned `event_id` and `correlation_id`; or structured HTTP 422/409 error |
| **Failure mode** | Malformed events are rejected with HTTP 422 and structured field-level errors. Processing pipeline continues for subsequent events. A single malformed event never crashes the pipeline (REQ-027.4) |
| **Security invariant** | All inputs are schema-validated before any internal component receives them. No unvalidated data reaches the evidence engine or trust module |
| **Phase** | 1 |

---

### 4.2 Identity & Session Registry
**Satisfies:** REQ-002, REQ-006

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Maintain `Agent_Context` records per distinct `agent_id`; create records on first observation; detect and flag scope escalation and capability escalation; manage session lifecycle; track resource and capability spread per agent |
| **Inputs** | `ValidatedEvent` |
| **Outputs** | `SessionContext` (agent record + current session state + lease associations) |
| **Failure mode** | If agent context cannot be read or created, the event is rejected with HTTP 503 and `STORAGE_SUBSYSTEM_UNAVAILABLE` logged |
| **Security invariant** | `agent_id` and `owning_principal` fields on an `Agent_Context` record are immutable after creation (REQ-002.5). Scope escalation detection is applied on every event, not only on first observation |
| **Phase** | 1 |

---

### 4.3 Capability Lease Manager
**Satisfies:** REQ-010

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Create, evaluate, suspend, reinstate, revoke, and expire `Capability_Lease` records; enforce the four-state lifecycle (ACTIVE → EXPIRED/SUSPENDED/REVOKED); cascade suspension and revocation when triggered by `ResponseRecommendation` |
| **Inputs** | `ValidatedEvent`; `ResponseRecommendation` from the Adaptive Response Engine |
| **Outputs** | `LeaseEvaluation` (whether the event's requested capability is within an active lease); updated `CapabilityLease` records |
| **Failure mode** | Lease state storage unavailability returns HTTP 503. Expiry transition failures are logged and retried; the lease is not silently left in ACTIVE state |
| **Security invariant** | A REVOKED lease never transitions to any other state (REQ-010.6). Expiry timestamp modification is not permitted after activation (REQ-010.9). Reinstatement of SUSPENDED leases requires an explicit authorized request and produces an `Audit_Record` |
| **Phase** | 1 |

---

### 4.4 Behavioral Evidence Engine
**Satisfies:** REQ-003, REQ-004

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Orchestrate the configurable detector pipeline; derive `EvidenceRecord` instances from each detector; correlate records within the configured time window; compute `composite_score`; bundle into `EvidenceBundle`; compute and store cryptographic hash per record |
| **Inputs** | `ValidatedEvent`, `SessionContext`, `LeaseEvaluation` |
| **Outputs** | `EvidenceBundle` (containing one `EvidenceRecord` per triggered detector) |
| **Failure mode** | If a detector raises a runtime exception, the error is logged with `detector_id`, the detector is skipped for this event, and processing continues (REQ-004.7). No detector error propagates to other detectors |
| **Security invariant** | Evidence records are immutable after storage (REQ-003.5). Cryptographic hash is computed and stored on creation (REQ-003.6). `EVIDENCE_DERIVATION_INCOMPLETE` status is recorded when source data is insufficient; such records are never used in scoring (REQ-003.4) |
| **Phase** | 1 |

**Detector types (all Phase 1):**

| Detector ID | Anomaly Class | Detection Logic |
|-------------|---------------|-----------------|
| `capability_escalation` | `CAPABILITY_ESCALATION` | Action type falls outside Agent's declared capability scope (REQ-002.4) |
| `resource_anomaly` | `RESOURCE_ANOMALY` | Resource spread exceeds configurable domain threshold within time window (REQ-004.3, REQ-006) |
| `action_frequency` | `ACTION_FREQUENCY` | Action rate exceeds configurable threshold within sliding window |
| `authorization_bypass` | `AUTHORIZATION_BYPASS_ATTEMPT` | Three or more authorization denials within configurable window (default 300s) (REQ-004.2) |
| `context_deviation` | `CONTEXT_DEVIATION` | Cross-context behavioral correlation: same agent's actions correlate to two or more distinct agent identities or task contexts within a single session (REQ-004.4) |
| `temporal_anomaly` | `TEMPORAL_ANOMALY` | Actions at statistically unusual times relative to the agent's historical pattern |

---

### 4.5 Dynamic Trust Module
**Satisfies:** REQ-005, REQ-021

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Maintain `TrustState` per agent; update score using the documented deterministic formula after each event; classify score into `TrustLevel`; append a `TrustHistoryEntry` per update; store score history for trajectory analysis |
| **Inputs** | Current `TrustState`, `EvidenceBundle`, `TrustConfig` |
| **Outputs** | Updated `TrustState` |
| **Failure mode** | If score computation produces a value outside [0.0, 1.0] due to floating-point edge cases, it is clamped and the anomaly is logged. If trust storage is unavailable, HTTP 503 is returned |
| **Security invariant** | Score is always in [0.0, 1.0] inclusive (REQ-005.2). `EVIDENCE_DERIVATION_INCOMPLETE` records are excluded from score computation and the exclusion count is recorded in score metadata (REQ-005.4). No score recovery in Phase 1 |
| **Phase** | 1 |

---

### 4.6 BCSE Engine
**Satisfies:** REQ-007, REQ-008

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Evaluate a proposed (not yet executed) agent action against current evidence and trust state; return projected risk level, uncertainty score, rationale, and supporting evidence references; never modify event log or evidence store |
| **Inputs (Phase 1 stub)** | `BCSeContext` |
| **Outputs** | `BCSeResult` |
| **Phase 1 stub behavior** | Returns `is_stub=True`; `active_consequence` mirrors current policy recommendation; `counterfactual_consequences` is empty list; `divergence_score` is 0.0; uncertainty reflects history depth |
| **Phase 2 engine behavior** | Policy simulation across `PolicyAlternative` list; consequence projection per policy; divergence scoring; confidence from evidence density |
| **Failure mode** | Internal error during BCSE evaluation returns HTTP 503 with `BCSE_EVALUATION_FAILED`. No partial or fabricated result is returned (REQ-007.8). Pipeline continues with stub result |
| **Security invariant** | BCSE never writes to behavioral event log, evidence store, agent context, or lease state (REQ-007.3, REQ-007.4). Projected consequences are never stored as `EvidenceRecord` entries. BCSE evaluation result is stored separately from evidence |
| **Phase** | 1 (stub), 2 (full) |

---

### 4.7 Predictive Intelligence Layer
**Satisfies:** REQ-021

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Maintain `Security_Trajectory` classification per agent; project future `Behavioral_Trust_Score` at configurable horizon; emit `EARLY_WARNING_TRAJECTORY_BREACH` signals; label all projected values with `PROJECTED` marker |
| **Inputs** | Current `TrustState` (with history) |
| **Outputs** | `TrajectoryProjection` |
| **Phase 1 stub behavior** | Always returns `TrendDirection.STABLE`, `is_stub=True`, `early_warning=False` |
| **Phase 2 engine behavior** | Window-based trend analysis over `TrustHistoryEntry` records using linear regression; configurable window size and horizon; 95% confidence interval computation |
| **Failure mode** | Runtime error in trend computation falls back to STABLE stub, logs `TRAJECTORY_COMPUTATION_ERROR`, and does not affect other agents (REQ-021.9) |
| **Security invariant** | Projected values never stored as `EvidenceRecord` entries (REQ-021.7). All projected values labeled `PROJECTED` in all API responses, dashboard views, and log entries (REQ-021.6) |
| **Phase** | 1 (stub), 2 (full) |

---

### 4.8 Adaptive Response Engine
**Satisfies:** REQ-009, REQ-011

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Map `(TrustLevel, AnomalyClass[])` to `ResponseType` using a configurable policy table; enforce escalation logic; prevent de-escalation without an explicit de-escalation event; record policy table version and inputs as metadata on the Security_Decision |
| **Inputs** | `EvidenceBundle`, `TrustState`, `BCSeResult`, `TrajectoryProjection`, active policy |
| **Outputs** | `ResponseRecommendation` (a Security_Decision) |
| **Failure mode** | If the policy table is invalid or missing at startup, the system fails to start with `POLICY_TABLE_INVALID` error (REQ-020.2). At runtime, falls back to `MONITOR` and logs `POLICY_TABLE_INVALID` (REQ-011.7) |
| **Security invariant** | Decision generation is deterministic: identical inputs and configuration produce identical `ReasonCode` and `ResponseType` (REQ-009.3). Security_Decisions are clearly labeled as recommendations, never as enforcement outcomes (REQ-009.4). Security_Decision is stored before it is transmitted to the Enforcement_Boundary (REQ-009.5) |
| **Phase** | 1 |

---

### 4.9 Runtime Enforcement Layer
**Satisfies:** REQ-022

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Translate `ResponseRecommendation` into concrete enforcement actions; validate policies independently; produce `EnforcementRecord` per action; support dry-run mode; enforce audit-before-action ordering; guarantee idempotency |
| **Inputs** | `ResponseRecommendation` |
| **Outputs** | `EnforcementRecord` |
| **Failure mode** | If audit log write fails before enforcement, the action is not applied (REQ-022.5). Policy validation rejection produces an `EnforcementRecord` with outcome `SKIPPED` and `POLICY_VALIDATION_REJECTED` reason (REQ-022.7) |
| **Security invariant** | Enforcement layer cannot be bypassed by the behavioral engine (architectural constraint). Dry-run records have `dry_run=True` and are never used as inputs to trust computation or decision generation (REQ-022.4). Idempotency: repeated same recommendation for same agent with same `recommendation_id` produces `SKIPPED` with `DUPLICATE_ENFORCEMENT` reason (REQ-022.8) |
| **Phase** | 1 |

---

### 4.10 Audit Log & Evidence Provenance Store
**Satisfies:** REQ-013, REQ-014, REQ-012

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Accept append-only `AuditRecord` writes from all pipeline components; compute and store SHA-256 hash-chain; support integrity verification on demand; serve traceability queries by `correlation_id`; detect and report `TAMPER_DETECTED` |
| **Inputs** | `AuditRecord` from any pipeline component |
| **Outputs** | Stored `AuditRecord`; hash-chain verification results; traceability query results |
| **Failure mode** | If the audit log is unavailable, enforcement does not proceed (REQ-022.5). HTTP 503 is returned to callers (REQ-017.4). `STORAGE_SUBSYSTEM_UNAVAILABLE` is logged |
| **Security invariant** | Append-only: no `UPDATE` or `DELETE` privilege is granted on `audit_log` table (REQ-013.3). `AuditRecord` entries reference source records by identifier; they do not reproduce content (REQ-013.6). Hash-chain recomputation detects any modification (REQ-013.4) |
| **Phase** | 1 |

---

### 4.11 Evaluation Framework
**Satisfies:** REQ-015, REQ-025, REQ-026

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Load and validate YAML scenario files; execute the full behavioral analysis pipeline against scenario events; compute detection metrics; support ablation configuration; support baseline comparisons (B1–B4); produce structured evaluation reports with statistical summaries; support adversarial evasion scenarios |
| **Inputs** | Scenario YAML files; baseline configuration; random seed; configuration snapshot |
| **Outputs** | Structured evaluation report with per-run metrics, statistical summaries (mean, std, 95% CI), effect sizes, and `SCENARIO_EXPECTATION_MISMATCH` entries |
| **Failure mode** | Invalid scenario files are rejected with `SCENARIO_VALIDATION_FAILED` and skipped (REQ-025.4). Mislabeled ground-truth annotations cause events to be skipped with the count reported (REQ-015.9). Fewer than minimum runs marks the report `INCOMPLETE` (REQ-026.6) |
| **Security invariant** | Simulated events (`is_simulated=True`) are never mixed with non-simulated events in the same evaluation metric computation without explicit configuration (REQ-027.12). Scenario outcome annotations are never modified to match observed results (REQ-025.6). Metrics are never fabricated (REQ-015.8) |
| **Phase** | 1 (B1–B3), 2 (B4 with full BCSE and predictive) |

---

### 4.12 REST API Layer
**Satisfies:** REQ-016

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Expose all Varynx capabilities via versioned REST endpoints; validate all requests against JSON schemas; authenticate and authorize every request; return structured error responses; enforce rate limiting; propagate `correlation_id` in all responses |
| **Inputs** | HTTP requests |
| **Outputs** | HTTP responses conforming to the versioned OpenAPI specification |
| **Failure mode** | Validation failures return HTTP 422 with field-level error list. Unauthenticated requests: HTTP 401. Unauthorized: HTTP 403. Rate exceeded: HTTP 429. Oversized body: HTTP 413. Internal errors: HTTP 503 with error code |
| **Security invariant** | All API inputs are schema-validated before any internal component is reached (REQ-016.2, REQ-027.8). Authentication is required for all endpoints (REQ-016.3). Authorization is enforced per principal (REQ-016.4) |
| **Phase** | 1 |

---

### 4.13 Dashboard UI (Phase 3)
**Satisfies:** REQ-018

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Provide a web-based analyst interface for reviewing agent security profiles, Security_Decisions, Capability_Lease states, audit records, and evaluation results |
| **Inputs** | REST API responses |
| **Outputs** | Rendered analyst views |
| **Failure mode** | API errors display non-technical error messages; internal error details and stack traces are never shown to the analyst (REQ-018.8) |
| **Security invariant** | Dashboard has no privileged API surface. All actions execute via authenticated REST API (REQ-018.4). Sensitive `Behavioral_Event` payload fields are redacted in the UI (REQ-018.7). WCAG 2.1 Level AA required (REQ-018.5) |
| **Phase** | 3 |

---

### 4.14 Framework Adapter Contract (Phase 2+)
**Satisfies:** REQ-023

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Define the `AgentAdapterProtocol` typed interface for translating framework-specific events into `AgentActionEvent`; provide the `SimulatedEventAdapter` reference implementation; validate all adapter output against `AgentActionEvent` schema before pipeline ingestion |
| **Inputs** | Framework-specific event objects |
| **Outputs** | `AgentActionEvent` |
| **Failure mode** | Adapter exceptions are caught, logged as `ADAPTER_TRANSLATION_ERROR` with `framework_id` and sanitized description, and do not propagate to the behavioral analysis pipeline (REQ-023.5). Invalid adapter output is rejected with `ADAPTER_OUTPUT_INVALID` and not stored (REQ-023.8) |
| **Security invariant** | Core engine never imports or requires any live agent framework. Adapters are separately packaged optional modules (REQ-023.7). Framework decoupling is a hard boundary |
| **Phase** | Phase 1 (`SimulatedEventAdapter` only), Phase 2+ (real framework adapters) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  REST API  (FastAPI)                              REQ-016             │
│  /events  /agents  /sessions  /leases  /bcse                        │
│  /audit   /evaluate  /health  /config                               │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  Raw HTTP request
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Ingestion & Validation Layer                     REQ-001, REQ-023   │
│  Schema validation · Field completeness · Timestamp bounds          │
│  Idempotency (action_id) · correlation_id assignment                │
│  is_simulated labeling · HTTP 422/409 on rejection                  │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  ValidatedEvent
                          ▼
           ┌──────────────┴──────────────┐
           │                             │
           ▼                             ▼
┌──────────────────────┐      ┌──────────────────────────────────────┐
│  Identity & Session  │      │  Capability Lease Manager            │
│  Registry            │      │  REQ-010                             │
│  REQ-002, REQ-006    │◄────►│  Grant · Suspend · Revoke · Expire   │
│  Agent records       │      │  Scope evaluation                    │
│  Session lifecycle   │      │  Cascade on SUSPEND/TERMINATE        │
│  Spread tracking     │      │                                      │
└──────────┬───────────┘      └─────────────┬────────────────────────┘
           │  SessionContext                │  LeaseEvaluation
           └──────────────┬────────────────┘
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Behavioral Evidence Engine                       REQ-003, REQ-004   │
│  Detector pipeline (6 detector types)                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ capability_     │  │ resource_       │  │ action_frequency    │ │
│  │ escalation      │  │ anomaly         │  │                     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │ authorization_  │  │ context_        │  │ temporal_anomaly    │ │
│  │ bypass          │  │ deviation       │  │                     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│  Evidence correlation · Composite score · Hash per record           │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  EvidenceBundle
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Dynamic Trust Module                             REQ-005, REQ-021   │
│  Score update formula (deterministic) · Clamp [0.0, 1.0]           │
│  TrustLevel classification · TrustHistoryEntry append               │
│  Security_Trajectory stub (Phase 1) / computed (Phase 2)           │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  TrustState
            ┌─────────────┴──────────────┐
            │                            │
            ▼                            ▼
┌───────────────────┐        ┌───────────────────────────────────────┐
│  BCSE Engine      │        │  Predictive Intelligence Layer        │
│  REQ-007, REQ-008 │        │  REQ-021                              │
│  Phase 1: stub    │        │  Phase 1: always STABLE stub          │
│  Phase 2: full    │        │  Phase 2: trend analysis + EWS        │
│  (read-only)      │        │  All outputs labeled PROJECTED        │
└─────────┬─────────┘        └──────────────┬────────────────────────┘
          │  BCSeResult                      │  TrajectoryProjection
          └─────────────┬────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Adaptive Response Engine                         REQ-009, REQ-011   │
│  Policy YAML evaluation (priority-ordered rules)                    │
│  TrustLevel × AnomalyClass → ResponseType                          │
│  Escalation enforcement · Reason code assignment                    │
│  Store-before-transmit · Deterministic output                       │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  ResponseRecommendation
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Runtime Enforcement Layer                        REQ-022            │
│  Independent policy validation · Audit-before-action               │
│  Dry-run mode · Idempotency (DUPLICATE_ENFORCEMENT)                 │
│  Cascade lease SUSPEND/REVOKE via Lease Manager                     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  EnforcementRecord
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Audit Log & Evidence Provenance Store            REQ-013, REQ-012   │
│  Append-only · SHA-256 hash-chain · Tamper detection                │
│  Traceability query by correlation_id                               │
│  CHAIN_INTEGRITY_VIOLATION detection                                │
└──────────────────────────────────────────────────────────────────────┘
                          ▲
          All pipeline components emit AuditRecord entries
                          │
┌──────────────────────────────────────────────────────────────────────┐
│  Evaluation Framework                     REQ-015, REQ-025, REQ-026  │
│  Scenario runner (YAML) · Baseline comparisons B1–B4               │
│  Ablation config · Statistical analysis (mean, std, 95% CI)        │
│  Adversarial evaluation · Reproducibility (seed + version)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6. End-to-End Data Flow

This section narrates the processing of a single `AgentActionEvent` from API submission through enforcement and audit recording.

1. **API receipt.** An `API_Consumer` sends `POST /api/v1/events` with an `AgentActionEvent` JSON body. The REST API layer (REQ-016) applies JSON schema validation as the first processing step. If any required field is missing, HTTP 422 is returned with a field-level error list. If the body exceeds the configured maximum size (default 1 MB), HTTP 413 is returned immediately (REQ-016.8).

2. **Ingestion and validation.** The Ingestion & Validation Layer (REQ-001) verifies: all required fields present; `timestamp` within ±300/60 second bounds; `action_id` uniqueness for this `agent_id`. On success, a `correlation_id` (128-bit entropy, non-sequential) is assigned and the event is stored durably in the behavioral event log. A `ValidatedEvent` is produced.

3. **Session context.** The Identity & Session Registry (REQ-002) looks up or creates an `Agent_Context` record for the `agent_id`. If the event's `resource_scope` falls outside the agent's authorized scope, `SCOPE_ESCALATION_DETECTED` is flagged and the scope escalation counter is incremented. If the `action_type` falls outside declared capability scope, `CAPABILITY_ESCALATION_DETECTED` is flagged. A `SessionContext` is produced.

4. **Lease evaluation.** The Capability Lease Manager (REQ-010) evaluates whether the requested capability is covered by any `ACTIVE` lease. The result (`LeaseEvaluation`) is passed to the evidence engine.

5. **Evidence derivation.** The Behavioral Evidence Engine (REQ-003, REQ-004) runs the six configured detectors. Each detector receives the `ValidatedEvent`, `SessionContext`, and `LeaseEvaluation`, and returns an `Optional[EvidenceRecord]`. Triggered detectors return records; non-triggered detectors return `None`. A cryptographic hash is stored per record. All records are correlated within the configured time window, a `composite_score` is computed, and an `EvidenceBundle` is produced. One or more `Evidence_Record` entries are stored in the evidence store, each linked to the originating event via `correlation_id`.

6. **Trust update.** The Dynamic Trust Module (REQ-005) applies the deterministic score update formula to produce a new `TrustState`. The previous score, new score, delta, timestamp, and contributing evidence IDs are stored as a `TrustHistoryEntry`. The score is clamped to [0.0, 1.0].

7. **BCSE evaluation (Phase 1: stub).** The BCSE Engine (REQ-007) receives a `BCSeContext` derived from the `ValidatedEvent`, `EvidenceBundle`, `TrustState`, and active policy. The Phase 1 stub returns a `BCSeResult` with `is_stub=True`, no counterfactuals, and a `divergence_score` of 0.0. BCSE does not write to any store.

8. **Trajectory projection (Phase 1: stub).** The Predictive Intelligence Layer (REQ-021) receives the `TrustState`. The Phase 1 stub returns a `TrajectoryProjection` with `TrendDirection.STABLE` and `is_stub=True`.

9. **Response recommendation.** The Adaptive Response Engine (REQ-009, REQ-011) evaluates the configured policy table against `(TrustLevel, AnomalyClass[])`. The first matching rule determines the `ResponseType` and associated `ReasonCode` list. A `ResponseRecommendation` (Security_Decision) is constructed with `decision_id`, `correlation_id`, evidence references, and rationale. The decision is stored in the decision store before transmission.

10. **Enforcement.** The Runtime Enforcement Layer (REQ-022) receives the `ResponseRecommendation`. It independently validates applicable policies (it does not blindly trust the recommendation). An `EnforcementRecord` is written to the audit log before any external state change is applied. If dry-run mode is active, no external action is taken and `dry_run=True` is set on the record.

11. **Audit recording.** Throughout the pipeline, each significant event (event acceptance, evidence derivation, trust update, response issued, enforcement applied) produces an `AuditRecord`. Each record is appended to the hash-chain, with `prior_record_hash` chaining to the previous record. Records reference source documents by identifier only; they do not reproduce content.

12. **API response.** The `POST /api/v1/events` response returns HTTP 200 with the event's `event_id` and `correlation_id` in the standard response envelope.

---

## Data Models

*This section introduces the canonical Pydantic v2 data models for Varynx. The primary ingestion schema (AgentActionEvent) is defined immediately below in Section 7. Subsequent sections define the remaining data models: behavioral evidence and trust (Section 8), BCSE (Section 9), predictive trajectory (Section 10), adaptive response (Section 11), enforcement and leases (Section 12), and audit records (Section 13). All models use strict mode (strict=True) to eliminate type coercion. All score and probability fields are constrained to [0.0, 1.0] inclusive. Every record type propagates correlation_id for end-to-end traceability. Simulated events carry is_simulated=True and are never mixed with live event records in evaluation outputs (REQ-027.12).*

---

## 7. Structured Agent-Action Schema

**Satisfies:** REQ-001, REQ-002, REQ-023

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    """
    The primary ingestion boundary for Varynx.
    Represents a single discrete operation attempted by an autonomous AI agent.

    Satisfies: REQ-001.1, REQ-023.3
    """

    model_config = ConfigDict(strict=True)

    event_id: UUID
    """Unique identifier for this event. Submitted by the API_Consumer."""

    agent_id: str
    """Stable identity of the agent. Maps to Agent_Context record."""

    session_id: UUID
    """Session grouping identifier. Created by the API_Consumer."""

    timestamp: datetime
    """UTC timestamp of the action. Must be within ±300/60 seconds of system clock."""

    task_id: Optional[str] = None
    """Optional task context identifier for cross-context correlation analysis."""

    action_type: ActionType
    """The category of operation the agent is performing."""

    capability_requested: str
    """The specific capability the agent claims to be exercising."""

    target_resource: str
    """The resource the action targets. Used for scope evaluation and spread tracking."""

    execution_context: dict[str, Any] = Field(default_factory=dict)
    """Free-form context bag. May include tool arguments, environment metadata, etc."""

    authorization_result: AuthorizationResult
    """The authorization outcome for this action as reported by the agent runtime."""

    behavioral_signals: dict[str, float] = Field(default_factory=dict)
    """Optional numeric signals from the agent runtime (e.g., token counts, latency)."""

    trust_signal: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    """Optional trust hint from the agent framework. Range [0.0, 1.0]."""

    is_simulated: bool
    """
    REQUIRED. True for all events produced by the SimulatedEventAdapter or scenario files.
    Simulated and non-simulated events must never be mixed in the same evaluation
    metric computation (REQ-027.12).
    """
```

---

## 8. Behavioral Evidence and Dynamic Trust Interfaces

**Satisfies:** REQ-003, REQ-004, REQ-005

### 8.1 AnomalyClass Enum

```python
class AnomalyClass(str, Enum):
    CAPABILITY_ESCALATION = "CAPABILITY_ESCALATION"
    """Agent attempted an action outside its declared capability scope (REQ-002.4)."""

    RESOURCE_ANOMALY = "RESOURCE_ANOMALY"
    """Resource access pattern exceeds spread threshold within time window (REQ-004.3)."""

    ACTION_FREQUENCY = "ACTION_FREQUENCY"
    """Action rate exceeds configurable threshold within sliding window."""

    AUTHORIZATION_BYPASS_ATTEMPT = "AUTHORIZATION_BYPASS_ATTEMPT"
    """Three or more authorization denials within configurable window (REQ-004.2)."""

    CONTEXT_DEVIATION = "CONTEXT_DEVIATION"
    """Agent actions correlate to two or more distinct identities or task contexts (REQ-004.4)."""

    TEMPORAL_ANOMALY = "TEMPORAL_ANOMALY"
    """Actions at statistically unusual times relative to agent's historical pattern."""
```

### 8.2 EvidenceRecord and EvidenceBundle

```python
class EvidenceRecord(BaseModel):
    """
    Immutable derived signal from a Behavioral_Event.
    Satisfies: REQ-003.1–REQ-003.6
    """
    evidence_id: UUID
    event_id: UUID                          # Source Behavioral_Event
    session_id: UUID
    agent_id: str
    correlation_id: UUID                    # Shared with source Behavioral_Event
    anomaly_class: AnomalyClass
    score: float = Field(ge=0.0, le=1.0)   # Invariant: always in [0, 1]
    weight: float = Field(ge=0.0, le=1.0)
    detector_id: str                        # Identifies which detector produced this
    contributing_signals: list[str]         # Signal keys from AgentActionEvent
    provenance: dict[str, Any]             # Full derivation record (method, params, inputs)
    timestamp: datetime
    is_simulated: bool
    content_hash: str                       # SHA-256 of this record's content (REQ-003.6)
    derivation_status: str = "COMPLETE"    # "COMPLETE" | "EVIDENCE_DERIVATION_INCOMPLETE"


class EvidenceBundle(BaseModel):
    """
    Correlated collection of EvidenceRecords for a single event processing cycle.
    """
    bundle_id: UUID
    session_id: UUID
    agent_id: str
    correlation_id: UUID
    records: list[EvidenceRecord]
    composite_score: float = Field(ge=0.0, le=1.0)
    correlation_window_seconds: float
    timestamp: datetime
    is_simulated: bool
```

### 8.3 TrustLevel, TrustState, and TrustHistoryEntry

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
    contributing_evidence_ids: list[UUID]
    excluded_incomplete_count: int = 0    # Count of EVIDENCE_DERIVATION_INCOMPLETE exclusions


class TrustState(BaseModel):
    """
    Per-agent dynamic trust state. Satisfies: REQ-005
    """
    session_id: UUID
    agent_id: str
    current_score: float = Field(ge=0.0, le=1.0)
    level: TrustLevel
    history: list[TrustHistoryEntry] = Field(default_factory=list)
    last_updated: datetime
    session_age_seconds: float
```

### 8.4 Trust Score Update Formula

The trust score update is a deterministic, forward-only function (no recovery in Phase 1):

```
new_score = clamp(
    current_score
    - (evidence_weight * anomaly_composite_score * sensitivity)
    - (temporal_decay_rate * session_age_seconds / 3600),
    0.0, 1.0
)
```

**Parameter documentation:**

| Parameter | Source | Default | Note |
|-----------|--------|---------|------|
| `evidence_weight` | EvidenceBundle.composite_score weighted by detector weights | Computed | Sum of (record.score × record.weight) across non-incomplete records |
| `anomaly_composite_score` | EvidenceBundle.composite_score | Computed | Normalized to [0.0, 1.0] |
| `sensitivity` | TrustConfig | 1.0 | Deployment-specific multiplier; requires empirical calibration |
| `temporal_decay_rate` | TrustConfig | 0.01 | Per-hour decay; requires empirical calibration |
| `session_age_seconds` | SessionContext | Computed | Elapsed seconds since session start |
| `clamp(v, 0.0, 1.0)` | Hard bounds | — | Score is always clamped; overflow is logged |

**Invariants enforced by property tests:**
- Output is always in [0.0, 1.0] (REQ-005.2)
- Score never increases in Phase 1 (no recovery factor)
- A zero-evidence bundle (composite_score=0.0) produces only a decay delta
- History length after update = prior history length + 1

### 8.5 AnomalyDetector Protocol

```python
from typing import Protocol, Optional


class AnomalyDetector(Protocol):
    """
    Typed interface for all behavioral anomaly detectors.
    Satisfies: REQ-004
    """
    detector_id: str
    anomaly_class: AnomalyClass
    enabled: bool

    def detect(
        self,
        event: "ValidatedEvent",
        session_context: "SessionContext",
        lease_evaluation: "LeaseEvaluation",
        config: "DetectorConfig",
    ) -> Optional[EvidenceRecord]:
        """
        Returns an EvidenceRecord if the anomaly is triggered, None otherwise.
        Must never raise an unhandled exception; callers catch and log errors.
        """
        ...
```

---

## 9. BCSE Inputs, Outputs, Bounded Analysis, Assumptions, and Limitations

**Satisfies:** REQ-007, REQ-008

### 9.1 Data Models

```python
class PolicyAlternative(BaseModel):
    """A hypothetical policy configuration for BCSE counterfactual analysis."""
    policy_id: str
    label: str
    overrides: dict[str, Any]              # Declarative delta from active policy


class BCSeContext(BaseModel):
    """
    Input to BCSE evaluation. Read-only snapshot; BCSE never modifies any of these.
    Satisfies: REQ-007.3
    """
    context_id: UUID
    proposed_action: AgentActionEvent
    evidence_bundle: EvidenceBundle
    trust_state: TrustState
    active_policy_id: str
    alternative_policies: list[PolicyAlternative] = Field(default_factory=list)


class ConsequenceProjection(BaseModel):
    """
    A single projected consequence for one policy configuration.
    ALL fields describe projections, never observed facts.
    """
    policy_id: str
    projected_response: "ResponseType"
    projected_trust_impact: float          # Estimated delta to trust score
    risk_level: str                        # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN"
    uncertainty_score: float = Field(ge=0.0, le=1.0)  # Invariant: always in [0, 1]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str                         # Natural language; must cite Evidence_Record IDs
    supporting_evidence_ids: list[UUID]    # Only IDs that exist in the evidence store
    is_projected: bool = True              # ALWAYS True; never an observed fact (REQ-007.4)
    projection_basis: str                  # Description of historical window used


class BCSeResult(BaseModel):
    """
    Output of BCSE evaluation.
    Satisfies: REQ-007.2
    """
    bcse_id: UUID
    context_id: UUID
    agent_id: str
    evaluation_timestamp: datetime
    active_consequence: ConsequenceProjection
    counterfactual_consequences: list[ConsequenceProjection]
    divergence_score: float = Field(ge=0.0, le=1.0)
    analysis_timestamp: datetime
    is_stub: bool                          # True in Phase 1
    low_history_warning: bool = False      # True when history < configured minimum (REQ-007.5)
```

### 9.2 BCSeEngine Protocol

```python
class BCSeEngine(Protocol):
    """
    Stable interface for both Phase 1 stub and Phase 2 full implementation.
    Satisfies: REQ-007, REQ-023
    """

    def analyze(self, context: BCSeContext) -> BCSeResult:
        """
        Evaluates a proposed action and returns a projected consequence.
        MUST be non-destructive: must not write to any store (REQ-007.3).
        MUST return HTTP 503 on internal failure, never a partial result (REQ-007.8).
        """
        ...
```

### 9.3 Phase 1 Stub Behavior

The Phase 1 stub satisfies the protocol without counterfactual analysis:
- `is_stub=True`
- `active_consequence` mirrors the current policy recommendation
- `counterfactual_consequences` is an empty list
- `divergence_score` is 0.0
- If `agent_id` has fewer than the configured minimum history events, `uncertainty_score=1.0` and `low_history_warning=True`, `risk_level="UNKNOWN"` (REQ-007.5)

### 9.4 Phase 2 Engine Design

The Phase 2 full implementation (not yet designed in detail) will:
1. **Policy simulation:** Evaluate the active policy and each `PolicyAlternative` against the `BCSeContext`
2. **Consequence projection:** For each policy, derive the projected `ResponseType` and `trust_impact`
3. **Divergence scoring:** Quantify how different alternative projections are from the active consequence
4. **Confidence derivation:** Based on evidence density, history depth, and policy coverage

### 9.5 Explicit Limitations

> **Research Integrity Notice:** BCSE produces probabilistic estimates, not guarantees. The following limitations apply regardless of implementation quality:

- BCSE is **not a proof system.** It does not formally verify that an action is safe or unsafe.
- BCSE is **not a model checker.** It does not explore agent program state space.
- BCSE is **not a statistical potential-outcomes model.** It does not compute causal counterfactual distributions.
- BCSE is **not an exact attacker predictor.** Projected risk levels reflect heuristic estimates derived from behavioral patterns. They do not constitute security verdicts.
- All BCSE outputs carry uncertainty quantification. Any consumer that treats BCSE results as definitive security decisions is misusing the system.

---

## 10. Predictive Security and Security Trajectory Interfaces

**Satisfies:** REQ-021

### 10.1 Data Models

```python
class TrendDirection(str, Enum):
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    RECOVERING = "RECOVERING"
    VOLATILE = "VOLATILE"


class TrajectoryProjection(BaseModel):
    """
    Forward-looking Security_Trajectory for an agent.
    All projected values are labeled PROJECTED and never stored as Evidence_Records.
    Satisfies: REQ-021
    """
    projection_id: UUID
    session_id: UUID
    agent_id: str
    trend: TrendDirection
    projected_trust_at_horizon: float = Field(ge=0.0, le=1.0)
    horizon_seconds: float
    confidence_interval: tuple[float, float]  # (lower, upper) at 95%
    early_warning: bool
    warning_threshold: float
    is_projected: bool = True              # ALWAYS True (REQ-021.6)
    is_stub: bool                          # True in Phase 1
    low_history_stub: bool = False         # True when history < minimum (REQ-021.2)
    computation_timestamp: datetime
```

### 10.2 PredictiveEngine Protocol

```python
class PredictiveEngine(Protocol):
    """
    Stable interface for both Phase 1 stub and Phase 2 full implementation.
    """

    def project(self, trust_state: TrustState) -> TrajectoryProjection:
        """
        Returns a trajectory projection for the agent.
        Must never store results as Evidence_Records (REQ-021.7).
        Must label all outputs with is_projected=True (REQ-021.6).
        """
        ...
```

### 10.3 Phase 1 Stub Behavior

- Returns `TrendDirection.STABLE`, `is_stub=True`, `early_warning=False`
- If history entries < configured minimum (default 5), sets `low_history_stub=True` (REQ-021.2)
- `confidence_interval` is `(0.0, 1.0)` (full uncertainty)

### 10.4 Phase 2 Engine Design

The Phase 2 implementation will:
1. Require a configurable minimum number of `TrustHistoryEntry` records before computing trend (REQ-021.3)
2. Apply a window-based linear regression over trust history within the configured window
3. Extrapolate to the configured horizon (default: 10 score-update intervals) and compute a 95% confidence interval
4. Classify trajectory using configurable thresholds (STABLE/DEGRADING/RECOVERING/VOLATILE)
5. Emit `EARLY_WARNING_TRAJECTORY_BREACH` if projected score at horizon falls below the configured threshold (REQ-021.5)

The linear regression baseline algorithm may be replaced in future phases pending empirical evaluation.

---

## 11. Decision Generation, Reason Codes, and Adaptive Response

**Satisfies:** REQ-009, REQ-011

### 11.1 Response Type and Reason Code Models

```python
class ResponseType(str, Enum):
    PERMIT = "PERMIT"
    WARN = "WARN"
    RESTRICT = "RESTRICT"
    SUSPEND = "SUSPEND"
    TERMINATE = "TERMINATE"
    ESCALATE = "ESCALATE"


class ReasonCode(BaseModel):
    code: str                              # e.g. "TRUST_LEVEL_CRITICAL" (from enumerated set)
    description: str
    contributing_evidence_ids: list[UUID]  # Only IDs resolvable in evidence store (REQ-008.3)
    trust_level_at_recommendation: TrustLevel
    severity: str                          # "INFO" | "WARNING" | "CRITICAL"


class ResponseRecommendation(BaseModel):
    """
    A Security_Decision: a recommendation to the Enforcement_Boundary.
    NEVER labeled as an enforcement outcome. Satisfies: REQ-009
    """
    recommendation_id: UUID
    agent_id: str
    correlation_id: UUID                   # Propagated from originating Behavioral_Event
    response_type: ResponseType
    reason_codes: list[ReasonCode]
    evidence_bundle_id: UUID
    trust_state_snapshot: TrustState
    bcse_result_id: Optional[UUID] = None
    trajectory_projection_id: Optional[UUID] = None
    rationale: str                         # Natural language; must cite Evidence_Record IDs (REQ-008.2)
    timestamp: datetime
    policy_id: str
    policy_version: str                    # Policy table version at decision time (REQ-011.6)
```

### 11.2 Policy YAML Format

The adaptive response engine evaluates a priority-ordered YAML rule list. The first matching rule wins. Rules are evaluated in declaration order.

```yaml
# config/default_policy.yaml
version: "1.0.0"
rules:
  - if:
      trust_level: CRITICAL
    then:
      response: TERMINATE
      reason_codes: [TRUST_LEVEL_CRITICAL]

  - if:
      trust_level: LOW
      trajectory: degrading
    then:
      response: SUSPEND
      reason_codes: [TRUST_DEGRADED, TRAJECTORY_DEGRADING]

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

  - if:
      anomaly_class: RESOURCE_ANOMALY
    then:
      response: RESTRICT
      reason_codes: [RESOURCE_SPREAD_DETECTED]

  - if:
      trust_level: [LOW, GUARDED]
    then:
      response: WARN
      reason_codes: [TRUST_DEGRADED]

  - default:
      response: PERMIT
      reason_codes: []
```

### 11.3 Escalation Rules (REQ-011)

The Adaptive_Response_Engine enforces the following escalation semantics:

| Condition | Minimum Response |
|-----------|-----------------|
| `Security_Trajectory = degrading` AND `trust_score < 0.4` (configurable) | `RESTRICT` |
| `Security_Trajectory = degrading` AND `trust_score < 0.2` (configurable) | `SUSPEND` |
| `Security_Trajectory = improving` AND `trust_score > 0.7` (configurable) | No escalation without corroborating anomaly signals |

**Escalation monotonicity:** The engine never recommends a lower severity response than the current active recommendation without an explicit de-escalation event. Passage of time alone does not trigger de-escalation (REQ-011.5).

**Policy table fallback (REQ-011.7):** If the policy table is invalid or missing at runtime, all agents receive `MONITOR` and `POLICY_TABLE_INVALID` is logged.

---

## 12. Authorization and Runtime Enforcement Boundaries

**Satisfies:** REQ-010, REQ-022

### 12.1 Lease and Enforcement Models

```python
class LeaseState(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class CapabilityLease(BaseModel):
    """Satisfies: REQ-010"""
    lease_id: UUID
    agent_id: str
    session_id: UUID
    capability: str
    resource_scope: dict[str, Any]         # Resource patterns, action types, etc.
    activation_timestamp: datetime
    expiry_timestamp: Optional[datetime] = None
    issuing_principal: str
    issuing_policy_id: str
    state: LeaseState
    state_history: list[dict[str, Any]] = Field(default_factory=list)


class EnforcementRecord(BaseModel):
    """Satisfies: REQ-022.3"""
    enforcement_id: UUID
    source_recommendation_id: UUID         # Links back to ResponseRecommendation
    action_taken: str
    target_agent_id: str
    target_resource_scope: Optional[str] = None
    action_timestamp: datetime
    outcome: str                           # "SUCCESS" | "FAILED" | "SKIPPED"
    outcome_reason: Optional[str] = None   # e.g. "POLICY_VALIDATION_REJECTED", "DUPLICATE_ENFORCEMENT"
    dry_run: bool                          # True in dry-run mode (REQ-022.4)
```

### 12.2 Enforcement Pipeline

```
ResponseRecommendation received
        │
        ▼
Independent policy validation (Enforcement_Layer validates; does not blindly trust recommendation)
        │
   ┌────┴────┐
   │ PASS    │ REJECT → EnforcementRecord(outcome=SKIPPED, reason=POLICY_VALIDATION_REJECTED)
   │         │          → Audit log entry → STOP
   ▼
Write EnforcementRecord to audit log (BEFORE applying action)
        │
   ┌────┴────┐
   │ SUCCESS │ FAIL → Action blocked; HTTP 503 returned
   │
   ▼
Apply enforcement action (lease state change, session termination, etc.)
        │
        ▼
Update EnforcementRecord with outcome (SUCCESS | FAILED)
```

### 12.3 Dry-Run Mode Semantics

When `dry_run_mode=True` in `VarynxConfig`:
- The enforcement layer evaluates what action would be taken and logs it
- No external state change is applied (no lease transitions, no session terminations)
- Every `EnforcementRecord` has `dry_run=True`
- Dry-run records are stored in the audit log (for analysis) but never used as inputs to trust computation or decision generation (REQ-022.4)

### 12.4 Idempotency Guarantee

Applying the same `ResponseRecommendation` for the same `agent_id` with the same `source_recommendation_id` more than once produces no additional enforcement effects. Subsequent applications produce an `EnforcementRecord` with `outcome=SKIPPED` and `outcome_reason=DUPLICATE_ENFORCEMENT` (REQ-022.8).

### 12.5 Architectural Boundary

> **Mandatory constraint:** The behavioral intelligence components (evidence engine, trust module, BCSE, adaptive response engine) have no path to apply enforcement actions directly. Enforcement is exclusively the responsibility of the Runtime Enforcement Layer. No component within Varynx records a Security_Decision as an enforcement outcome (REQ-009.4, architectural constraint 2).

---

## 13. Correlation Identifiers, Provenance, and Audit Integration

**Satisfies:** REQ-012, REQ-013, REQ-014

### 13.1 AuditRecord Model

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
    """
    Tamper-evident, append-only record.
    References source records by ID only; never reproduces content (REQ-013.6).
    Satisfies: REQ-013
    """
    record_id: UUID
    timestamp: datetime
    record_type: AuditRecordType
    source_entity_id: str                  # ID of the primary entity this record concerns
    correlation_id: Optional[UUID] = None  # Propagated from originating Behavioral_Event
    session_id: Optional[UUID] = None
    agent_id: Optional[str] = None
    payload: dict[str, Any]               # References only (IDs, status codes, reason strings)
    prior_record_hash: Optional[str] = None  # SHA-256 of the previous record in the chain
    record_hash: str                        # SHA-256(prior_record_hash + content_hash)
```

### 13.2 Hash-Chain Algorithm

On each `append(audit_record)`:

1. Serialize the record content (all fields except `record_hash` and `prior_record_hash`) to canonical JSON (sorted keys, no whitespace)
2. Compute `content_hash = SHA-256(canonical_json)`
3. Set `prior_record_hash` to the `record_hash` of the last record in the chain (`None` for the first record)
4. Set `record_hash = SHA-256(prior_record_hash || content_hash)` where `||` is string concatenation (empty string for `None`)
5. Persist the complete record

**Hash-chain integrity verification** scans all records in insertion order, recomputes each `record_hash`, and returns `TAMPER_DETECTED` for any record where the computed hash differs from the stored hash (REQ-013.4).

### 13.3 Append-Only Enforcement

The PostgreSQL application role MUST NOT be granted `UPDATE` or `DELETE` privileges on the `audit_log` table. The append-only constraint is enforced at the database privilege level, not solely in application logic (REQ-013.3).

### 13.4 Traceability Query

`GET /api/v1/audit/provenance/{correlation_id}` returns:
- The originating `Behavioral_Event`
- All associated `Evidence_Records`
- All `Security_Decisions` referencing those records
- All `Audit_Records` linked to the `correlation_id`

If `correlation_id` does not exist, HTTP 404 is returned. The system never fabricates or infers records for an absent ID (REQ-012.3).

If any referenced record in the chain is missing, the response includes a `CHAIN_INTEGRITY_VIOLATION` flag identifying the gap rather than silently returning an incomplete chain (REQ-012.5).

### 13.5 Evidence Integrity Verification (REQ-014)

Before any `Evidence_Record` is used in trust score computation or Security_Decision generation:
1. Recompute `content_hash` from the stored record
2. Compare against `content_hash` in `EvidenceRecord.content_hash`
3. On mismatch: mark the record `INTEGRITY_VIOLATION`, exclude from all computation, create an `AuditRecord` documenting the violation
4. If all required evidence records are `INTEGRITY_VIOLATION` or `EVIDENCE_DERIVATION_INCOMPLETE`, withhold the Security_Decision and emit `DECISION_BLOCKED_EVIDENCE_INTEGRITY` alert

---

## 14. Persistence and Database Design

**Satisfies:** REQ-017

All persistence uses PostgreSQL 15 with TimescaleDB. Four logically separate storage subsystems are maintained (REQ-017.1). No data type crosses subsystem boundaries via content copy; cross-references use identifiers only (REQ-017.3).

```sql
-- ==========================================================================
-- Subsystem: Identity
-- ==========================================================================

CREATE TABLE agents (
    agent_id            TEXT PRIMARY KEY,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    declared_capability_scope  JSONB NOT NULL DEFAULT '[]',
    authorized_resource_scope  JSONB NOT NULL DEFAULT '[]',
    owning_principal    TEXT NOT NULL,
    scope_escalation_count  INTEGER NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'
);
-- CONSTRAINT: agent_id and owning_principal must not be updated after insert (REQ-002.5)
-- Enforced via application logic; trigger may be added for defense-in-depth.

CREATE TABLE sessions (
    session_id          UUID PRIMARY KEY,
    agent_id            TEXT NOT NULL REFERENCES agents(agent_id),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at       TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    current_trust       FLOAT NOT NULL DEFAULT 0.7 CHECK (current_trust >= 0.0 AND current_trust <= 1.0),
    trust_level         TEXT NOT NULL DEFAULT 'ELEVATED',
    state               TEXT NOT NULL DEFAULT 'ACTIVE',
    resource_spread     JSONB NOT NULL DEFAULT '{}',
    capability_spread   JSONB NOT NULL DEFAULT '{}'
);

-- ==========================================================================
-- Subsystem: Behavioral Event Log (TimescaleDB hypertable)
-- ==========================================================================

CREATE TABLE events (
    event_id                UUID NOT NULL,
    agent_id                TEXT NOT NULL,
    session_id              UUID NOT NULL,
    correlation_id          UUID NOT NULL,
    timestamp               TIMESTAMPTZ NOT NULL,
    task_id                 TEXT,
    action_type             TEXT NOT NULL,
    capability_requested    TEXT NOT NULL,
    target_resource         TEXT NOT NULL,
    execution_context       JSONB NOT NULL DEFAULT '{}',
    authorization_result    TEXT NOT NULL,
    behavioral_signals      JSONB NOT NULL DEFAULT '{}',
    trust_signal            FLOAT CHECK (trust_signal IS NULL OR (trust_signal >= 0.0 AND trust_signal <= 1.0)),
    is_simulated            BOOLEAN NOT NULL,
    raw_payload             JSONB NOT NULL,
    PRIMARY KEY (event_id, timestamp)
);
SELECT create_hypertable('events', 'timestamp');
CREATE UNIQUE INDEX events_agent_action_uniq ON events (agent_id, event_id);

-- ==========================================================================
-- Subsystem: Evidence Store
-- ==========================================================================

CREATE TABLE evidence_records (
    evidence_id             UUID PRIMARY KEY,
    event_id                UUID NOT NULL,
    session_id              UUID NOT NULL,
    agent_id                TEXT NOT NULL,
    correlation_id          UUID NOT NULL,
    anomaly_class           TEXT NOT NULL,
    score                   FLOAT NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    weight                  FLOAT NOT NULL CHECK (weight >= 0.0 AND weight <= 1.0),
    detector_id             TEXT NOT NULL,
    contributing_signals    JSONB NOT NULL DEFAULT '[]',
    provenance              JSONB NOT NULL,
    timestamp               TIMESTAMPTZ NOT NULL,
    is_simulated            BOOLEAN NOT NULL,
    content_hash            TEXT NOT NULL,
    derivation_status       TEXT NOT NULL DEFAULT 'COMPLETE'
);
-- No UPDATE or DELETE should be permitted on this table after initial insert.

CREATE TABLE trust_history (
    entry_id                UUID PRIMARY KEY,
    session_id              UUID NOT NULL,
    agent_id                TEXT NOT NULL,
    timestamp               TIMESTAMPTZ NOT NULL,
    prior_score             FLOAT NOT NULL,
    delta                   FLOAT NOT NULL,
    new_score               FLOAT NOT NULL CHECK (new_score >= 0.0 AND new_score <= 1.0),
    contributing_evidence_ids  JSONB NOT NULL DEFAULT '[]',
    excluded_incomplete_count  INTEGER NOT NULL DEFAULT 0
);

-- ==========================================================================
-- Subsystem: Decision Store
-- ==========================================================================

CREATE TABLE capability_leases (
    lease_id                UUID PRIMARY KEY,
    agent_id                TEXT NOT NULL REFERENCES agents(agent_id),
    session_id              UUID NOT NULL,
    capability              TEXT NOT NULL,
    resource_scope          JSONB NOT NULL DEFAULT '{}',
    activation_timestamp    TIMESTAMPTZ NOT NULL,
    expiry_timestamp        TIMESTAMPTZ,
    issuing_principal       TEXT NOT NULL,
    issuing_policy_id       TEXT NOT NULL,
    state                   TEXT NOT NULL DEFAULT 'ACTIVE',
    state_history           JSONB NOT NULL DEFAULT '[]'
);
-- expiry_timestamp must not be modified after activation (REQ-010.9)

CREATE TABLE response_recommendations (
    recommendation_id       UUID PRIMARY KEY,
    agent_id                TEXT NOT NULL,
    correlation_id          UUID NOT NULL,
    response_type           TEXT NOT NULL,
    reason_codes            JSONB NOT NULL,
    evidence_bundle_id      UUID NOT NULL,
    trust_snapshot          JSONB NOT NULL,
    bcse_result_id          UUID,
    trajectory_projection_id UUID,
    rationale               TEXT NOT NULL,
    policy_id               TEXT NOT NULL,
    policy_version          TEXT NOT NULL,
    timestamp               TIMESTAMPTZ NOT NULL
);

CREATE TABLE enforcement_records (
    enforcement_id          UUID PRIMARY KEY,
    source_recommendation_id UUID NOT NULL,
    action_taken            TEXT NOT NULL,
    target_agent_id         TEXT NOT NULL,
    target_resource_scope   TEXT,
    action_timestamp        TIMESTAMPTZ NOT NULL,
    outcome                 TEXT NOT NULL,
    outcome_reason          TEXT,
    dry_run                 BOOLEAN NOT NULL DEFAULT FALSE
);

-- ==========================================================================
-- Subsystem: Audit Log (append-only)
-- ==========================================================================

CREATE TABLE audit_log (
    record_id               UUID PRIMARY KEY,
    timestamp               TIMESTAMPTZ NOT NULL,
    record_type             TEXT NOT NULL,
    source_entity_id        TEXT NOT NULL,
    correlation_id          UUID,
    session_id              UUID,
    agent_id                TEXT,
    payload                 JSONB NOT NULL,
    prior_record_hash       TEXT,
    record_hash             TEXT NOT NULL
);
-- CRITICAL: The application database role MUST NOT have UPDATE or DELETE
-- privileges on audit_log. This is enforced at the PostgreSQL GRANT level,
-- not only in application logic. (REQ-013.3)
```

---

## 15. API Contracts and Error Semantics

**Satisfies:** REQ-016

### 15.1 Base Path and Versioning

All endpoints are prefixed with `/api/v1`. The OpenAPI specification version is included in all responses as the HTTP header `X-API-Version`.

### 15.2 Route Table

**Event Ingestion (REQ-001)**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/events` | Submit a single `AgentActionEvent` |
| `POST` | `/events/batch` | Submit up to 100 events atomically |
| `GET` | `/events/{event_id}` | Retrieve a stored event record |

**Agent & Session Management (REQ-002)**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agents` | Register an agent |
| `GET` | `/agents/{agent_id}` | Get agent context record |
| `GET` | `/agents/{agent_id}/profile` | Get full agent security profile (trust, trajectory, leases, decisions) |
| `POST` | `/sessions` | Create a session |
| `GET` | `/sessions/{session_id}` | Get session state including current trust |
| `DELETE` | `/sessions/{session_id}` | Terminate a session |

**Capability Leases (REQ-010)**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/leases` | Grant a capability lease |
| `GET` | `/leases/{lease_id}` | Get lease record and state history |
| `PATCH` | `/leases/{lease_id}/suspend` | Suspend an ACTIVE lease |
| `PATCH` | `/leases/{lease_id}/reinstate` | Reinstate a SUSPENDED lease |
| `DELETE` | `/leases/{lease_id}` | Revoke a lease |
| `GET` | `/sessions/{session_id}/leases` | List all leases for a session |

**BCSE (REQ-007)**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/bcse/evaluate` | Submit a proposed action for BCSE evaluation (non-destructive) |

**Audit & Evidence (REQ-012, REQ-013)**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/audit` | Query audit records (filter: agent_id, correlation_id, record_type, time range) |
| `GET` | `/audit/{record_id}` | Get a single audit record |
| `GET` | `/audit/provenance/{correlation_id}` | Full traceability chain for a correlation_id |
| `GET` | `/audit/export` | Export audit records as JSON-L |
| `GET` | `/audit/verify` | Verify hash-chain integrity for a record range |

**Evaluation (REQ-015, REQ-025)**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate/run` | Execute a named scenario |
| `GET` | `/evaluate/scenarios` | List available scenarios with validation status |
| `GET` | `/evaluate/results/{run_id}` | Get evaluation run results |

**System Health (REQ-017, REQ-019)**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Storage subsystem availability and record counts |
| `GET` | `/metrics` | Operational metrics (ingestion rate, latencies, etc.) |
| `GET` | `/config` | Read-only active configuration snapshot (secrets excluded) |

### 15.3 Common Response Envelope

Success:
```json
{
  "status": "success",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "api_version": "v1",
  "data": { "...": "..." }
}
```

Error:
```json
{
  "status": "error",
  "request_id": "uuid",
  "timestamp": "2026-10-20T11:00:00Z",
  "api_version": "v1",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "correlation_id": "uuid-or-null",
    "details": [
      { "field": "agent_id", "message": "field required" }
    ]
  }
}
```

### 15.4 HTTP Status Code Semantics

| Code | Condition |
|------|-----------|
| 200 | Success |
| 201 | Resource created |
| 400 | Malformed request (syntax error) |
| 401 | Unauthenticated (REQ-016.3) |
| 403 | Insufficient permissions (REQ-016.4) |
| 404 | Resource not found |
| 409 | Duplicate action_id for agent (REQ-001.4) |
| 413 | Request body exceeds configured maximum (REQ-016.8) |
| 422 | Semantic validation failure (missing fields, out-of-range values) (REQ-001.2) |
| 429 | Rate limit exceeded (REQ-016.6) |
| 503 | Storage subsystem or BCSE unavailable |

---

## 16. Research Dataset and Experiment Architecture

**Satisfies:** REQ-015, REQ-025

### 16.1 Scenario YAML Format

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
    declared_capability_scope: ["file:read"]
    authorized_resource_scope: ["/data/reports/*"]
    leases:
      - capability: file:read
        resource_scope: {resource_pattern: "/data/reports/*"}
        issuing_policy_id: policy-default

events:
  - event_id: "00000000-0000-0000-0000-000000000001"
    agent_id: agent-alpha
    session_id: "00000000-0000-0000-0001-000000000000"
    timestamp: "2026-01-01T00:00:00Z"
    action_type: READ
    capability_requested: "file:read"
    target_resource: "/data/reports/q3.csv"
    authorization_result: allowed
    is_simulated: true

  - event_id: "00000000-0000-0000-0000-000000000002"
    agent_id: agent-alpha
    session_id: "00000000-0000-0000-0001-000000000000"
    timestamp: "2026-01-01T00:00:05Z"
    action_type: WRITE
    capability_requested: "file:write"
    target_resource: "/data/reports/q3.csv"
    authorization_result: denied
    is_simulated: true

  - event_id: "00000000-0000-0000-0000-000000000003"
    agent_id: agent-alpha
    session_id: "00000000-0000-0000-0001-000000000000"
    timestamp: "2026-01-01T00:00:10Z"
    action_type: CREDENTIAL_ACCESS
    capability_requested: "credential:read"
    target_resource: "/secrets/api_keys"
    authorization_result: denied
    is_simulated: true

expected_outcomes:
  - event_id: "00000000-0000-0000-0000-000000000002"
    anomaly_classes: [CAPABILITY_ESCALATION]
    min_response: RESTRICT
    trust_trajectory_direction: degrading

  - event_id: "00000000-0000-0000-0000-000000000003"
    anomaly_classes: [AUTHORIZATION_BYPASS_ATTEMPT, CAPABILITY_ESCALATION]
    min_response: SUSPEND
    trust_trajectory_direction: degrading
```

### 16.2 Five Required Scenario Types (REQ-025.1)

| Scenario ID | Behavioral Pattern | Primary Detectors |
|-------------|-------------------|-------------------|
| `baseline_nominal_01` | Nominal agent behavior — all actions within scope, no denials | None triggered |
| `capability_escalation_01` | Agent attempts actions outside declared capability scope | `capability_escalation` |
| `repeated_denial_01` | Three or more authorization denials within 300-second window | `authorization_bypass` |
| `resource_spread_01` | Agent accesses increasing number of distinct resource domains | `resource_anomaly` |
| `cross_context_correlation_01` | Agent actions correlate to two or more distinct task contexts in one session | `context_deviation` |

### 16.3 Baseline Configurations B1–B4

| Baseline | ID | Evidence Engine | Trust Module | BCSE | Predictive | Phase |
|----------|----|-----------------|--------------|------|------------|-------|
| Policy-only | B1 | Disabled | Disabled | Disabled | Disabled | 1 |
| Risk threshold | B2 | Enabled | Disabled (static threshold) | Disabled | Disabled | 1 |
| Behavioral + Trust | B3 | Enabled | Enabled | Disabled | Disabled | 1 |
| Full system | B4 | Enabled | Enabled | Enabled (Phase 2) | Enabled (Phase 2) | 2 |

---

## 17. Baseline, Ablation, Sensitivity, Robustness, and Statistical Analysis Interfaces

**Satisfies:** REQ-015, REQ-026

### 17.1 Metric Definitions

| Metric | Symbol | Definition |
|--------|--------|------------|
| Detection Rate | DR | TP / (TP + FN) |
| False Positive Rate | FPR | FP / (FP + TN) |
| False Negative Rate | FNR | FN / (FN + TP) |
| Precision | P | TP / (TP + FP) |
| Recall | R | TP / (TP + FN) |
| F1 Score | F1 | 2 × P × R / (P + R) |
| Mean Time to Detection | MTTD | Mean events between anomaly injection and first anomaly evidence record |
| Mean Time to Response | MTTR | Mean events between anomaly injection and enforcement action |
| P99 Latency | L99 | 99th percentile per-event pipeline duration (ms) |
| Computational Overhead | CO | Additional CPU time per event vs. B1 baseline |

All metrics in [0.0, 1.0] (except latency/overhead) are subject to the range invariant verified by property tests (REQ-026).

### 17.2 Ablation Configuration

Individual detectors can be disabled via `EvidenceConfig.enabled_detectors`. The full system can be ablated to any of the B1–B4 baselines via configuration — no code change required (REQ-015.5, REQ-020.1). Each ablation configuration produces a distinct evaluation report with its own configuration snapshot identifier.

### 17.3 Statistical Reporting Requirements (REQ-026)

- Minimum 5 repeated runs per experiment with identical seed, dataset, configuration, and software version (REQ-024.4)
- Report: arithmetic mean, standard deviation, 95% confidence interval per metric
- Effect size: Cohen's d (or equivalent) when comparing two configurations
- Reports marked `INCOMPLETE` if run count is below minimum (REQ-026.6)
- Per-run values stored alongside aggregate summaries (REQ-026.7)
- In-distribution and out-of-distribution results reported separately (REQ-026.4)

### 17.4 Adversarial Evaluation (REQ-015.7)

The scenario runner accepts manually crafted event sequences designed to evade detection. These are loaded as standard YAML scenario files with `adversarial: true` metadata. The evaluation pipeline is not modified for adversarial inputs; the system's response is recorded and reported.

### 17.5 Threshold Sensitivity Analysis (REQ-015.6)

The evaluation framework supports executing a scenario across a configurable range of threshold values. Results at each threshold level are recorded in a separate report. This enables threshold calibration studies before deployment.

---

## 18. Configuration and Reproducibility

**Satisfies:** REQ-020, REQ-027

### 18.1 Configuration Models

```python
class TrustConfig(BaseModel):
    initial_score: float = Field(default=0.7, ge=0.0, le=1.0)
    sensitivity: float = Field(default=1.0, gt=0.0)
    temporal_decay_rate: float = Field(default=0.01, ge=0.0)
    thresholds: dict[str, float] = {
        "HIGH": 0.85,
        "ELEVATED": 0.65,
        "GUARDED": 0.40,
        "LOW": 0.20,
    }
    # Note: all defaults require empirical calibration (REQ-005.3)


class EvidenceConfig(BaseModel):
    correlation_window_seconds: float = 60.0
    enabled_detectors: list[str] = ["all"]   # ["all"] enables all detectors
    detector_weights: dict[str, float] = {}  # Per-detector weight overrides
    authz_denial_window_seconds: float = 300.0
    authz_denial_threshold: int = 3          # REQ-004.2; requires evaluation
    resource_spread_domains: int = 10        # REQ-004.3; requires evaluation
    resource_spread_window_seconds: float = 600.0
    capability_spread_threshold: int = 5     # REQ-006.4; requires evaluation


class PolicyConfig(BaseModel):
    path: str = "config/default_policy.yaml"
    escalation_threshold: float = 0.4       # REQ-011.2; requires evaluation
    critical_threshold: float = 0.2         # REQ-011.3; requires evaluation
    de_escalation_threshold: float = 0.7    # REQ-011.4; requires evaluation


class BCSeConfig(BaseModel):
    min_history_events: int = 10            # REQ-007.5; requires evaluation
    evaluation_timeout_seconds: float = 2.0 # REQ-007.7; requires evaluation


class VarynxConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VARYNX_")

    database_url: str
    trust: TrustConfig = TrustConfig()
    evidence: EvidenceConfig = EvidenceConfig()
    policy: PolicyConfig = PolicyConfig()
    bcse: BCSeConfig = BCSeConfig()
    dry_run_mode: bool = False
    log_level: str = "INFO"
    session_max_duration_seconds: float = 3600.0
    config_version: str = "1.0.0"
    evaluation_min_runs: int = 5            # REQ-026.1
```

### 18.2 Startup Validation

- If the external configuration source is unavailable at startup, the system fails to start with `CONFIGURATION_UNAVAILABLE` error (REQ-020.2)
- If any parameter fails schema validation, startup fails with `CONFIGURATION_INVALID` naming each failing parameter (REQ-020.3)
- No threshold values are hard-coded in application logic (REQ-020.1)
- Configuration changes at runtime are logged as `AuditRecord` entries with previous snapshot, new snapshot, timestamp, and requesting principal (REQ-020.4)

### 18.3 Configuration Versioning

Each evaluation experiment references a `config_version` identifier. The configuration snapshot for a given version is stored and retrievable, enabling independent reproducibility (REQ-020.6, REQ-027.5).

### 18.4 reproduce.sh Requirements (REQ-027.6)

The `reproduce.sh` script at the repository root must:
1. Install all required dependencies (Python, PostgreSQL, Redis if applicable)
2. Apply database migrations
3. Load all scenario files
4. Execute the full evaluation harness against all scenario files for all baselines
5. Write evaluation reports to `./output/evaluation/`
6. Exit with non-zero status if any evaluation step fails

---

## 19. Logging, Observability, and System Health

**Satisfies:** REQ-019

### 19.1 Structured Log Format

Every log entry is emitted as JSON with at minimum the following fields:

```json
{
  "timestamp": "2026-10-20T11:00:00.000Z",
  "severity": "INFO",
  "component": "evidence_engine.capability_escalation",
  "correlation_id": "uuid-or-null",
  "agent_id": "agent-alpha-or-null",
  "event": "EVIDENCE_PRODUCED",
  "message": "Capability escalation detected",
  "details": {}
}
```

**Sensitive field redaction (REQ-019.5):** Raw `Behavioral_Event` payload fields that may contain sensitive agent input data are redacted before logging. The redaction list is configurable. Log entries reference events by `event_id` and `correlation_id`, not by payload content.

### 19.2 Metrics Endpoint

`GET /api/v1/metrics` returns current operational metrics including:

| Metric | Description |
|--------|-------------|
| `events_ingested_per_second` | Rolling ingestion rate |
| `evidence_derivation_latency_p99_ms` | P99 latency from event receipt to evidence bundle |
| `bcse_evaluation_latency_p99_ms` | P99 BCSE evaluation latency |
| `security_decision_rate_per_second` | Decision generation rate |
| `storage_availability` | Per-subsystem availability flags |
| `audit_record_count` | Total records in audit log |
| `active_session_count` | Currently active sessions |

### 19.3 W3C Trace Context Propagation (REQ-019.4)

All internal service boundaries propagate trace context headers in accordance with the W3C Trace Context specification (`traceparent`, `tracestate`). Distributed tracing is supported for integration with external observability platforms.

### 19.4 System Health Degraded Alert (REQ-019.6)

When the configurable error rate threshold is exceeded within a configurable time window, the system emits a `SYSTEM_HEALTH_DEGRADED` alert via the configurable alerting channel. The alert includes the affected component, error rate, threshold, and window.

---

## 20. Repository Layout

**Satisfies:** REQ-027 (testability, reproducibility)

```
varynx/
├── varynx/                                  # Core Python package
│   ├── __init__.py
│   ├── config.py                            # Pydantic Settings configuration (REQ-020)
│   ├── models/                              # Shared Pydantic v2 data models
│   │   ├── __init__.py
│   │   ├── agent.py                         # AgentRecord, SessionRecord
│   │   ├── event.py                         # AgentActionEvent, ValidatedEvent
│   │   ├── evidence.py                      # EvidenceRecord, EvidenceBundle, AnomalyClass
│   │   ├── trust.py                         # TrustState, TrustHistoryEntry, TrustLevel
│   │   ├── lease.py                         # CapabilityLease, LeaseState, LeaseEvaluation
│   │   ├── bcse.py                          # BCSeContext, BCSeResult, ConsequenceProjection
│   │   ├── prediction.py                    # TrajectoryProjection, TrendDirection
│   │   ├── response.py                      # ResponseRecommendation, ResponseType, ReasonCode
│   │   ├── enforcement.py                   # EnforcementRecord
│   │   └── audit.py                         # AuditRecord, AuditRecordType
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── validator.py                     # Schema validation, idempotency, timestamp check
│   │   └── normalizer.py                    # Action type normalization, is_simulated labeling
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── registry.py                      # Agent + session registry (REQ-002)
│   │   └── spread_tracker.py               # Resource and capability spread tracking (REQ-006)
│   ├── evidence/
│   │   ├── __init__.py
│   │   ├── engine.py                        # Detector pipeline orchestration (REQ-003, REQ-004)
│   │   ├── detectors/
│   │   │   ├── __init__.py
│   │   │   ├── capability_escalation.py
│   │   │   ├── resource_anomaly.py
│   │   │   ├── action_frequency.py
│   │   │   ├── authorization_bypass.py
│   │   │   ├── context_deviation.py
│   │   │   └── temporal_anomaly.py
│   │   ├── correlator.py                    # Evidence correlation and composite score
│   │   └── hasher.py                        # Per-record cryptographic hash (REQ-003.6)
│   ├── trust/
│   │   ├── __init__.py
│   │   ├── scorer.py                        # Trust score update formula (REQ-005)
│   │   ├── decay.py                         # Temporal decay functions
│   │   └── classifier.py                   # Score → TrustLevel mapping
│   ├── bcse/
│   │   ├── __init__.py
│   │   ├── interface.py                     # BCSeEngine Protocol definition
│   │   ├── stub.py                          # Phase 1 stub (REQ-007)
│   │   └── engine.py                        # Phase 2 full implementation (placeholder)
│   ├── prediction/
│   │   ├── __init__.py
│   │   ├── interface.py                     # PredictiveEngine Protocol definition
│   │   ├── stub.py                          # Phase 1 stub — always STABLE (REQ-021)
│   │   └── engine.py                        # Phase 2 full implementation (placeholder)
│   ├── response/
│   │   ├── __init__.py
│   │   ├── engine.py                        # Response recommendation logic (REQ-009, REQ-011)
│   │   ├── policy.py                        # Policy YAML loading and evaluation
│   │   ├── reason_codes.py                  # Enumerated reason code catalog
│   │   └── rationale.py                     # Rationale text generation (REQ-008)
│   ├── lease/
│   │   ├── __init__.py
│   │   ├── manager.py                       # Lease CRUD and lifecycle (REQ-010)
│   │   └── evaluator.py                     # Lease scope checking per event
│   ├── enforcement/
│   │   ├── __init__.py
│   │   └── enforcer.py                      # Recommendation → state change, dry-run (REQ-022)
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── store.py                         # Append-only audit log (REQ-013)
│   │   ├── hasher.py                        # SHA-256 hash-chain computation
│   │   ├── integrity.py                     # Hash verification and TAMPER_DETECTED (REQ-014)
│   │   └── provenance_query.py             # Traceability query by correlation_id (REQ-012)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI app factory
│   │   ├── auth.py                          # Authentication and authorization middleware
│   │   ├── routers/
│   │   │   ├── events.py
│   │   │   ├── agents.py
│   │   │   ├── sessions.py
│   │   │   ├── leases.py
│   │   │   ├── bcse.py
│   │   │   ├── audit.py
│   │   │   ├── evaluate.py
│   │   │   └── health.py
│   │   └── middleware.py                    # Request ID, timing, structured logging
│   └── pipeline/
│       ├── __init__.py
│       └── processor.py                     # Top-level pipeline orchestration (REQ-027.9)
├── evaluation/
│   ├── __init__.py
│   ├── runner.py                            # Scenario execution engine (REQ-015, REQ-025)
│   ├── schema.py                            # Scenario YAML schema validation
│   ├── scenarios/                           # YAML scenario definitions
│   │   ├── baseline_nominal_01.yaml
│   │   ├── capability_escalation_01.yaml
│   │   ├── repeated_denial_01.yaml
│   │   ├── resource_spread_01.yaml
│   │   └── cross_context_correlation_01.yaml
│   ├── baselines/
│   │   ├── b1_policy_only.py
│   │   ├── b2_risk_threshold.py
│   │   ├── b3_behavioral_trust.py
│   │   └── b4_full_system.py               # Phase 2
│   ├── metrics.py                           # Detection rate, F1, latency, etc.
│   ├── statistics.py                        # Mean, std, 95% CI, Cohen's d (REQ-026)
│   └── report.py                            # Structured report generation
├── tests/
│   ├── unit/
│   │   ├── test_ingestion.py
│   │   ├── test_evidence_engine.py
│   │   ├── test_trust_scorer.py
│   │   ├── test_bcse_stub.py
│   │   ├── test_response_engine.py
│   │   ├── test_lease_manager.py
│   │   ├── test_enforcement.py
│   │   ├── test_audit_store.py
│   │   └── test_config.py
│   ├── property/
│   │   ├── test_event_schema_properties.py  # REQ-016 serialization round-trip
│   │   ├── test_evidence_properties.py      # REQ-003, REQ-004
│   │   ├── test_trust_properties.py         # REQ-005 [0,1] invariant
│   │   ├── test_response_properties.py      # REQ-009, REQ-011 determinism
│   │   ├── test_lease_properties.py         # REQ-010 REVOKED terminal
│   │   ├── test_enforcement_properties.py   # REQ-022 idempotence
│   │   ├── test_correlation_properties.py   # REQ-012 uniqueness
│   │   ├── test_bcse_properties.py          # REQ-007 uncertainty in [0,1]
│   │   ├── test_config_properties.py        # REQ-020
│   │   └── test_evaluation_properties.py    # REQ-025 determinism, REQ-026 metrics
│   ├── integration/
│   │   ├── test_pipeline.py                 # Full event-to-enforcement
│   │   ├── test_api_events.py
│   │   ├── test_bcse_non_interference.py    # REQ-007.3
│   │   └── test_audit_provenance.py
│   └── fixtures/
│       ├── events.py
│       ├── agents.py
│       ├── sessions.py
│       ├── policies.py
│       └── scenarios.py
├── ui/                                      # Phase 3 — Next.js dashboard
│   └── (scaffolded in Phase 3)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── alembic/                                 # PostgreSQL schema migrations
│   ├── env.py
│   └── versions/
├── config/
│   ├── default_policy.yaml
│   ├── trust_thresholds.yaml
│   └── evaluation_config.yaml
├── docs/
│   ├── research_methodology.md             # REQ-024 — versioned, pre-results
│   ├── evaluation_protocol.md
│   └── api_reference.md
├── reproduce.sh                             # REQ-027.6
├── pyproject.toml
└── README.md
```

---

## 21. Dashboard Information Architecture and Design System (Phase 3)

**Satisfies:** REQ-018

### 21.1 Color Design System

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-base` | `#080D1A` | Application background |
| `bg-secondary` | `#0D1426` | Sidebar, secondary panels |
| `bg-panel` | `#121C32` | Cards, main content panels |
| `border-subtle` | `#24334D` | Card borders, dividers, separators |
| `accent-primary` | `#7777FF` | Primary actions, active nav, selected state, focus rings |
| `accent-secondary` | `#46D9F5` | Live data indicators, streaming events, real-time signals |
| `text-primary` | `#F3F6FC` | Main body text, headings |
| `text-secondary` | `#9BAAC2` | Labels, metadata, secondary information |
| `state-success` | `#39D98A` | TrustLevel HIGH, all-clear, nominal state |
| `state-warning` | `#F5B84B` | TrustLevel GUARDED/ELEVATED, anomaly signals, warnings |
| `state-critical` | `#FF637D` | TrustLevel LOW/CRITICAL, active threats, enforcement actions |

> **Security state indicators MUST always combine color + icon + text label. Color alone is never sufficient.** This applies to trust level badges, anomaly indicators, lease state badges, and enforcement outcome indicators. This rule is required for WCAG 2.1 Level AA compliance (REQ-018.5).

**Typography:** Inter or Geist Sans for all body and UI text. JetBrains Mono for `event_id`, `correlation_id`, `lease_id`, cryptographic hashes, `ReasonCode` values, and all structured identifiers.

### 21.2 Page Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│  bg-secondary                                                        │
│  VARYNX                 [● Live]  [Evaluation]  [Audit]  [Settings] │
│  ─────────────────────────────────────────────────────────────────── │
│  bg-secondary           │  bg-base / bg-panel                       │
│  Navigation             │  Main Content Area                        │
│  ─ Overview             │                                           │
│  ─ Agents      ● 3      │                                           │
│  ─ Sessions             │                                           │
│  ─ Evidence             │                                           │
│  ─ Trust                │                                           │
│  ─ BCSE        (Ph. 2)  │                                           │
│  ─ Responses            │                                           │
│  ─ Leases               │                                           │
│  ─ Audit                │                                           │
│  ─ Evaluation           │                                           │
│                         │                                           │
│  bg-panel               │                                           │
│  System Health          │                                           │
│  ● Event log: OK        │                                           │
│  ● Evidence: OK         │                                           │
│  ● Audit log: OK        │                                           │
│  ● Decisions: OK        │                                           │
└──────────────────────────────────────────────────────────────────────┘
```

### 21.3 Key Views

**Overview Dashboard**
- System-wide trust distribution histogram (bg-panel bars, accent-primary selected)
- Active sessions table: agent ID, trust level badge (color + icon + text), last event time, active lease count
- Recent anomaly feed: scrolling list with anomaly class, session, score, timestamp
- Response recommendation summary: counts by type, sparkline of last 24 hours
- No raw Behavioral_Event payloads are displayed (REQ-018.7)

**Agent Security Profile / Session Detail**
- Header: agent ID, session ID, trust score (large numeral), current level badge (color + icon + text)
- Trust history sparkline: full-width, bg-base background, accent-primary line, accent-secondary dot at current point
- Event timeline: chronological, color-coded by `authorization_result`
- Evidence panel: collapsible per-event; shows `detector_id`, `anomaly_class`, score per triggered detector
- Active leases table: capability, resource_scope, state badge, expiry
- Response history: `response_type` badge, reason codes (expandable structured cards showing `ReasonCode` detail)
- Sensitive `execution_context` fields are redacted or masked

**Counterfactual View (Phase 2)**
- Left panel: active policy consequence projection
- Right panel: alternative policy projections (one panel per `PolicyAlternative`)
- Divergence score meter
- Confidence badge per projection
- Prominent label: **"PROJECTED — not an observed fact"** on all projected values (REQ-021.6)
- `uncertainty_score` displayed alongside every projected risk level

**Audit View**
- Filterable table: `record_type`, `agent_id`, `correlation_id`, time range
- Hash-chain verification status: success indicator (state-success + checkmark + "Verified") or failure indicator (state-critical + warning icon + "TAMPER DETECTED")
- Expandable provenance chain per enforcement action (traceability query result)
- Export as JSON-L

**Evaluation View**
- Scenario selector (list with validation status badges)
- Baseline comparison matrix (B1–B4 metric cards side by side)
- Metric cards: DR, FPR, F1, MTTD, MTTR with mean ± CI
- Per-run result history table
- Ablation toggle panel: enable/disable individual detectors and subsystems
- Clear `INCOMPLETE` indicator when run count is below minimum (REQ-026.6)
- `SCENARIO_EXPECTATION_MISMATCH` entries highlighted in evaluation report view

---

## Error Handling

**Satisfies:** REQ-003, REQ-007, REQ-013, REQ-014, REQ-016, REQ-018, REQ-019, REQ-022, REQ-023, REQ-027

| Threat / Failure Condition | System Response |
|----------------------------|-----------------|
| **Invalid or malformed agent events** | Validated at REST API boundary before any internal component is reached. HTTP 422 with field-level errors. No unvalidated data enters the pipeline (REQ-016.2, REQ-027.8) |
| **Missing or incomplete evidence** | `EVIDENCE_DERIVATION_INCOMPLETE` status recorded on `EvidenceRecord`. Record excluded from trust scoring and decision generation. Never silently substituted with invented values (REQ-003.4) |
| **Evidence integrity violation** | Evidence record marked `INTEGRITY_VIOLATION`. Excluded from all computation. `AuditRecord` documenting the violation created. If all required records are violated, `DECISION_BLOCKED_EVIDENCE_INTEGRITY` alert emitted (REQ-014) |
| **Privilege / capability escalation** | `CAPABILITY_ESCALATION_DETECTED` or `SCOPE_ESCALATION_DETECTED` flagged on Agent_Context. Anomaly signal generated. Scope escalation counter incremented (REQ-002.3, REQ-002.4) |
| **BCSE internal error** | HTTP 503 with `BCSE_EVALUATION_FAILED`. No partial result returned. Pipeline continues with stub result (REQ-007.8) |
| **Adaptive response engine failure** | Safe-fail: MONITOR recommendation issued. `POLICY_TABLE_INVALID` logged. No silent blocking (REQ-011.7) |
| **Audit log integrity failure** | `TAMPER_DETECTED` flag surfaced to operator via audit integrity verification endpoint. Affected records identified (REQ-013.4) |
| **Unauthorized dashboard action** | 401 (unauthenticated) or 403 (insufficient permissions) returned from the REST API. No bypass path exists in the dashboard UI (REQ-018.4) |
| **Sensitive data in logs** | Configurable redaction list applied before any log emission. Events referenced by ID only (REQ-019.5) |
| **Simulated event contamination** | `is_simulated` label preserved through ingestion, storage, and all evaluation outputs. Simulated and non-simulated events never mixed in the same evaluation metric computation without explicit configuration (REQ-027.12) |
| **BCSE non-interference** | BCSE never writes to behavioral event log, evidence store, agent context, or lease state. Projected consequences never stored as `EvidenceRecord` entries (REQ-007.3, REQ-007.4) |
| **Enforcement idempotency** | Repeated enforcement of the same recommendation produces `SKIPPED` with `DUPLICATE_ENFORCEMENT` reason. No additional external state changes (REQ-022.8) |
| **Adapter exception** | Caught at adapter boundary. Logged as `ADAPTER_TRANSLATION_ERROR`. Not propagated to behavioral pipeline (REQ-023.5) |
| **Single malformed event** | Structured error returned; pipeline continues processing subsequent events. No unhandled exception terminates the ingestion pipeline (REQ-027.4) |
| **Storage subsystem unavailable** | HTTP 503 returned. `STORAGE_SUBSYSTEM_UNAVAILABLE` logged. Enforcement does not proceed without audit log write (REQ-017.4, REQ-022.5) |

---

## Testing Strategy

**Satisfies:** REQ-027 (testability), all component requirements

All testing uses **pytest** as the test runner and **Hypothesis** for property-based testing. Core behavioral analysis components are independently unit-testable without a running database or live agent framework — all storage and external dependencies are injectable and replaceable with in-memory stubs (REQ-027.9).

| Component / Invariant | Test Types | Key Invariants Verified |
|-----------------------|------------|------------------------|
| Event schema (REQ-001) | Property | For all valid `AgentActionEvent` objects, `deserialize(serialize(obj)) == obj` (REQ-016) |
| Timestamp validation (REQ-001.3) | Property | Hypothesis generates timestamps at and around ±300/60s boundary; all out-of-range values rejected |
| Duplicate action_id (REQ-001.4) | Property | Hypothesis generates event batches with collisions; all duplicates rejected with HTTP 409 |
| correlation_id uniqueness (REQ-001.5, REQ-012.4) | Property | For all generated event batches, all assigned `correlation_id` values are distinct |
| Scope escalation detection (REQ-002.3) | Property | For all generated capability/resource scope pairs, out-of-scope actions trigger the signal |
| Evidence derivation (REQ-003) | Property | For all accepted `AgentActionEvent` inputs, a corresponding `EvidenceRecord` is produced with non-null `evidence_id` and matching `correlation_id` |
| Evidence immutability (REQ-003.5) | Unit | Attempt to modify stored evidence record; verify rejection |
| Anomaly signal generation (REQ-004) | Unit + Property | Unit: representative event sequences trigger named signals. Property: repeated denial signals generated for all inputs where denial count exceeds threshold within window |
| Trust score range [0.0, 1.0] (REQ-005.2) | Property | Hypothesis generates extreme weight and score combinations; output always in [0.0, 1.0] |
| Trust score determinism (REQ-009.3) | Unit | Identical inputs produce identical scores across multiple invocations |
| Incomplete evidence exclusion (REQ-005.4) | Unit | Score computed with and without `EVIDENCE_DERIVATION_INCOMPLETE` records; excluded count recorded |
| Spread counters monotonic (REQ-006) | Property | For any append-only event stream, resource and capability spread counters are monotonically non-decreasing |
| BCSE non-interference (REQ-007.3) | Integration | Event log and evidence store state are identical before and after a BCSE evaluation call |
| BCSE uncertainty in [0.0, 1.0] (REQ-007) | Property | Hypothesis generates BCSE input contexts; `uncertainty_score` always in [0.0, 1.0] |
| Projected values labeled PROJECTED (REQ-021.6) | Unit | All `TrajectoryProjection` and `ConsequenceProjection` instances have `is_projected=True` |
| Projected trust at horizon in [0.0, 1.0] (REQ-021) | Property | Hypothesis generates trust history inputs; projected value always in [0.0, 1.0] |
| Response determinism (REQ-009.3) | Property | Identical `EvidenceBundle` + `TrustState` + policy produce identical `ResponseType` and `ReasonCode` list |
| Reason codes in enumerated set (REQ-009.2) | Property | For all generated evidence sets, `ReasonCode.code` values are always members of the documented set |
| Escalation threshold (REQ-011.2, REQ-011.3) | Property | For any score below critical threshold with degrading trajectory, recommendation is never MONITOR |
| REVOKED lease terminal (REQ-010.6) | Property | For any generated event sequence, a REVOKED lease never transitions to any other state |
| Suspension cascade (REQ-010.4) | Unit | SUSPEND recommendation triggers state change on all ACTIVE leases for the agent |
| Enforcement idempotency (REQ-022.8) | Property | Repeated application of same recommendation for same agent produces no additional enforcement effects |
| Audit append-only (REQ-013.3) | Unit | Attempt UPDATE/DELETE on audit_log; verify rejection at DB level |
| Hash-chain tamper detection (REQ-013.4) | Unit | Modify stored audit record content; verify `TAMPER_DETECTED` on integrity check |
| Traceability chain integrity (REQ-012.5) | Unit | Remove a record from chain; verify `CHAIN_INTEGRITY_VIOLATION` flag on query |
| Evidence integrity block (REQ-014.4) | Unit | Mark all required evidence as `INTEGRITY_VIOLATION`; verify `DECISION_BLOCKED_EVIDENCE_INTEGRITY` |
| Audit record no-duplication (REQ-013.6) | Unit | Audit records contain only IDs referencing source records, not content copies |
| Configuration validation (REQ-020.3) | Property | For all valid configuration objects, system applies them without error. Invalid configs fail with descriptive `CONFIGURATION_INVALID` |
| Scenario determinism (REQ-025.5) | Property | Identical seed + scenario file + config → identical behavioral analysis outputs |
| is_simulated preserved (REQ-025.3) | Unit | Events ingested with `is_simulated=True` retain the flag through storage, evidence derivation, and evaluation outputs |
| Evaluation metrics in [0.0, 1.0] (REQ-026) | Property | For all valid per-run metric sets, precision/recall/F1 are in [0.0, 1.0] |
| Reported mean within CI (REQ-026) | Property | For all valid sets of per-run metrics, reported mean is within reported 95% confidence interval |
| Incomplete run report (REQ-026.6) | Unit | Report with fewer than minimum runs is marked `INCOMPLETE` |
| Pipeline resilience (REQ-027.4) | Integration | Submit malformed event; verify structured error returned and subsequent events processed normally |
| Adapter exception isolation (REQ-023.5) | Unit | Raise exception in adapter `adapt()`; verify pipeline continues and `ADAPTER_TRANSLATION_ERROR` logged |
| Full pipeline (REQ-027.11) | Integration | Submit `AgentActionEvent` → verify evidence derivation → anomaly detection → trust scoring → Security_Decision generated → `EnforcementRecord` produced |

---

## 24. Assumptions, Limitations, Unresolved Interfaces, and Future Extensions

### 24.1 Known Open Questions

**Trust scoring calibration.** The `sensitivity` and `temporal_decay_rate` parameters in the trust score formula are initial proposals (default 1.0 and 0.01 respectively). Their appropriateness for any specific deployment environment requires empirical evaluation. Claims about detection performance cannot be made until calibration experiments are executed per REQ-024 and REQ-026.

**BCSE Phase 2 algorithm.** The policy simulation and consequence projection algorithm for the Phase 2 BCSE engine is not yet finalized. The Phase 1 stub interface is designed to be a drop-in replacement target. The Phase 2 design will be specified in a design amendment after Phase 1 is implemented and evaluated.

**Predictive trajectory algorithm.** Linear regression over `TrustHistoryEntry` is proposed as the Phase 2 baseline algorithm. It may be replaced by a more appropriate statistical model (e.g., exponential smoothing, ARIMA) pending empirical evaluation of its sensitivity to trajectory classification threshold settings.

**Cross-session trust aggregation.** Phase 1 tracks trust per session. Whether and how to aggregate trust across an agent's session history to produce a lifetime trust profile is deferred to Phase 2.

**Framework adapter implementations.** The `AgentAdapterProtocol` interface and the `SimulatedEventAdapter` are Phase 1 deliverables. Adapters for real AI agent frameworks (LangGraph, AutoGen, and others) are out of scope for Phase 1. Their design and packaging are Phase 2+ items.

**Multi-agent federation.** Scenarios involving coordination between multiple Varynx instances, shared trust state, or federated evidence correlation are deferred to Phase 3+.

**Production SLA and multi-tenancy.** This design targets a research and evaluation deployment. Production SLA hardening (HA, multi-region, tenant isolation) is Phase 3 scope and is not designed here.

**Threshold empirical calibration.** All default threshold values documented in this design (authorization denial count=3, window=300s, resource spread=10 domains in 600s, capability spread=5, escalation threshold=0.4, critical threshold=0.2, de-escalation threshold=0.7) are initial design proposals. Per the Research Integrity Notice in requirements.md, their appropriateness must be measured experimentally before any performance claims are made.

**Statistical power.** Five repeated runs (REQ-024.4) may be insufficient for statistical power depending on effect sizes encountered. The minimum run count is a floor; actual experiment design should include a power analysis.

### 24.2 Interface Stability Contract

After Phase 1 completion, the following interfaces are considered stable and MUST NOT be changed without a version bump and migration path:

- `AgentActionEvent` (primary ingestion schema)
- `EvidenceRecord` and `EvidenceBundle`
- `TrustState` and `TrustHistoryEntry`
- `ResponseRecommendation` and `ReasonCode`
- `AuditRecord` and `AuditRecordType`
- `AnomalyDetector` Protocol
- `BCSeEngine` Protocol (stub or real)
- `PredictiveEngine` Protocol (stub or real)
- `AgentAdapterProtocol`

Phase 2 implementations of BCSE and predictive engines must conform to the Phase 1 protocol definitions without requiring changes to existing tests or consumers.

---

*End of Design Specification*

*Status: PROPOSED — Not Yet Implemented. All data models, component designs, API contracts, database schemas, and configuration structures in this document are forward specifications. No component has been implemented, tested, or verified against production workloads.*

---

## Correctness Properties

*Property-based testing (PBT) verifies universal invariants that hold across all valid inputs. The following 26 properties define the formal correctness contract for Varynx and are testable via Hypothesis. Each property is a universally quantified statement with cross-references to the requirements it validates. All properties are PROPOSED — Not Yet Implemented; no property has been verified by a passing test suite at the time of authoring. Property tests will be written alongside the component implementations described in `tasks.md` (Phase 10).*

---

### Property 1: Valid event storage produces required identifiers

*For any* valid `AgentActionEvent` submitted to the ingestion layer, the system SHALL store the event and return a record containing a non-null `event_id` and a non-null, unique `correlation_id`.

**Validates: Requirements 1.1, 1.5**

---

### Property 2: Missing required fields are rejected

*For any* `AgentActionEvent`-shaped object with one or more required fields absent, the system SHALL reject the submission with an HTTP 422 response that identifies every missing field.

**Validates: Requirements 1.2**

---

### Property 3: Out-of-range timestamps are rejected

*For any* timestamp value that falls more than 300 seconds before or more than 60 seconds after the system wall clock at the time of submission, the system SHALL reject the event with an HTTP 422 response and a `TIMESTAMP_OUT_OF_RANGE` reason code.

**Validates: Requirements 1.3**

---

### Property 4: Duplicate action_id for same agent is rejected and correlation_id is unique

*For any* pair of events sharing the same `agent_id` and `action_id`, the second submission SHALL be rejected with an HTTP 409 response. Furthermore, *for any* batch of accepted events, all assigned `correlation_id` values SHALL be distinct.

**Validates: Requirements 1.4, 12.4**

---

### Property 5: Scope escalation is detected for all out-of-scope resource access

*For any* `(authorized_resource_scope, requested_resource)` pair where the requested resource falls outside the authorized scope, the system SHALL flag the action as `SCOPE_ESCALATION_DETECTED` and increment the agent's scope escalation counter.

**Validates: Requirements 2.3**

---

### Property 6: Capability escalation is detected for all out-of-scope action types

*For any* `(declared_capability_scope, action_type)` pair where the `action_type` falls outside the agent's declared capability scope, the system SHALL flag the action as `CAPABILITY_ESCALATION_DETECTED`.

**Validates: Requirements 2.4**

---

### Property 7: Accepted events produce evidence records with correct linkage

*For any* accepted `AgentActionEvent`, the system SHALL produce one or more `EvidenceRecord` instances, each with a non-null `evidence_id`, a `correlation_id` matching the source event's `correlation_id`, and a non-empty cryptographic `content_hash`.

**Validates: Requirements 3.1, 3.2, 3.6**

---

### Property 8: Incomplete evidence records are flagged and excluded from scoring

*For any* `EvidenceBundle` containing one or more records with `derivation_status = EVIDENCE_DERIVATION_INCOMPLETE`, those records SHALL be excluded from the trust score computation, and the exclusion count SHALL be recorded in the agent's score metadata.

**Validates: Requirements 3.4, 5.4**

---

### Property 9: Authorization denial threshold triggers bypass signal

*For any* event sequence where an agent receives three or more authorization denials within the configured time window, the system SHALL generate an anomaly signal of type `AUTHORIZATION_BYPASS_ATTEMPT`. Conversely, *for any* sequence where the denial count remains strictly below the threshold within the window, no such signal SHALL be generated.

**Validates: Requirements 4.2**

---

### Property 10: Trust score is always in [0.0, 1.0]

*For any* combination of current trust score, evidence bundle composite score, evidence weight, sensitivity parameter, temporal decay rate, and session age, the trust score update formula SHALL produce a value in [0.0, 1.0] inclusive. No input combination may yield a value outside this range.

**Validates: Requirements 5.2**

---

### Property 11: Trust score history entry is structurally complete

*For any* trust score update, the appended `TrustHistoryEntry` SHALL contain: non-null `entry_id`, `timestamp`, `prior_score`, `new_score`, `delta`, and a list of contributing evidence record identifiers (empty only when all records were incomplete, with the exclusion count recorded).

**Validates: Requirements 5.6**

---

### Property 12: Resource and capability spread counters are monotonically non-decreasing

*For any* append-only sequence of accepted events for an agent, the resource spread count and capability spread count on the agent's context record SHALL never decrease between consecutive events.

**Validates: Requirements 6.1, 6.2**

---

### Property 13: BCSE evaluation is non-interfering

*For any* `BCSeContext` submitted to the BCSE engine, the state of the behavioral event log, evidence store, agent context records, and capability lease records SHALL be identical before and after the BCSE evaluation call. BCSE SHALL NOT create, modify, or delete any record in those stores.

**Validates: Requirements 7.3, 7.4**

---

### Property 14: BCSE uncertainty score is in [0.0, 1.0]

*For any* `BCSeContext` input, the `uncertainty_score` field in the resulting `BCSeResult.active_consequence` SHALL be in [0.0, 1.0] inclusive.

**Validates: Requirements 7.2**

---

### Property 15: Low-history BCSE returns uncertainty=1.0 and UNKNOWN risk

*For any* BCSE evaluation where the agent's accepted event count is strictly below the configured minimum history threshold, the result SHALL have `uncertainty_score = 1.0`, `low_history_warning = True`, and `risk_level = "UNKNOWN"`.

**Validates: Requirements 7.5**

---

### Property 16: Projected values are never stored as EvidenceRecords

*For any* execution of the predictive intelligence layer or BCSE engine, the evidence store SHALL contain no `EvidenceRecord` entries whose `provenance` traces to a projected (non-observed) value. The `is_projected = True` marker SHALL be present on all `ConsequenceProjection` and `TrajectoryProjection` instances.

**Validates: Requirements 7.4, 21.7**

---

### Property 17: Security_Decision generation is deterministic

*For any* `(EvidenceBundle, TrustState, active_policy)` triple, the Adaptive_Response_Engine SHALL produce identical `ResponseType` and `ReasonCode` list on repeated invocations under identical configuration.

**Validates: Requirements 9.3**

---

### Property 18: Reason codes are members of the versioned enumerated set

*For any* generated `Security_Decision`, every `ReasonCode.code` value SHALL be a member of the documented, versioned enumerated set. The Reason_Code set SHALL NOT change between system versions without a versioned migration path.

**Validates: Requirements 9.2**

---

### Property 19: REVOKED capability leases are a terminal state

*For any* `CapabilityLease` in `REVOKED` state, no event sequence SHALL cause a transition to `ACTIVE`, `SUSPENDED`, or `EXPIRED`. Revocation is terminal.

**Validates: Requirements 10.6**

---

### Property 20: Escalation threshold and de-escalation gating

*For any* agent whose `Behavioral_Trust_Score` is below the critical threshold with a `degrading` trajectory, the Adaptive_Response_Engine SHALL recommend `SUSPEND` or higher severity — never `MONITOR`. Conversely, *for any* agent whose score rises above the de-escalation threshold, the engine SHALL NOT recommend escalation without corroborating anomaly signals.

**Validates: Requirements 11.2, 11.3, 11.5**

---

### Property 21: Enforcement is idempotent

*For any* `(ResponseRecommendation, agent_id)` pair, applying the same `source_recommendation_id` more than once SHALL produce no additional external state changes; subsequent applications yield an `EnforcementRecord` with `outcome=SKIPPED` and `outcome_reason=DUPLICATE_ENFORCEMENT`.

**Validates: Requirements 22.8**

---

### Property 22: Audit log is append-only

*For any* `AuditRecord` after creation, no `UPDATE` or `DELETE` operation SHALL succeed against the `audit_log` table. The append-only constraint is enforced at the database privilege level, not solely in application logic.

**Validates: Requirements 13.3**

---

### Property 23: Hash-chain tamper detection

*For any* `AuditRecord` whose stored content is modified after creation, the hash-chain integrity verification SHALL return a `TAMPER_DETECTED` flag for that record. Similarly, *for any* `EvidenceRecord` that fails hash verification, the system SHALL mark it `INTEGRITY_VIOLATION` and SHALL NOT use it in any subsequent computation or decision.

**Validates: Requirements 13.4, 14.1, 14.2**

---

### Property 24: Traceability chain integrity violation is reported

*For any* traceability query where one or more referenced records in the chain are missing, the system SHALL return a `CHAIN_INTEGRITY_VIOLATION` flag identifying the gap rather than silently returning an incomplete chain.

**Validates: Requirements 12.5**

---

### Property 25: Scenario execution is deterministic

*For any* scenario YAML file, random seed, configuration snapshot, and software version, repeated executions of the evaluation pipeline SHALL produce identical behavioral analysis outputs and identical quantitative metrics.

**Validates: Requirements 15.4, 25.5**

---

### Property 26: API serialization round-trip preserves all fields

*For any* valid API request object (including `AgentActionEvent`, `BCSeContext`, and all response models), `deserialize(serialize(obj)) == obj` SHALL hold — no field loss or type coercion SHALL occur.

**Validates: Requirements 16.2**

---

*End of Correctness Properties. All 26 properties are PROPOSED — Not Yet Implemented. They will be verified by the Hypothesis-based property tests defined in Phase 10 of `tasks.md`.*
