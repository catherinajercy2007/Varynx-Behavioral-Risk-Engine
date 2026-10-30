"""FastAPI Application and Middleware.

Entry point for the Varynx REST API. Registers all routers, middleware,
exception handlers, and startup/shutdown lifecycle hooks.

Satisfies: REQ-016
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from varynx.api.middleware import AuthMiddleware, CorrelationIDMiddleware, RateLimitMiddleware
from varynx.api.routes import agents, audit, bcse, evaluate, events, health, leases, sessions
from varynx.config import VarynxConfig
from varynx.engine.pipeline import VarynxPipeline

logger = logging.getLogger(__name__)

# Module-level pipeline instance (production: inject via DI)
_pipeline: VarynxPipeline | None = None


def get_pipeline() -> VarynxPipeline:
    """Dependency: returns the active VarynxPipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VarynxPipeline()
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and clean up resources."""
    global _pipeline
    logger.info("Starting Varynx API server")
    _pipeline = VarynxPipeline()
    yield
    logger.info("Shutting down Varynx API server")


def create_app(config: VarynxConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Optional VarynxConfig. When None, reads from VARYNX_ env vars
                (backward-compatible with existing callers that pass no args).

    Satisfies: REQ-016
    """
    if config is None:
        config = VarynxConfig()

    # Production auth guard (REQ-016.3): when require_api_key=True the application
    # must not start without a key.  This is an explicit opt-in so local development
    # (where api_key is intentionally absent) continues to work unchanged.
    if config.require_api_key and not config.api_key:
        raise ValueError(
            "VARYNX_REQUIRE_API_KEY is True but VARYNX_API_KEY is not set. "
            "Set VARYNX_API_KEY before starting the application, or set "
            "VARYNX_REQUIRE_API_KEY=false to allow unauthenticated local access."
        )

    app = FastAPI(
        title="Varynx Behavioral Risk Control Engine",
        description=(
            "Cloud-native behavioral risk control engine for autonomous AI agents. "
            "Satisfies REQ-001 through REQ-027."
        ),
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware — origins from config (VARYNX_CORS_ORIGINS).
    # Replaces the previous allow_origins=["*"] wildcard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order: last added = outermost)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=1000)
    app.add_middleware(
        AuthMiddleware,
        api_key=config.api_key,
        exempt_paths={"/api/v1/health"},
    )
    app.add_middleware(CorrelationIDMiddleware)

    # Register routers
    API_PREFIX = "/api/v1"
    app.include_router(events.router, prefix=API_PREFIX, tags=["Events"])
    app.include_router(agents.router, prefix=API_PREFIX, tags=["Agents"])
    app.include_router(sessions.router, prefix=API_PREFIX, tags=["Sessions"])
    app.include_router(leases.router, prefix=API_PREFIX, tags=["Leases"])
    app.include_router(bcse.router, prefix=API_PREFIX, tags=["BCSE"])
    app.include_router(audit.router, prefix=API_PREFIX, tags=["Audit"])
    app.include_router(evaluate.router, prefix=API_PREFIX, tags=["Evaluation"])
    app.include_router(health.router, prefix=API_PREFIX, tags=["Health"])

    # Global exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal error occurred.",
                "request_id": str(uuid.uuid4()),
            },
        )

    return app


app = create_app()
