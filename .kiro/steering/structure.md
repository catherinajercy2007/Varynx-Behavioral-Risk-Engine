# Varynx — Repository Structure Steering

## Repository map
The following is a high-level map based on the repository documentation and manifests. Inspect the checked-out tree before assuming a file or subdirectory exists.

```text
.
├── .kiro/                  # Kiro specifications and project guidance
├── varynx/                 # Python backend package
│   ├── api/                # FastAPI application and routes
│   ├── engine/             # Runtime/security engine components
│   ├── models/             # Domain and API data models
│   ├── evaluation/         # Evaluation code
│   └── aws/                # AWS adapters and related integrations
├── tests/                  # Automated tests
│   ├── unit/
│   ├── integration/
│   ├── property/
│   └── benchmarks/
├── scenarios/              # Scenario inputs for evaluation
├── config/                 # Policy and threshold configuration
├── docs/                   # Research and engineering documentation
├── dashboard/              # Next.js analyst dashboard
├── dashboard_streamlit/    # Streamlit dashboard
├── docker/                 # Container and compose assets
├── alembic/                # Database migration assets
├── pyproject.toml           # Python package and tooling configuration
├── README.md                # Project overview and setup
└── buildspec.yml            # AWS CodeBuild build specification, if present
```

## Ownership boundaries
- `varynx/api/`: HTTP interface, request/response handling, and API routing. Keep core domain logic out of route handlers where the existing architecture provides engine services.
- `varynx/engine/`: runtime orchestration and security decision components. Preserve separation between authorization, behavioral analysis, response selection, audit, and resource mediation.
- `varynx/models/`: shared domain/data models. Avoid duplicating equivalent model definitions in route or dashboard code.
- `varynx/evaluation/`: scenario execution, metrics, comparisons, and research evaluation. Keep experimental code clearly labeled and reproducible.
- `varynx/aws/`: cloud adapters and AWS-specific integration. Clearly distinguish local/mock behavior from real AWS calls.
- `tests/`: tests organized by scope. Add regression tests alongside the relevant existing test organization.
- `dashboard/`: Next.js frontend. Run frontend commands from this directory.
- `dashboard_streamlit/`: Streamlit frontend. Do not assume it shares the Next.js build process.
- `scenarios/`, `config/`, and `docs/`: supporting experiment inputs, configuration, and project documentation.

## Change placement rules
1. Put backend behavior in the appropriate `varynx/` package module, not in dashboard-only code.
2. Put frontend presentation and browser interaction in the appropriate dashboard.
3. Put reusable test fixtures in the existing test fixture location rather than copying them into production modules.
4. Put research scenarios and evaluation outputs in their established locations; do not commit transient logs or local runtime databases as research evidence.
5. Update README and relevant docs when setup, public interfaces, security semantics, or repository layout changes.
6. Do not create a second implementation of an existing engine, API client, or shared model without a documented reason.

## Repository hygiene
Do not commit:
- `.venv/`, virtual environments, Python bytecode, `__pycache__/`, or test caches.
- Local `.env` files, credentials, tokens, private keys, or populated MCP configuration containing secrets.
- Local databases, runtime state, generated logs, temporary scripts, editor caches, and backup/snapshot archives.
- Machine-specific absolute paths.

Commit sanitized templates such as `.env.example` or `mcp.json.example` only when they contain placeholders and are genuinely useful to contributors.
