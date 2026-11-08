# Varynx — Product Steering

## Product identity
Varynx is a behavioral risk control engine for autonomous AI agents.

Research title: **Cloud-Native Behavioral Risk Control for Autonomous AI Agents**.

Varynx is intended to collect behavioral evidence about agents, maintain agent-related trust context, evaluate proposed actions, and provide structured security decisions or recommendations to the surrounding enforcement layer.

## Problem being addressed
Autonomous agents can invoke tools, APIs, data stores, and other resources. A static permission check alone may not capture whether an otherwise permitted action is anomalous in its current behavioral context. Varynx explores runtime decisions informed by policy, identity/session context, behavioral evidence, trust, and risk.

## Product boundaries
- Treat Varynx as a research and engineering system, not as a universally novel solution.
- Distinguish a decision or recommendation emitted by Varynx from enforcement performed by an external host, cloud service, or resource.
- Do not claim that an external agent process is terminated unless the host actually performs that operation.
- Do not claim real AWS integration or production deployment merely because adapters, templates, or mocked tests exist.
- Do not claim exactly-once execution across an external side effect and a local database transaction.
- Describe synthetic evaluation results as synthetic; do not generalize them to production workloads without evidence.

## Main capabilities represented in the repository
- FastAPI-based API surface.
- Agent identity, session, authorization, and lease-related components.
- Behavioral evidence and risk evaluation components.
- BCSE and predictive evaluation components.
- Adaptive response and audit-related components.
- AWS adapter and deployment-related code.
- A Next.js analyst dashboard under `dashboard/`.
- A Streamlit dashboard under `dashboard_streamlit/` where present in the checked-out repository.
- Automated tests and evaluation/scenario assets.

The exact implementation status of any capability must be checked in source code and tests before documenting it as complete.

## Decision and enforcement language
Use the action names and semantics implemented by the current code. In particular:
- A behavioral approval does not override an invalid or expired authorization lease.
- A hold, escalation, restriction, suspension, or termination decision must not be described as successful external enforcement unless the relevant host or integration confirms it.
- For resource operations, distinguish policy evaluation, authorization, gateway mediation, and actual resource-side effect.

## Research integrity
- Report measured results only when the experiment or test actually produced them.
- State the dataset, scenario set, seed, configuration, and evaluation method when making quantitative claims.
- Do not describe a passing unit-test suite as proof of security, cloud readiness, or production reliability.
- Preserve limitations and unresolved hypotheses in documentation.
- Avoid unqualified claims such as “fully secure,” “production-ready,” “real-time prevention,” or “zero-trust enforcement.”

## Documentation expectations
When changing product behavior:
1. Update the relevant specification and implementation documentation.
2. Add or update tests for the behavior.
3. Record assumptions, limitations, and failure modes.
4. Keep README claims consistent with the implementation and current test results.
