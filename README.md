# VARYNX
### Behavioral Risk Control Engine for Autonomous AI Agents

**Research Theme:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents

Varynx is a research-oriented security platform designed to evaluate the behavior of autonomous AI agents and support risk-aware runtime control. It combines behavioral evidence, agent trust histories, policy evaluation, counterfactual analysis, predictive signals, adaptive responses, and auditable security decisions.

The objective is to move beyond static permission checks by considering not only what an agent is authorized to do, but also the context and behavioral evidence surrounding its proposed actions.

> **Research principle:** Behavioral anomalies are risk signals, not proof of malicious intent. Security decisions must remain policy-grounded, explainable, and testable.

---

## Platform Overview

Varynx is designed around three operational questions:

- **Observe:** What is the agent attempting to do, and how does this compare with its established behavior?
- **Evaluate:** How do trust, policy constraints, behavioral evidence, and predictive signals affect the risk of the proposed action?
- **Control:** What response is appropriate, and can the resulting decision be traced and evaluated?

The platform includes a Python security engine, a REST API, an analyst dashboard, an evaluation framework, and cloud-adapter modules.

## Core Capabilities

| Capability | Purpose |
|---|---|
| Agent identity and authorization | Associate actions with an agent identity and enforce policy constraints |
| Behavioral evidence | Collect and evaluate signals relevant to agent behavior |
| Dynamic behavioral trust | Maintain trust histories and assess changes in agent reliability |
| Risk assessment | Combine relevant security evidence into a risk evaluation |
| BCSE | Evaluate alternative policy outcomes and counterfactual security decisions |
| Predictive analysis | Analyze trust histories for potential future behavioral changes |
| Adaptive response | Map security assessments to appropriate response actions |
| Audit integrity | Maintain structured audit records and support hash-chain verification |
| Evaluation framework | Execute scenarios and measure system behavior |
| Cloud adapters | Provide integration points for supported AWS services |
| Analyst dashboard | Present agent profiles, audit records, evaluation results, and security information |

Implementation maturity varies by component. A listed capability does not imply that every production integration or research hypothesis has been validated.

---

## Dashboard Experience

The Varynx analyst dashboard is built with Next.js, React, TypeScript, and Tailwind CSS.

The planned visual direction is a modern security operations console featuring:

- A persistent navigation sidebar.
- A high-contrast dark interface.
- Clear agent identity and trust information.
- Risk and response summaries.
- Behavioral activity and anomaly views.
- Searchable agent and audit tables.
- Counterfactual evaluation results.
- Research evaluation metrics.
- Responsive layouts for desktop and smaller screens.

Dashboard information must distinguish live API results from mock data, unavailable services, and empty states. Security indicators must not imply that a check succeeded when its result is unknown.

### Dashboard sections

| Section | Intended function |
|---|---|
| Overview | Summarize security activity and system health |
| Agents | Inspect agent identity, trust, behavior, and status |
| Audit Log | Review security events and decision provenance |
| Evaluation | Inspect scenario results and research metrics |
| BCSE | Compare alternative security decisions |
| Predictive Analysis | Explore available trust-history predictions |
| Settings | Configure supported API connection and display options |

The actual routes and API capabilities should be verified against the current implementation before enabling any section.

---

## Architecture

```text
                  AUTONOMOUS AI AGENT
                           |
                           v
                  Proposed Agent Action
                           |
                           v
                  Identity and Policy
                           |
                           v
                  Behavioral Evidence
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
       Trust History   Anomaly Signals  Context
             |             |             |
             +-------------+-------------+
                           |
                           v
                     Risk Assessment
                           |
                 +---------+---------+
                 |                   |
                 v                   v
          BCSE Evaluation     Predictive Analysis
                 |                   |
                 +---------+---------+
                           |
                           v
                  Adaptive Response
                           |
                           v
                  Enforcement Layer
                           |
                           v
                   Audit and Evidence
                           |
                           v
                  Analyst Dashboard
```

This diagram represents the conceptual security workflow. The actual execution order and enforcement guarantees depend on the implemented pipeline and must be verified through integration tests.

### Technology stack

| Layer | Technology |
|---|---|
| Core engine | Python |
| API | FastAPI |
| Dashboard | Next.js 14 |
| UI framework | React |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Testing | pytest |
| Data and migrations | In-memory storage support, PostgreSQL/TimescaleDB configuration, and Alembic migrations |
| Cloud integrations | AWS adapter modules |
| Research evaluation | Scenario-driven evaluation and reproducibility tooling |

---

## Repository Structure

```text
varynx/
├── varynx/             # Core Python package
│   ├── engine/         # Security and decision pipeline
│   ├── models/         # Data models
│   ├── api/            # REST API
│   ├── evaluation/     # Scenario evaluation
│   ├── aws/            # AWS integration adapters
│   └── config/         # Configuration
├── dashboard/         # Next.js analyst dashboard
│   ├── app/            # App Router pages and layouts
│   ├── public/         # Static assets
│   └── package.json
├── tests/              # Automated tests
│   ├── unit/
│   ├── property/
│   ├── integration/
│   └── benchmarks/
├── scenarios/          # Evaluation scenarios
├── config/             # Policies and threshold configuration
├── docs/               # Research and technical documentation
├── docker/             # Container configuration
├── alembic/            # Database migrations
├── reproduce.sh        # Reproducibility workflow
└── README.md
```

This structure reflects the documented repository layout. Some directories or filenames may differ between branches.

---

## Getting Started

### Prerequisites

Install the following:

- Python 3.11 or a Python version supported by the project's dependency configuration.
- Node.js 18 or later, compatible with the dashboard's Next.js version.
- npm.
- Git.

PostgreSQL or AWS credentials are only needed for workflows that use those integrations.

### 1. Clone the repository

```bash
git clone https://github.com/catherinajercy2007/Varynx-Behavioral-Risk-Engine.git
cd Varynx-Behavioral-Risk-Engine
```

### 2. Create a Python environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks activation, use the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

These commands assume the repository contains the documented Python package configuration. If installation fails, inspect `pyproject.toml` and follow the dependency configuration in your checked-out branch.

### 3. Configure the API

For local development, configure the database URL:

**Windows PowerShell:**

```powershell
$env:VARYNX_DATABASE_URL = "memory://dev"
```

**Linux/macOS:**

```bash
export VARYNX_DATABASE_URL="memory://dev"
```

Start the API:

```bash
uvicorn varynx.api.app:app --host 127.0.0.1 --port 8000 --reload
```

API documentation:

`http://127.0.0.1:8000/api/v1/docs`

Keep the API bound to localhost during local development.

### 4. Configure authentication for protected deployments

Before exposing the API to other machines or the public internet, configure authentication:

**Windows PowerShell:**

```powershell
$env:VARYNX_API_KEY = "replace-with-a-secure-secret"
$env:VARYNX_REQUIRE_API_KEY = "true"
```

**Linux/macOS:**

```bash
export VARYNX_API_KEY="replace-with-a-secure-secret"
export VARYNX_REQUIRE_API_KEY="true"
```

Clients must supply the expected API key using the authentication header supported by the backend.

Never commit API keys, cloud credentials, or production secrets. Use a secrets manager or the deployment platform's secret configuration for protected environments.

A production deployment also requires appropriate TLS termination, network restrictions, monitoring, and security review.

### 5. Start the dashboard

Open a second terminal:

```bash
cd dashboard
npm install
npm run dev
```

Open:

`http://localhost:3000`

Configure the dashboard to use the running API:

**Windows PowerShell:**

```powershell
$env:VARYNX_API_URL = "http://127.0.0.1:8000/api/v1"
npm run dev
```

**Linux/macOS:**

```bash
export VARYNX_API_URL="http://127.0.0.1:8000/api/v1"
npm run dev
```

The dashboard's current implementation must be checked to determine whether this environment variable is read by server-side code or exposed to browser-side code. Do not assume a server-only variable is automatically available in browser components.

If a browser component needs the URL directly, use a deliberately configured public environment variable only when appropriate, and never expose secrets through public variables.

The backend must implement the endpoints the dashboard requests. A successful frontend build does not establish that live API integration works.

---

## Testing

Run the full Python test suite:

```bash
python -m pytest tests/ -q
```

Run focused suites when diagnosing failures:

```bash
python -m pytest tests/unit/ -v
python -m pytest tests/property/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/benchmarks/ -v -s
```

Some directories may not exist in every branch. Use the actual test structure in the checked-out version.

For dashboard validation:

```bash
cd dashboard
npm install
npm run build
```

Run the development server and test the actual navigation, loading states, API responses, error handling, and responsive layout.

Record the actual results from the current environment. Do not reuse historical test counts as evidence that a newer revision passes.

---

## Evaluation and Reproducibility

Varynx includes scenario-driven evaluation tooling for repeatable experiments.

Where supported by the checked-out implementation, run the reproducibility script:

```bash
./reproduce.sh
```

For a fixed random seed:

```bash
./reproduce.sh --skip-install --seed 42
```

On Windows, use an appropriate Bash environment if the script requires one.

When reporting evaluation results, document:

- Dataset or scenario source.
- Number and type of scenarios.
- Random seed and configuration.
- Baseline methods.
- Detection and response metrics.
- Threshold selection.
- Repeated-run results and uncertainty.
- Runtime and resource measurements.
- Known limitations.

Synthetic scenarios can help validate controlled behavior, but they do not by themselves establish real-world detection effectiveness.

---

## Database and Cloud Integrations

The repository documents PostgreSQL/TimescaleDB configuration and AWS service adapters.

A documented adapter is not proof of a working live integration.

Before reporting a cloud integration as production-ready, verify authentication, permissions, request behavior, error handling, retry policies, logging, and integration tests against the intended environment.

For database-backed testing, follow the repository's migration configuration and use an isolated development database.

Never use production data or credentials in experiments without appropriate authorization and safeguards.

---

## Research Integrity and Limitations

Varynx is a research-oriented system. Its results must be evaluated empirically.

The repository's previous documentation reported 329 passing tests, implemented BCSE and predictive-analysis components, and AWS adapters operating in local mode by default. Those are historical claims and should be revalidated against the current commit before being presented as current status.

Important limitations to assess include:

- Whether persistent event and trust storage is fully integrated.
- Whether BCSE and predictive outputs improve security outcomes under controlled evaluation.
- Whether evaluation scenarios cover the stated research hypotheses.
- Whether threshold choices have been calibrated on appropriate data.
- Whether cloud adapters have been tested against live services.
- Whether dashboard views reflect live backend data.
- Whether production deployment, authentication, and operational controls have been verified.

The project must distinguish between implemented code, passing tests, experimental evidence, and production validation.

---

## Development Workflow

Use a feature branch for each independently reviewable change.

```bash
git fetch origin
git branch --show-current
git status
git diff --check
```

Before committing:

1. Confirm the correct repository and branch.
2. Review all modified files.
3. Run the relevant tests.
4. Check that no secrets or local artifacts are included.
5. Commit the intended changes.
6. Push the feature branch.
7. Open a pull request against the team's agreed integration branch.

Do not force-push shared branches or merge unreviewed changes into the main branch.

---

## Project Goal

Varynx aims to provide an auditable and experimentally evaluable approach to behavioral risk control for autonomous AI agents.

Its long-term direction is to connect behavioral evidence, dynamic trust, policy-grounded decisions, counterfactual evaluation, predictive analysis, and runtime enforcement within a coherent security architecture.

The strength of the project should be demonstrated through reproducible experiments, defensible baselines, transparent limitations, and verified implementation—not through feature claims alone.

---

**Project:** Varynx — Behavioral Risk Control Engine  
**Research Area:** Runtime Security · Autonomous AI Agents · Behavioral Risk Analysis · Cloud-Native Security
