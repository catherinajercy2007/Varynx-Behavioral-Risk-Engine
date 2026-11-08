
# Varynx — Behavioral Risk Control Engine

**Research Title:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents

Varynx is a behavioral risk control engine designed to monitor,
analyze, and respond to behavioral anomalies in autonomous AI agents.

It provides agent registration, behavioral evidence collection,
dynamic trust evaluation, BCSE analysis, adaptive security responses,
and structured audit records.

## Architecture

- Backend: Python and FastAPI
- Frontend: Streamlit
- Containerization: Docker
- Container registry: Amazon ECR
- Compute: Amazon ECS with AWS Fargate
- Load balancing: Application Load Balancer
- Deployment: GitHub Actions with AWS IAM OIDC
- Monitoring: Amazon CloudWatch
- Secrets: AWS Secrets Manager

## Project Structure

```text
Varynx-Behavioral-Risk-Engine/
├── varynx/
│   ├── api/
│   ├── engine/
│   ├── aws/
│   └── evaluation/
├── dashboard_streamlit/
│   ├── app.py
│   ├── api_client.py
│   ├── styles.py
│   └── pages/
├── dashboard/
├── deploy/
│   ├── ecs-backend-task-definition.json
│   └── ecs-frontend-task-definition.json
├── docker/
├── tests/
├── scenarios/
├── Dockerfile
├── buildspec.yml
├── pyproject.toml
└── README.md
```

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run Backend

```powershell
$env:VARYNX_API_KEY="local-development-key"
$env:VARYNX_REQUIRE_API_KEY="true"
uvicorn varynx.api.app:app --host 127.0.0.1 --port 8000
```

API documentation:

http://127.0.0.1:8000/api/v1/docs

## Run Streamlit Dashboard

Open another terminal:

```powershell
pip install streamlit requests
$env:VARYNX_API_URL="http://127.0.0.1:8000/api/v1"
$env:VARYNX_API_KEY="local-development-key"
streamlit run dashboard_streamlit/app.py
```

Dashboard:

http://localhost:8501

## AWS Deployment

Varynx uses separate ECS Fargate services for the FastAPI
backend and Streamlit frontend.

1. Build backend and frontend Docker images.
2. Push both images to Amazon ECR.
3. Register updated ECS task definitions.
4. Deploy the backend and frontend ECS services.
5. Route public HTTPS traffic through an Application Load Balancer.
6. Store API credentials in AWS Secrets Manager.
7. Monitor service health and container logs through CloudWatch.

GitHub Actions authenticates to AWS using IAM OpenID Connect.
No long-lived AWS access keys should be stored in GitHub.

Required GitHub configuration:

- Repository variable: AWS_REGION
- Repository variable: ECS_CLUSTER
- Repository variable: ECS_BACKEND_SERVICE
- Repository variable: ECS_FRONTEND_SERVICE
- Repository secret: AWS_ROLE_ARN

The IAM role must permit ECR image publishing and ECS task
definition registration and service deployment.

## Testing

```powershell
pytest tests/ -q
```

## Security Notes

- Do not commit API keys, AWS credentials, or database passwords.
- Require API-key authentication for publicly exposed backend APIs.
- Restrict network access to backend services.
- Use HTTPS for public endpoints.
- Keep AWS task execution and application task roles separate.
- Use persistent storage for production state.
- Verify actual AWS integration separately from local or mocked tests.

## Research Integrity

Varynx is a research implementation of behavior-aware runtime
security for autonomous AI agents. Detection metrics, thresholds,
and security claims must be supported by reproducible experiments.
Local-mode adapters and simulated scenarios must not be represented
as verified live AWS enforcement.
