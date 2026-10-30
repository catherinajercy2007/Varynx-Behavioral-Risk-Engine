import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\tests\integration\test_api_auth.py')
src = p.read_text(encoding='utf-8')

addition = '''

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
        # require_api_key=False means startup won\'t fail, but if a key IS configured
        # the auth middleware will still enforce it.
        client = _make_app(api_key="some-key")
        r = client.post("/api/v1/events", json=_event_body())
        assert r.status_code == 401  # key configured but not provided in request
'''

new_src = src + addition
p.write_text(new_src, encoding='utf-8')
print(f'Auth guard tests added: {p.stat().st_size} bytes')