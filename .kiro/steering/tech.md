# Varynx — Technical Steering

## Supported project stack
Use the versions and constraints declared by the repository manifests as the source of truth.

### Backend
- Python project; `pyproject.toml` currently declares Python `>=3.11`.
- FastAPI for the HTTP API.
- Pydantic v2 and `pydantic-settings` for data models and settings.
- Uvicorn for serving the API.
- PyYAML and python-dotenv are declared runtime dependencies.
- HTTPX is used by the project for HTTP-related functionality and testing.
- Optional database dependencies are declared in the `db` extra; check current configuration and migrations before assuming a database backend is active.

### Frontend
- `dashboard/` is the Next.js analyst dashboard.
- The current `dashboard/package.json` declares Next.js 14.2.35, React 18, TypeScript, and Tailwind CSS.
- `dashboard_streamlit/` is a separate Streamlit dashboard directory in the integrated repository. Keep its setup and deployment distinct from the Next.js application.

### AWS and deployment
- AWS-related adapters and deployment templates exist in the repository.
- Treat LOCAL_MODE, mocks, and templates as non-production unless real credentials, service calls, integration tests, and deployment evidence establish otherwise.
- Never commit AWS access keys, secret keys, session tokens, private certificates, or populated secret environment files.
- Prefer least-privilege IAM and short-lived credentials for real integrations.

### Quality and tests
- pytest is the test runner.
- Hypothesis is used for property-based testing.
- Ruff and mypy are declared development tools.
- Run focused tests for the changed component, then the relevant broader suite.
- Report the exact command and result; do not reuse historical test counts as current results.

## Engineering rules
- Follow existing module boundaries and naming conventions before introducing new abstractions.
- Prefer small, typed, testable changes over broad rewrites.
- Preserve API compatibility unless a breaking change is intentional and documented.
- Validate external input at boundaries.
- Keep policy evaluation, identity/lease validation, behavioral risk analysis, response selection, and external enforcement conceptually separate.
- Make failure behavior explicit. Do not silently retry operations whose external side-effect status is indeterminate.
- Treat audit records and security-relevant state as sensitive; avoid logging credentials, tokens, or unnecessary personal data.
- Keep configuration external to source code. Provide safe examples rather than real secrets.
- Do not add dependencies without explaining why they are needed and updating the relevant manifest and lockfile, if present.

## Verification workflow
For backend changes, use the repository's Python environment and run focused pytest tests. For frontend changes, work from `dashboard/` and use its package scripts. For Streamlit changes, verify the Streamlit application independently.

Before declaring a change complete:
1. Inspect `git diff`.
2. Run relevant tests, type/lint checks where applicable.
3. Check for secrets and machine-specific paths.
4. Update documentation if behavior or setup changed.
5. State what was not tested.
