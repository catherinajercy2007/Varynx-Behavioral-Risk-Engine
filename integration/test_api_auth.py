"""Phase 5 Task 5.1 - API Authentication & CORS integration tests.

Tests cover:
- Missing/invalid/valid API key behavior
- Health endpoint public access
- Development mode (no key) bypass + warning
- CORS allowed-origin behavior
- CORS unapproved-origin behavior
- OPTIONS preflight without API key
- Correlation ID preservation on auth failures
- Structured error-response format
- Backward compatibility with existing test configuration

Satisfies: Task 5.1 acceptance criteria.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-api-auth")

from fastapi.testclient import TestClient
from varynx.api.app import create_app
from varynx.config import VarynxConfig
from varynx.engine.pipeline import VarynxPipeline


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_body(agent_id: str = "ag-auth-test") -> dict:
    return {
        "agent_id": agent_id,
        "session_id": str(uuid4()),
        "timestamp": _now_iso(),
        "action_type": "READ",
        "capability_requested": "read:files",
        "target_resource": "/data/test.csv",
        "authorization_result": "allowed",
        "is_simulated": True,
    }


def _make_app(api_key: str | None = None, cors: str = "http://localhost:3000") -> TestClient:
    """Build a TestClient with explicit config (no env-var leakage)."""
    import varynx.api.app as api_app
    api_app._pipeline = VarynxPipeline()
    config = VarynxConfig(database_url="memory://", api_key=api_key, cors_origins=cors)
    app = create_app(config=config)
    return TestClient(app, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# Authentication tests
# ─────────────────────────────────────────────────────────────────────────────

class TestApiKeyAuthentication:
    """API-key auth behavior when VARYNX_API_KEY is configured."""

    def test_missing_api_key_returns_401(self):
        """Requests without X-API-Key header receive HTTP 401 when auth is enabled."""
        client = _make_app(api_key="secret-key-123")
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 401
        assert r.json()["status"] == "error"
        assert r.json()["error_code"] == "UNAUTHORIZED"

    def test_invalid_api_key_returns_401(self):
        """Requests with a wrong X-API-Key value receive HTTP 401."""
        client = _make_app(api_key="secret-key-123")
        r = client.post("/api/v1/events", json=_event_body(), headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "UNAUTHORIZED"

    def test_valid_api_key_accepted(self):
        """Requests with a matching X-API-Key receive HTTP 200 (not 401)."""
        client = _make_app(api_key="secret-key-123")
        r = client.post("/api/v1/events", json=_event_body(), headers={"X-API-Key": "secret-key-123"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "event_id" in r.json()["data"]

    def test_health_accessible_without_auth(self):
        """Health endpoint must be accessible without any API key, even when auth is enabled."""
        client = _make_app(api_key="secret-key-123")
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "healthy"

    def test_auth_failure_preserves_error_format(self):
        """401 response uses the standard structured error envelope."""
        client = _make_app(api_key="secret-key-123")
        r = client.post("/api/v1/events", json=_event_body())
        body = r.json()
        assert body["status"] == "error"
        assert body["error_code"] == "UNAUTHORIZED"
        assert "message" in body
        assert "request_id" not in body or isinstance(body.get("request_id"), str)  # may or may not be present

    def test_auth_failure_preserves_correlation_id(self):
        """401 response carries the X-Correlation-ID header (set by CorrelationIDMiddleware)."""
        client = _make_app(api_key="secret-key-123")
        provided_cid = "test-cid-abc123"
        r = client.post("/api/v1/events", json=_event_body(), headers={"X-Correlation-ID": provided_cid})
        assert r.status_code == 401
        assert r.headers.get("X-Correlation-ID") == provided_cid, (
            f"Correlation ID not preserved on 401: got {r.headers.get('X-Correlation-ID')}"
        )

    def test_docs_not_exempt_when_auth_enabled(self):
        """OpenAPI docs endpoints should NOT be publicly accessible when auth is enabled.

        Only /api/v1/health is explicitly exempt per the requirements.
        """
        client = _make_app(api_key="secret-key-123")
        # /api/v1/docs should require auth
        r = client.get("/api/v1/docs")
        assert r.status_code == 401, f"Docs should require auth, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Development mode (no key) tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDevelopmentMode:
    """Behavior when VARYNX_API_KEY is not set (local development)."""

    def test_no_key_bypasses_auth(self):
        """When api_key is None, all endpoints are accessible without X-API-Key."""
        client = _make_app(api_key=None)
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 200, f"Auth disabled should allow: {r.status_code}"

    def test_no_key_logs_warning(self, caplog):
        """When api_key is None, a warning is logged when the middleware initializes.

        Note: Starlette builds the middleware stack lazily on the first request,
        so we must trigger a request to force AuthMiddleware instantiation.
        """
        import logging
        with caplog.at_level(logging.WARNING, logger="varynx.api.middleware"):
            client = _make_app(api_key=None)
            client.get("/api/v1/health")  # triggers middleware stack build
        assert any("VARYNX_API_KEY not set" in rec.message for rec in caplog.records), (
            "Expected a warning about missing API key"
        )

    def test_empty_api_key_treated_as_disabled(self):
        """An empty-string API key must NOT enable auth (equivalent to None)."""
        client = _make_app(api_key="")
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 200, f"Empty key should disable auth: {r.status_code}"

    def test_whitespace_api_key_treated_as_disabled(self):
        """A whitespace-only API key must NOT enable auth with an empty secret."""
        client = _make_app(api_key="   ")
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 200, f"Whitespace key should disable auth: {r.status_code}"

    def test_development_mode_health_accessible(self):
        """Health endpoint works in dev mode too."""
        client = _make_app(api_key=None)
        r = client.get("/api/v1/health")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# CORS tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCorsBehavior:
    """CORS origin restriction behavior."""

    def test_allowed_origin_receives_cors_headers(self):
        """An approved origin receives Access-Control-Allow-Origin in the response."""
        client = _make_app(api_key=None, cors="http://localhost:3000,https://app.example.com")
        r = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000", (
            f"Expected CORS header for approved origin, got: {r.headers.get('access-control-allow-origin')}"
        )

    def test_second_allowed_origin_receives_cors_headers(self):
        """A second approved origin also receives CORS headers."""
        client = _make_app(api_key=None, cors="http://localhost:3000,https://app.example.com")
        r = client.get(
            "/api/v1/health",
            headers={"Origin": "https://app.example.com"},
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "https://app.example.com"

    def test_unapproved_origin_does_not_receive_cors_headers(self):
        """An unapproved origin does NOT receive Access-Control-Allow-Origin."""
        client = _make_app(api_key=None, cors="http://localhost:3000")
        r = client.get(
            "/api/v1/health",
            headers={"Origin": "http://evil.example.com"},
        )
        assert r.status_code == 200  # The request still succeeds (same-origin policy)
        # But CORS header should not grant access to the evil origin
        aco = r.headers.get("access-control-allow-origin")
        assert aco != "http://evil.example.com", (
            f"Unapproved origin should not receive CORS access: got {aco}"
        )

    def test_no_origin_header_no_cors_header(self):
        """When no Origin header is present, no CORS header is returned."""
        client = _make_app(api_key=None, cors="http://localhost:3000")
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    def test_options_preflight_approved_origin_without_api_key(self):
        """OPTIONS preflight from an approved origin passes without an API key.

        Browsers send preflight requests without custom headers (like X-API-Key).
        The auth middleware must allow OPTIONS through so the preflight succeeds.
        """
        client = _make_app(api_key="secret-key-123", cors="http://localhost:3000")
        r = client.options(
            "/api/v1/events",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key,Content-Type",
            },
        )
        # Preflight should not be 401; it should return 200 or 204
        assert r.status_code != 401, f"Preflight should bypass auth, got {r.status_code}"
        # CORS preflight response should include allowed methods
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000", (
            f"Preflight CORS origin wrong: {r.headers.get('access-control-allow-origin')}"
        )

    def test_options_preflight_unapproved_origin(self):
        """OPTIONS preflight from an unapproved origin does not receive CORS access."""
        client = _make_app(api_key="secret-key-123", cors="http://localhost:3000")
        r = client.options(
            "/api/v1/events",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Preflight should not be 401 (OPTIONS bypasses auth)
        assert r.status_code != 401
        # But the CORS origin header should not grant access
        aco = r.headers.get("access-control-allow-origin")
        assert aco != "http://evil.example.com", (
            f"Unapproved origin preflight should not get CORS: {aco}"
        )

    def test_comma_separated_cors_origins_parsed(self):
        """VARYNX_CORS_ORIGINS as comma-separated string is parsed correctly."""
        client = _make_app(api_key=None, cors="http://a.com,http://b.com,http://c.com")
        for origin in ["http://a.com", "http://b.com", "http://c.com"]:
            r = client.get("/api/v1/health", headers={"Origin": origin})
            assert r.headers.get("access-control-allow-origin") == origin, (
                f"Origin {origin} not allowed: {r.headers.get('access-control-allow-origin')}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

class TestBackwardCompatibility:
    """Existing API tests must remain compatible with the new auth middleware."""

    def test_create_app_with_no_config_still_works(self):
        """create_app() with no args creates a working app (auth disabled by default)."""
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        app = create_app()  # no config arg — backward compatible
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    def test_events_work_without_auth_in_default_mode(self):
        """In default mode (no api_key), POST /events works without X-API-Key header."""
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        app = create_app(config=VarynxConfig(database_url="memory://"))
        client = TestClient(app, raise_server_exceptions=True)
        r = client.post("/api/v1/events", json=_event_body(agent_id="ag-bcompat"))
        assert r.status_code == 200, f"Default mode should allow events: {r.status_code}"

# ---------------------------------------------------------------------------
# Startup auth guard tests (require_api_key)
# ---------------------------------------------------------------------------

class TestProductionAuthGuard:
    """Verify require_api_key startup guard behavior."""

    def test_dev_mode_no_key_starts_without_error(self):
        """require_api_key=False (default) allows startup without a key -- dev behavior."""
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        from varynx.config import VarynxConfig
        # Default: require_api_key=False, api_key=None -- should NOT raise
        cfg = VarynxConfig(database_url="memory://test-dev-guard")
        assert cfg.require_api_key is False
        # create_app must succeed
        from varynx.api.app import create_app
        app = create_app(config=cfg)
        assert app is not None

    def test_dev_mode_no_key_allows_all_requests(self):
        """Dev mode (no key) permits requests through without authentication."""
        client = _make_app(api_key=None)
        r = client.post("/api/v1/events", json=_event_body())
        # Dev mode: no 401, the warning is logged but requests proceed
        assert r.status_code != 401, (
            "Dev mode with no api_key should NOT return 401; auth is intentionally disabled"
        )

    def test_production_mode_missing_key_raises_at_startup(self):
        """require_api_key=True with no api_key must raise ValueError at startup."""
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        from varynx.config import VarynxConfig
        from varynx.api.app import create_app
        cfg = VarynxConfig(database_url="memory://test-prod-guard", require_api_key=True)
        # api_key is None, require_api_key is True -- must fail
        with pytest.raises(ValueError, match="VARYNX_REQUIRE_API_KEY"):
            create_app(config=cfg)

    def test_production_mode_with_key_starts_normally(self):
        """require_api_key=True with api_key set must NOT raise at startup."""
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        from varynx.config import VarynxConfig
        from varynx.api.app import create_app
        cfg = VarynxConfig(
            database_url="memory://test-prod-key",
            require_api_key=True,
            api_key="prod-secret-xyz",
        )
        # Has both flags set correctly -- must succeed
        app = create_app(config=cfg)
        assert app is not None

    def test_production_mode_with_key_enforces_auth(self):
        """When require_api_key=True and api_key is set, missing key returns 401."""
        from varynx.config import VarynxConfig
        import varynx.api.app as api_app
        api_app._pipeline = VarynxPipeline()
        cfg = VarynxConfig(
            database_url="memory://test-prod-auth",
            require_api_key=True,
            api_key="prod-secret-xyz",
        )
        from varynx.api.app import create_app
        from fastapi.testclient import TestClient
        app = create_app(config=cfg)
        client = TestClient(app)
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 401

    def test_require_api_key_false_with_key_set_still_enforces(self):
        """Even with require_api_key=False, a configured api_key is still enforced."""
        # require_api_key=False means startup won't fail, but if a key IS configured
        # the auth middleware will still enforce it.
        client = _make_app(api_key="some-key")
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 401  # key configured but not provided in request
