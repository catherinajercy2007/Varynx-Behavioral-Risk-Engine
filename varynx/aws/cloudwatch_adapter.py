from __future__ import annotations
"""CloudWatch Adapter -- security metrics and log events.

LOCAL_MODE: writes to Python logging.
AWS_MODE: emits to CloudWatch Metrics and CloudWatch Logs.

Publishes security metrics from the Varynx pipeline.
Metric dimensions avoid high-cardinality agent_id values.
Publication failures never disable local audit or the core engine.

Configuration:
    This adapter is controlled by two independent mechanisms that must agree:

    1. The `enabled` constructor parameter (takes precedence when explicitly
       passed, e.g. from `AWSConfig.cloudwatch_enabled` in `VarynxConfig`).
    2. The `VARYNX_AWS__CLOUDWATCH_ENABLED` environment variable (used as a
       fallback when `enabled` is not passed at construction time).

    When BOTH are `False` (default), no CloudWatch clients are created, no
    metrics are published, and no network activity occurs.  The adapter only
    logs locally via Python's `logging` module.

    Use `CloudWatchAdapter.from_aws_config(aws_cfg)` to construct from an
    `AWSConfig` instance rather than relying on env-var fallback.

Local-vs-live: all tests in this file use mocked boto3 clients.
No real AWS calls have been made against a live CloudWatch endpoint.
"""
import logging
import os
from datetime import UTC, datetime

from varynx.aws.base import AWSAdapter, AdapterStatus

logger = logging.getLogger(__name__)

# Safe metric names published by Varynx
METRIC_EVENTS_PROCESSED = "EventsProcessed"
METRIC_RISK_LEVEL = "RiskLevelScore"
METRIC_ANOMALIES_DETECTED = "AnomaliesDetected"
METRIC_RESPONSE_TYPE = "ResponseTypeCount"
METRIC_AUTH_DENIALS = "AuthorizationDenials"
METRIC_PIPELINE_ERRORS = "PipelineErrors"
METRIC_INTEGRATION_FAILURES = "IntegrationFailures"


class CloudWatchAdapter(AWSAdapter):
    """Publishes Varynx security metrics and log events to Amazon CloudWatch.

    AWS identity: uses configured AWS credentials (IAM role / env vars).
    Varynx agent identity: completely separate from AWS credentials.
    Failure isolation: CW failures log locally and do not affect the pipeline.
    Secret safety: never publishes credentials, API keys, or sensitive payloads.
    """

    service_name = "cloudwatch"

    def __init__(
        self,
        namespace: str | None = None,
        log_group: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Construct the CloudWatchAdapter.

        Args:
            namespace: CloudWatch metric namespace.  Falls back to
                `VARYNX_CLOUDWATCH_NAMESPACE` / `VARYNX_AWS__CLOUDWATCH_NAMESPACE`.
            log_group: CloudWatch Logs log-group name.  Falls back to
                `VARYNX_CLOUDWATCH_LOG_GROUP` / `VARYNX_AWS__CLOUDWATCH_LOG_GROUP`.
            enabled: Explicit on/off switch.  When *not* `None` this value takes
                precedence over the `VARYNX_AWS__CLOUDWATCH_ENABLED` env var.
                Pass `enabled=True` to activate publishing; pass `enabled=False`
                to guarantee that no CloudWatch calls are made regardless of the
                environment.  Pass `None` (the default) to fall back to the env var.
        """
        super().__init__()
        self._namespace = (
            namespace
            or os.environ.get("VARYNX_CLOUDWATCH_NAMESPACE")
            or os.environ.get("VARYNX_AWS__CLOUDWATCH_NAMESPACE", "Varynx/SecurityEngine")
        )
        self._log_group = (
            log_group
            or os.environ.get("VARYNX_CLOUDWATCH_LOG_GROUP")
            or os.environ.get("VARYNX_AWS__CLOUDWATCH_LOG_GROUP", "/varynx/security")
        )
        # Resolve enabled flag: explicit parameter wins, then fall back to env var.
        if enabled is not None:
            self._enabled = bool(enabled)
        else:
            self._enabled = (
                os.environ.get("VARYNX_AWS__CLOUDWATCH_ENABLED", "").lower() == "true"
            )
        if not self.is_local:
            self._status = AdapterStatus.CONFIGURED

    @classmethod
    def from_aws_config(cls, aws_config) -> "CloudWatchAdapter":
        """Construct from an `AWSConfig` instance.

        This is the preferred construction path when a `VarynxConfig` object
        is available, because it ensures the Pydantic-validated config flag
        controls the adapter rather than a raw env-var re-read.

        Example::

            cfg = VarynxConfig(database_url="memory://")
            cw = CloudWatchAdapter.from_aws_config(cfg.aws)
        """
        return cls(
            namespace=aws_config.cloudwatch_namespace,
            log_group=aws_config.cloudwatch_log_group,
            enabled=aws_config.cloudwatch_enabled,
        )

    @property
    def is_publishing_enabled(self) -> bool:
        """True only when CloudWatch is reachable AND explicitly enabled."""
        return self._enabled and not self.is_local

    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: list[dict] | None = None,
    ) -> None:
        """Publish a single metric.  Never raises -- logs failures instead.

        When `cloudwatch_enabled=False`:
          * No boto3 client is created.
          * No network call occurs.
          * The call logs at DEBUG level and returns immediately.

        When `cloudwatch_enabled=True` and the adapter is in LOCAL_MODE
        (no AWS credentials / region configured):
          * Logs at INFO level and returns -- same safe no-op behaviour.

        Failure isolation: CloudWatch errors are caught and logged; local
        audit logging and the core engine remain unaffected.
        """
        if not self._enabled:
            logger.debug("CW metric skipped (cloudwatch_enabled=False): %s=%s", name, value)
            return
        if self.is_local:
            logger.info("CW[LOCAL] metric %s=%s %s", name, value, unit)
            return
        try:
            cw = self._get_client("cloudwatch")
            m: dict = {"MetricName": name, "Value": value, "Unit": unit,
                       "Timestamp": datetime.now(UTC)}
            if dimensions:
                m["Dimensions"] = dimensions
            cw.put_metric_data(Namespace=self._namespace, MetricData=[m])
            self._status = AdapterStatus.CONNECTED
        except Exception as exc:
            self._status = AdapterStatus.DEGRADED
            self._error = str(exc)
            logger.error("CW put_metric %s failed: %s", name, exc)

    def publish_pipeline_result(self, result) -> None:
        """Publish security metrics derived from a VarynxPipeline result.

        Safe to call even when CloudWatch is disabled or unavailable.
        Never emits agent_id as a dimension (high-cardinality guard).
        Never emits trust scores or sensitive behavioral details.

        Args:
            result: PipelineResult instance from VarynxPipeline.process_event().
        """
        if not self._enabled:
            logger.debug("CW publish_pipeline_result skipped (cloudwatch_enabled=False)")
            return
        if result.error:
            self.put_metric(METRIC_PIPELINE_ERRORS, 1.0)
            return
        self.put_metric(METRIC_EVENTS_PROCESSED, 1.0)
        if result.anomalies_detected:
            self.put_metric(METRIC_ANOMALIES_DETECTED, float(len(result.anomalies_detected)))
        if result.trust_level:
            level_map = {"CRITICAL": 0, "LOW": 1, "GUARDED": 2, "ELEVATED": 3, "HIGH": 4}
            self.put_metric(METRIC_RISK_LEVEL, float(level_map.get(result.trust_level, -1)))
        if result.recommendation:
            rt = result.recommendation.response_type.value
            self.put_metric(
                METRIC_RESPONSE_TYPE, 1.0,
                dimensions=[{"Name": "ResponseType", "Value": rt}],
            )

    def put_log_event(self, message: str, log_stream: str = "security-events") -> None:
        """Publish a log event to CloudWatch Logs.  Never raises."""
        if not self._enabled:
            logger.debug("CW log_event skipped (cloudwatch_enabled=False)")
            return
        if self.is_local:
            logger.info("CW[LOCAL] log %s: %s", log_stream, message)
            return
        try:
            logs = self._get_client("logs")
            ts = int(datetime.now(UTC).timestamp() * 1000)
            logs.put_log_events(
                logGroupName=self._log_group,
                logStreamName=log_stream,
                logEvents=[{"timestamp": ts, "message": message}],
            )
            self._status = AdapterStatus.CONNECTED
        except Exception as exc:
            self._status = AdapterStatus.DEGRADED
            self._error = str(exc)
            logger.warning("CW put_log_event failed: %s", exc)

    def health_check(self) -> dict:
        b = super().health_check()
        b["namespace"] = self._namespace
        b["publishing_enabled"] = self.is_publishing_enabled
        return b
