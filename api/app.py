
"""FastAPI Application and Middleware.

Entry point for the Varynx REST API. Registers all routers, middleware,
exception handlers, health endpoints, and application lifecycle hooks.

Satisfies: REQ-016
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from varynx.api.middleware import (
    AuthMiddleware,
    CorrelationIDMiddleware,
    RateLimitMiddleware,
)

from varynx.api.routes import (
    agents,
    audit,
    bcse,
    evaluate,
    events,
    health,
    leases,
    sessions,
)

from varynx.config import VarynxConfig
from varynx.engine.pipeline import VarynxPipeline


logger = logging.getLogger(__name__)

# Active Varynx pipeline instance.
_pipeline: VarynxPipeline | None = None


def get_pipeline() -> VarynxPipeline:
    """Return the active VarynxPipeline instance."""

    global _pipeline

    if _pipeline is None:
        _pipeline = VarynxPipeline()

    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and clean up application resources."""

    global _pipeline

    logger.info("Starting Varynx API server")

    try:
        _pipeline = VarynxPipeline()
        logger.info("Varynx pipeline initialized successfully")
    except Exception:
        logger.exception("Failed to initialize Varynx pipeline")
        raise

    yield

    logger.info("Shutting down Varynx API server")
    _pipeline = None


def create_app(config: VarynxConfig | None = None) -> FastAPI:
    """Create and configure the Varynx FastAPI application."""

    if config is None:
        config = VarynxConfig()

    # Production authentication validation.
    if config.require_api_key and not config.api_key:
        raise ValueError(
            "VARYNX_REQUIRE_API_KEY is enabled, but VARYNX_API_KEY "
            "is not configured."
        )

    app = FastAPI(
        title="Varynx Behavioral Risk Control Engine",
        description=(
            "Cloud-native behavioral risk control engine "
            "for autonomous AI agents. "
            "Satisfies REQ-001 through REQ-027."
        ),
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # -------------------------------------------------
    # CORS CONFIGURATION
    # -------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------
    # CUSTOM MIDDLEWARE
    # -------------------------------------------------

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=1000,
    )

    app.add_middleware(
        AuthMiddleware,
        api_key=config.api_key,
        exempt_paths={
            "/health",
            "/health/",
            "/api/v1/health",
            "/api/v1/health/",
        },
    )

    app.add_middleware(CorrelationIDMiddleware)

    # -------------------------------------------------
    # ROOT HEALTH CHECK
    # -------------------------------------------------

    @app.get(
        "/health",
        include_in_schema=False,
    )
    async def load_balancer_health():
        """
        Lightweight health endpoint for AWS ALB.

        Does not access the database, initialize the pipeline,
        or require API-key authentication.

        Expected response: HTTP 200.
        """

        return {
            "status": "ok",
            "service": "varynx-backend",
        }

    # -------------------------------------------------
    # API ROUTERS
    # -------------------------------------------------

    API_PREFIX = "/api/v1"

    app.include_router(
        events.router,
        prefix=API_PREFIX,
        tags=["Events"],
    )

    app.include_router(
        agents.router,
        prefix=API_PREFIX,
        tags=["Agents"],
    )

    app.include_router(
        sessions.router,
        prefix=API_PREFIX,
        tags=["Sessions"],
    )

    app.include_router(
        leases.router,
        prefix=API_PREFIX,
        tags=["Leases"],
    )

    app.include_router(
        bcse.router,
        prefix=API_PREFIX,
        tags=["BCSE"],
    )

    app.include_router(
        audit.router,
        prefix=API_PREFIX,
        tags=["Audit"],
    )

    app.include_router(
        evaluate.router,
        prefix=API_PREFIX,
        tags=["Evaluation"],
    )

    app.include_router(
        health.router,
        prefix=API_PREFIX,
        tags=["Health"],
    )

    # -------------------------------------------------
    # GLOBAL EXCEPTION HANDLER
    # -------------------------------------------------

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:

        logger.error(
            "Unhandled exception on %s: %s",
            request.url.path,
            exc,
            exc_info=True,
        )

        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal error occurred.",
                "request_id": str(uuid.uuid4()),
            },
        )

    logger.info("Varynx FastAPI application configured successfully")

    return app


# -------------------------------------------------
# APPLICATION ENTRY POINT
# -------------------------------------------------

app = create_app()
