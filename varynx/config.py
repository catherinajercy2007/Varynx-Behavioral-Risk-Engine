"""Varynx configuration system.

All behavioral thresholds and policy parameters are externally configurable
via environment variables (VARYNX_ prefix) and never hard-coded.

Satisfies: REQ-020, REQ-027 (NFR-REP-001)
"""
from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Raised when Varynx configuration is absent or invalid."""


class TrustConfig(BaseSettings):
    """Trust scoring parameters.

    All values require empirical calibration (REQ-005.3).
    """

    model_config = SettingsConfigDict(env_prefix="VARYNX_TRUST__", extra="ignore")

    initial_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Initial trust score for new agents. Requires empirical calibration.",
    )
    sensitivity: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Evidence sensitivity multiplier. Requires empirical calibration (REQ-005.3).",
    )
    temporal_decay_rate: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Per-hour trust decay rate. Requires empirical calibration (REQ-005.3).",
    )
    # TrustLevel thresholds — all require empirical calibration
    threshold_high: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum score for HIGH level. Requires empirical calibration.",
    )
    threshold_elevated: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum score for ELEVATED level. Requires empirical calibration.",
    )
    threshold_guarded: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Minimum score for GUARDED level. Requires empirical calibration.",
    )
    threshold_low: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Minimum score for LOW level. Requires empirical calibration.",
    )
    # CRITICAL range is [0.0, threshold_low)


class EvidenceConfig(BaseSettings):
    """Evidence engine and detector parameters.

    All thresholds require empirical calibration.
    """

    model_config = SettingsConfigDict(env_prefix="VARYNX_EVIDENCE__", extra="ignore")

    correlation_window_seconds: float = Field(
        default=300.0,
        ge=1.0,
        description="Time window for evidence correlation (REQ-004.2 default 300s).",
    )
    authz_denial_threshold: int = Field(
        default=3,
        ge=1,
        description="Authorization denial count to trigger AUTHORIZATION_BYPASS_ATTEMPT (REQ-004.2).",
    )
    authz_denial_window_seconds: float = Field(
        default=300.0,
        ge=1.0,
        description="Time window for authorization denial counting (REQ-004.2).",
    )
    resource_spread_threshold: int = Field(
        default=10,
        ge=1,
        description="Distinct resource domains to trigger RESOURCE_ANOMALY (REQ-004.3).",
    )
    resource_spread_window_seconds: float = Field(
        default=600.0,
        ge=1.0,
        description="Time window for resource spread counting (REQ-004.3).",
    )
    capability_spread_threshold: int = Field(
        default=5,
        ge=1,
        description="Distinct capability types to trigger CAPABILITY_SPREAD_THRESHOLD_EXCEEDED (REQ-006.4).",
    )
    action_frequency_threshold: int = Field(
        default=100,
        ge=1,
        description="Actions per minute to trigger ACTION_FREQUENCY anomaly.",
    )
    action_frequency_window_seconds: float = Field(
        default=60.0,
        ge=1.0,
        description="Time window for action frequency counting.",
    )
    # Detector ablation toggles (REQ-025 ablation support)
    enable_capability_escalation: bool = True
    enable_resource_anomaly: bool = True
    enable_action_frequency: bool = True
    enable_authorization_bypass: bool = True
    enable_context_deviation: bool = True
    enable_temporal_anomaly: bool = True


class PolicyConfig(BaseSettings):
    """Adaptive response engine parameters.

    All thresholds require empirical calibration.
    """

    model_config = SettingsConfigDict(env_prefix="VARYNX_POLICY__", extra="ignore")

    policy_file: str = Field(
        default="config/default_policy.yaml",
        description="Path to the policy YAML file (REQ-020, REQ-009.2).",
    )
    escalation_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Score below which degrading trajectory triggers RESTRICT (REQ-011.2).",
    )
    critical_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Score below which degrading trajectory triggers SUSPEND (REQ-011.3).",
    )
    de_escalation_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Score above which improving trajectory suppresses escalation (REQ-011.4).",
    )


class BCSeConfig(BaseSettings):
    """BCSE evaluation parameters.

    Phase 1 uses stub behavior. Phase 2 activates full evaluation.
    """

    model_config = SettingsConfigDict(env_prefix="VARYNX_BCSE__", extra="ignore")

    min_history_events: int = Field(
        default=10,
        ge=1,
        description="Minimum historical events for BCSE projection. Below this: LOW_HISTORY_WARNING (REQ-007.5).",
    )
    evaluation_timeout_seconds: float = Field(
        default=2.0,
        ge=0.1,
        description="BCSE evaluation timeout. Target: ≤2s under nominal load (REQ-007.7).",
    )


class EvaluationConfig(BaseSettings):
    """Evaluation framework parameters.

    Satisfies: REQ-015, REQ-025, REQ-026
    """

    model_config = SettingsConfigDict(env_prefix="VARYNX_EVAL__", extra="ignore")

    min_runs: int = Field(
        default=5,
        ge=1,
        description="Minimum evaluation runs. Fewer marks report INCOMPLETE (REQ-026.6).",
    )
    scenarios_dir: str = Field(
        default="scenarios/",
        description="Directory containing YAML scenario files.",
    )
    random_seed: int = Field(
        default=42,
        description="Random seed for reproducible evaluation (REQ-015, REQ-025).",
    )


class VarynxConfig(BaseSettings):
    """Top-level Varynx configuration.

    Loaded from environment variables with VARYNX_ prefix.
    Satisfies: REQ-020, REQ-027 (NFR-REP-001)
    """

    model_config = SettingsConfigDict(
        env_prefix="VARYNX_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    database_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL. Required. (REQ-017)",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for event replay cache.",
    )
    dry_run_mode: bool = Field(
        default=False,
        description="When True, enforcement layer logs actions without applying them (REQ-022.4).",
    )
    max_event_body_bytes: int = Field(
        default=1_048_576,  # 1 MB
        ge=1024,
        description="Maximum HTTP body size for event ingestion (REQ-016.8).",
    )
    timestamp_future_tolerance_seconds: int = Field(
        default=60,
        ge=0,
        description="Max seconds into future for event timestamp (REQ-001.3).",
    )
    timestamp_past_tolerance_seconds: int = Field(
        default=300,
        ge=0,
        description="Max seconds into past for event timestamp (REQ-001.3).",
    )

    api_key: str | None = Field(
        default=None,
        description=(
            "API key for authenticating REST API requests. When set, requests must "
            "include a matching X-API-Key header. When None (local dev), auth is "
            "bypassed with a logged warning. Satisfies REQ-016.3."
        ),
    )

    cors_origins: str = Field(
        default="http://localhost:3000",
        description=(
            "Allowed CORS origins as a comma-separated string. Parsed from "
            "VARYNX_CORS_ORIGINS. Default permits the local dashboard. "
            "Use cors_origin_list property for the parsed list. Satisfies REQ-016.2."
        ),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return cors_origins as a list of stripped origin strings."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    trust: TrustConfig = Field(default_factory=TrustConfig)
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    bcse: BCSeConfig = Field(default_factory=BCSeConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    @field_validator("database_url")
    @classmethod
    def database_url_must_be_set(cls, v: str | None) -> str | None:
        """Validated at load_config() time; allow None here for sub-model construction."""
        return v



def load_config(**overrides: Any) -> VarynxConfig:
    """Load and validate the Varynx configuration.

    Reads VARYNX_ environment variables. Raises ConfigurationError on failure.

    Raises:
        ConfigurationError: With message containing 'CONFIGURATION_UNAVAILABLE' if
            database_url is absent, or 'CONFIGURATION_INVALID: <fields>' on
            schema validation failure.
    """
    from pydantic import ValidationError

    try:
        config = VarynxConfig(**overrides)
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) for e in exc.errors() if e.get("loc"))
        raise ConfigurationError(f"CONFIGURATION_INVALID: {fields}") from exc

    if not config.database_url:
        raise ConfigurationError("CONFIGURATION_UNAVAILABLE: database_url is required")

    return config
