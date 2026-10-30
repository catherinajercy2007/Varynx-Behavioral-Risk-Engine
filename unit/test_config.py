"""Configuration system tests (T1.4).

Satisfies: T1.4 acceptance criteria
"""
from __future__ import annotations

import pytest

from varynx.config import ConfigurationError, EvidenceConfig, TrustConfig, load_config


def test_valid_config_loads(monkeypatch):
    monkeypatch.setenv("VARYNX_DATABASE_URL", "postgresql://user:pass@localhost/varynx")
    cfg = load_config()
    assert cfg.database_url == "postgresql://user:pass@localhost/varynx"


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("VARYNX_DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="CONFIGURATION_UNAVAILABLE"):
        load_config()


def test_default_trust_values():
    cfg = TrustConfig()
    assert cfg.initial_score == 0.7
    assert cfg.sensitivity == 1.0
    assert cfg.temporal_decay_rate == 0.01
    assert cfg.threshold_high == 0.85
    assert cfg.threshold_elevated == 0.65
    assert cfg.threshold_guarded == 0.40
    assert cfg.threshold_low == 0.20


def test_default_evidence_values():
    cfg = EvidenceConfig()
    assert cfg.authz_denial_threshold == 3
    assert cfg.authz_denial_window_seconds == 300.0
    assert cfg.resource_spread_threshold == 10
    assert cfg.capability_spread_threshold == 5


def test_default_policy_yaml_has_enough_rules():
    import yaml
    with open("config/default_policy.yaml") as f:
        policy = yaml.safe_load(f)
    assert len(policy["rules"]) >= 7
    # Must have a default rule
    assert any("default" in r for r in policy["rules"])


def test_no_hard_coded_thresholds_in_config_module():
    """All thresholds come from Field(default=...), not bare literals."""
    import inspect

    from varynx import config as cfg_module
    source = inspect.getsource(cfg_module)
    # Spot-check: sensitivity, temporal_decay_rate, thresholds appear in Field() calls
    assert "Field(" in source
    # The word "hard-coded" guard: no raw magic numbers assigned to class attrs outside Field
    # (best-effort check — not exhaustive)
    assert "sensitivity: float = 1.0" not in source
    assert "temporal_decay_rate: float = 0.01" not in source
