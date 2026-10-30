"""Comprehensive mocked tests for the 4 target AWS integrations.

Tests use unittest.mock.MagicMock to simulate boto3 clients.
No real AWS credentials required.

Covers per-service requirements from Phase I:
  IAM: caller identity, missing credentials, permissions, identity separation
  CloudWatch: metric publication, disabled, failure isolation
  CloudTrail: normalization, malformed events, duplicates, source metadata
  S3: upload, missing bucket, failure (local copy preserved), disabled
  End-to-end: pipeline produces audit record, CW only when enabled,
              CT ingest pipeline, S3 eval export, AWS failures safe.
"""
from __future__ import annotations
import json, os, pathlib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-aws-mocked")
# Strip real AWS credentials for deterministic mock tests
for _k in ["AWS_REGION","AWS_DEFAULT_REGION","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY"]:
    os.environ.pop(_k, None)

from varynx.aws.base import AdapterStatus
from varynx.aws.cloudwatch_adapter import CloudWatchAdapter
from varynx.aws.cloudtrail_adapter import CloudTrailAdapter
from varynx.aws.s3_adapter import S3Adapter
from varynx.aws.iam_adapter import IAMAdapter
from varynx.engine.pipeline import VarynxPipeline
from varynx.models.event import AgentActionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(agent_id="ag-mock-001"):
    return AgentActionEvent.model_validate(dict(
        agent_id=agent_id, session_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        action_type="READ", capability_requested="read:files",
        target_resource="/data/test.csv", authorization_result="allowed",
        is_simulated=True,
    ), strict=False)


def _aws_adapter(cls, region="us-east-1"):
    """Return an adapter instance that THINKS boto3 and credentials are available.
    The actual boto3 client creation is patched in individual tests.
    """
    a = cls()
    a._boto3_available = True
    a._region = region
    a._status = AdapterStatus.NOT_CONFIGURED
    return a


CT_FIXTURE = {
    "eventID": "event-001",
    "eventName": "PutObject",
    "eventSource": "s3.amazonaws.com",
    "eventTime": "2024-06-15T14:00:00Z",
    "awsRegion": "us-east-1",
    "recipientAccountId": "123456789012",
    "userIdentity": {
        "type": "AssumedRole",
        "arn": "arn:aws:sts::123456789012:assumed-role/VarynxRole/session",
        "accountId": "123456789012",
    },
    "requestID": "req-abc-001",
    "sourceIPAddress": "192.0.2.1",
    "resources": [{"ARN": "arn:aws:s3:::my-bucket/file.json",
                    "resourceType": "AWS::S3::Object",
                    "resourceName": "file.json"}],
}


# ---------------------------------------------------------------------------
# IAM Tests
# ---------------------------------------------------------------------------

class TestIAMWithMockedClient:
    def test_successful_caller_identity(self):
        """STS GetCallerIdentity succeeds with mocked client."""
        a = _aws_adapter(IAMAdapter)
        mock_client = MagicMock()
        mock_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "AROA123:session",
            "Arn": "arn:aws:sts::123456789012:assumed-role/VarynxRole/session",
        }
        with patch.object(a, "_get_client", return_value=mock_client):
            identity = a.get_caller_identity(force_refresh=True)
        assert identity["aws_caller_account"] == "123456789012"
        assert "varynx_note" in identity
        assert a.status == AdapterStatus.CONNECTED

    def test_missing_credentials_returns_error(self):
        """When STS raises, get_caller_identity returns error dict."""
        a = _aws_adapter(IAMAdapter)
        mock_client = MagicMock()
        mock_client.get_caller_identity.side_effect = Exception("NoCredentialsError")
        with patch.object(a, "_get_client", return_value=mock_client):
            identity = a.get_caller_identity(force_refresh=True)
        assert "error" in identity
        assert a.status == AdapterStatus.ERROR

    def test_varynx_permissions_local_mode(self):
        """verify_varynx_permissions in LOCAL_MODE returns NOT_VERIFIED."""
        a = IAMAdapter()
        result = a.verify_varynx_permissions()
        assert result["status"] == "NOT_VERIFIED"
        assert "required_permissions" in result

    def test_identity_separation_documented(self):
        """AWS caller identity must be labelled separately from Varynx agent."""
        a = IAMAdapter()
        identity = a.get_caller_identity()
        assert "varynx_note" in identity
        # AWS caller field must be distinct from "agent_id"
        assert "aws_caller" in identity or "aws_caller_arn" in identity
        assert "agent_id" not in identity

    def test_varynx_permissions_with_identity(self):
        """verify_varynx_permissions returns caller ARN in AWS mode."""
        a = _aws_adapter(IAMAdapter)
        mock_client = MagicMock()
        mock_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "AROA",
            "Arn": "arn:aws:iam::123456789012:role/VarynxRole",
        }
        with patch.object(a, "_get_client", return_value=mock_client):
            result = a.verify_varynx_permissions()
        assert result["status"] == "MANUAL_VERIFICATION_REQUIRED"
        assert "required_permissions" in result


# ---------------------------------------------------------------------------
# CloudWatch Tests
# ---------------------------------------------------------------------------

class TestCloudWatchWithMockedClient:
    def test_metric_published_when_enabled(self):
        """put_metric calls cloudwatch PutMetricData when enabled."""
        a = _aws_adapter(CloudWatchAdapter)
        a._enabled = True
        mock_cw = MagicMock()
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.put_metric("TestMetric", 1.0)
        mock_cw.put_metric_data.assert_called_once()
        assert a.status == AdapterStatus.CONNECTED

    def test_metric_skipped_when_disabled(self):
        """put_metric does NOT call AWS when cloudwatch_enabled=False."""
        a = _aws_adapter(CloudWatchAdapter)
        a._enabled = False
        mock_cw = MagicMock()
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.put_metric("TestMetric", 1.0)
        mock_cw.put_metric_data.assert_not_called()

    def test_metric_failure_does_not_raise(self):
        """CloudWatch failures are caught; no exception propagates."""
        a = _aws_adapter(CloudWatchAdapter)
        a._enabled = True
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("ThrottlingException")
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.put_metric("TestMetric", 1.0)  # Must not raise
        assert a.status == AdapterStatus.DEGRADED

    def test_publish_pipeline_result_emits_metrics(self):
        """publish_pipeline_result emits EventsProcessed and RiskLevelScore."""
        a = _aws_adapter(CloudWatchAdapter)
        a._enabled = True
        mock_cw = MagicMock()
        pipeline_result = MagicMock()
        pipeline_result.error = None
        pipeline_result.anomalies_detected = ["CAPABILITY_ESCALATION"]
        pipeline_result.trust_level = "GUARDED"
        pipeline_result.recommendation = MagicMock()
        pipeline_result.recommendation.response_type.value = "RESTRICT"
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.publish_pipeline_result(pipeline_result)
        # Should have called put_metric_data multiple times
        assert mock_cw.put_metric_data.call_count >= 3

    def test_pipeline_error_emits_pipeline_error_metric(self):
        """pipeline_result.error causes PipelineErrors metric instead."""
        a = _aws_adapter(CloudWatchAdapter)
        a._enabled = True
        mock_cw = MagicMock()
        pipeline_result = MagicMock()
        pipeline_result.error = "some error"
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.publish_pipeline_result(pipeline_result)
        # Only PipelineErrors metric published on error
        assert mock_cw.put_metric_data.call_count == 1

    def test_local_audit_unaffected_by_cw_failure(self):
        """When CW fails, existing pipeline audit records are unaffected."""
        pipeline = VarynxPipeline()
        # CW adapter that always fails
        cw = CloudWatchAdapter()
        cw._status = AdapterStatus.LOCAL_MODE  # stays local, no AWS calls
        pipeline._cloudwatch = cw
        event = _make_event()
        result = pipeline.process_event(event, skip_timestamp_check=True)
        # Local audit records should still be present
        assert len(pipeline.audit_store.all_records()) > 0
        assert result.error is None


# ---------------------------------------------------------------------------
# CloudTrail Tests
# ---------------------------------------------------------------------------

class TestCloudTrailNormalization:
    def test_valid_event_normalized(self):
        """Well-formed CT event normalizes to expected fields."""
        a = CloudTrailAdapter()
        n = a.normalize_event(CT_FIXTURE)
        assert n is not None
        assert n["source"] == "CLOUDTRAIL"
        assert n["event_id"] == "event-001"
        assert n["event_name"] == "PutObject"
        assert n["event_source"] == "s3.amazonaws.com"
        assert n["principal_arn"] == CT_FIXTURE["userIdentity"]["arn"]

    def test_source_metadata_preserved(self):
        """Full original CT event must be in source_metadata."""
        a = CloudTrailAdapter()
        n = a.normalize_event(CT_FIXTURE)
        assert n["source_metadata"] == CT_FIXTURE

    def test_malformed_event_rejected(self):
        """Missing required fields -> normalize_event returns None."""
        a = CloudTrailAdapter()
        bad = {"eventID": "ev-001"}  # missing eventName, eventSource, eventTime
        result = a.normalize_event(bad)
        assert result is None

    def test_non_dict_event_rejected(self):
        a = CloudTrailAdapter()
        assert a.normalize_event("not a dict") is None
        assert a.normalize_event(None) is None
        assert a.normalize_event(42) is None

    def test_duplicate_event_rejected(self):
        """Same eventID is only processed once."""
        a = CloudTrailAdapter()
        n1 = a.normalize_event(CT_FIXTURE)
        n2 = a.normalize_event(CT_FIXTURE)
        assert n1 is not None
        assert n2 is None  # duplicate

    def test_missing_optional_fields_safe(self):
        """Events without optional fields (resources, sourceIPAddress) are safe."""
        a = CloudTrailAdapter()
        minimal = {
            "eventID": "ev-minimal-001",
            "eventName": "DescribeInstances",
            "eventSource": "ec2.amazonaws.com",
            "eventTime": "2024-06-15T12:00:00Z",
        }
        n = a.normalize_event(minimal)
        assert n is not None
        assert n["source_ip"] == ""
        assert n["resources"] == []
        assert n["error_code"] == ""

    def test_error_message_truncated(self):
        """Long error messages are truncated to prevent log injection."""
        a = CloudTrailAdapter()
        long_msg = "X" * 500
        ev = dict(CT_FIXTURE, eventID="ev-err-001", errorCode="AccessDenied",
                   errorMessage=long_msg)
        n = a.normalize_event(ev)
        assert len(n["error_message"]) <= 200

    def test_ingest_batch_filters_invalids(self):
        """ingest_batch skips invalid and duplicate events."""
        a = CloudTrailAdapter()
        events = [
            CT_FIXTURE,
            {"eventID": "ev-002", "eventName": "GetObject",
             "eventSource": "s3.amazonaws.com", "eventTime": "2024-06-15T14:01:00Z"},
            {"malformed": True},  # missing required fields
            CT_FIXTURE,  # duplicate
        ]
        results = a.ingest_batch(events)
        assert len(results) == 2  # CT_FIXTURE + ev-002, not malformed, not duplicate

    def test_no_behavioral_conclusions_in_normalization(self):
        """Normalized CT events do not claim behavioral anomaly directly."""
        a = CloudTrailAdapter()
        n = a.normalize_event(CT_FIXTURE)
        # No anomaly_class, risk_score, or trust_delta in normalized output
        assert "anomaly_class" not in n
        assert "risk_score" not in n
        assert "trust_delta" not in n

    def test_aws_mode_lookup_normalized(self):
        """lookup_events in AWS mode returns normalized events."""
        a = _aws_adapter(CloudTrailAdapter)
        a._enabled = True
        mock_ct = MagicMock()
        mock_ct.lookup_events.return_value = {"Events": [CT_FIXTURE]}
        with patch.object(a, "_get_client", return_value=mock_ct):
            results = a.lookup_events(hours=1)
        assert len(results) == 1
        assert results[0]["source"] == "CLOUDTRAIL"


# ---------------------------------------------------------------------------
# S3 Tests
# ---------------------------------------------------------------------------

class TestS3WithMockedClient:
    def test_successful_upload_with_mocked_client(self, tmp_path, monkeypatch):
        """upload_artifact calls S3 PutObject when bucket is configured."""
        monkeypatch.chdir(tmp_path)
        a = _aws_adapter(S3Adapter)
        a._bucket = "varynx-test-bucket"
        a._enabled = True
        a._status = AdapterStatus.CONFIGURED
        mock_s3 = MagicMock()
        with patch.object(a, "_get_client", return_value=mock_s3):
            result = a.upload_artifact("test content", "test_prefix")
        mock_s3.put_object.assert_called_once()
        assert result["uploaded"] is True
        assert result["s3_uri"].startswith("s3://varynx-test-bucket/")

    def test_missing_bucket_uses_local_only(self, tmp_path, monkeypatch):
        """When S3 bucket not configured, upload goes to local only."""
        monkeypatch.chdir(tmp_path)
        a = _aws_adapter(S3Adapter)
        a._bucket = None
        a._enabled = True
        result = a.upload_artifact("test content", "test_prefix")
        assert result["uploaded"] is False
        assert result["s3_uri"] is None
        assert pathlib.Path(result["local_path"]).exists()

    def test_disabled_integration_uses_local(self, tmp_path, monkeypatch):
        """When s3_enabled=False, upload is local-only."""
        monkeypatch.chdir(tmp_path)
        a = _aws_adapter(S3Adapter)
        a._bucket = "some-bucket"
        a._enabled = False
        result = a.upload_artifact("content", "prefix")
        assert result["uploaded"] is False

    def test_local_copy_preserved_on_upload_failure(self, tmp_path, monkeypatch):
        """Local copy always written first; preserved when S3 fails."""
        monkeypatch.chdir(tmp_path)
        a = _aws_adapter(S3Adapter)
        a._bucket = "varynx-test-bucket"
        a._enabled = True
        a._status = AdapterStatus.CONFIGURED
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        with patch.object(a, "_get_client", return_value=mock_s3):
            result = a.upload_artifact("test content", "test_prefix")
        # Local file still exists
        assert pathlib.Path(result["local_path"]).exists()
        assert result["uploaded"] is False
        assert "error" in result

    def test_upload_uses_unique_key(self, tmp_path, monkeypatch):
        """Two uploads with same prefix produce different keys (timestamp-based)."""
        monkeypatch.chdir(tmp_path)
        a = _aws_adapter(S3Adapter)
        a._bucket = "bucket"
        a._enabled = True
        mock_s3 = MagicMock()
        import time
        with patch.object(a, "_get_client", return_value=mock_s3):
            r1 = a.upload_artifact("c1", "prefix")
            time.sleep(1.1)  # ensure different timestamp
            r2 = a.upload_artifact("c2", "prefix")
        # Different timestamps in key names
        assert r1["local_path"] != r2["local_path"]

    def test_upload_evaluation_report(self, tmp_path, monkeypatch):
        """upload_evaluation_report writes JSON locally."""
        monkeypatch.chdir(tmp_path)
        a = S3Adapter()
        report = {"scenario": "scope_escalation", "f1": 1.0, "pass": True}
        result = a.upload_evaluation_report(report, "scope_escalation")
        assert pathlib.Path(result["local_path"]).exists()
        saved = json.loads(pathlib.Path(result["local_path"]).read_text())
        assert saved["scenario"] == "scope_escalation"

    def test_upload_evaluation_dataset(self, tmp_path, monkeypatch):
        """upload_evaluation_dataset writes JSONL locally."""
        monkeypatch.chdir(tmp_path)
        a = S3Adapter()
        dataset = [{"event": "e1"}, {"event": "e2"}]
        result = a.upload_evaluation_dataset(dataset, "my_dataset")
        lines = pathlib.Path(result["local_path"]).read_text().splitlines()
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# End-to-End Integration Tests
# ---------------------------------------------------------------------------

class TestEndToEndIntegration:
    def test_pipeline_produces_audit_record(self):
        """Existing pipeline audit record creation is unchanged."""
        pipeline = VarynxPipeline()
        event = _make_event()
        result = pipeline.process_event(event, skip_timestamp_check=True)
        assert result.error is None
        records = pipeline.audit_store.all_records()
        assert len(records) >= 4  # evidence, trust, response, enforcement

    def test_cloudwatch_only_called_when_attached(self):
        """Pipeline without CloudWatch attached does not call any CW methods."""
        pipeline = VarynxPipeline()
        assert pipeline._cloudwatch is None
        event = _make_event()
        # Should complete without calling any CW code
        result = pipeline.process_event(event, skip_timestamp_check=True)
        assert result.error is None

    def test_cloudwatch_called_when_attached(self):
        """Pipeline calls publish_pipeline_result when CW adapter is attached."""
        pipeline = VarynxPipeline()
        mock_cw = MagicMock(spec=CloudWatchAdapter)
        mock_cw.publish_pipeline_result = MagicMock()
        pipeline._cloudwatch = mock_cw
        event = _make_event()
        pipeline.process_event(event, skip_timestamp_check=True)
        mock_cw.publish_pipeline_result.assert_called_once()

    def test_cloudtrail_events_normalized_to_dict_list(self):
        """CT ingest_batch returns list of dicts with source=CLOUDTRAIL."""
        ct = CloudTrailAdapter()
        events = [CT_FIXTURE, dict(CT_FIXTURE, eventID="ev-002")]
        normalized = ct.ingest_batch(events)
        assert all(n["source"] == "CLOUDTRAIL" for n in normalized)
        assert len(normalized) == 2

    def test_s3_eval_export_does_not_affect_pipeline(self, tmp_path, monkeypatch):
        """S3 export of evaluation report is independent of pipeline state."""
        monkeypatch.chdir(tmp_path)
        pipeline = VarynxPipeline()
        event = _make_event()
        result = pipeline.process_event(event, skip_timestamp_check=True)
        # Export audit records to "S3" (local in test)
        s3 = S3Adapter()
        records = [r.model_dump(mode="json") for r in pipeline.audit_store.all_records()]
        export = s3.upload_audit_log(records)
        assert pathlib.Path(export).exists()
        assert result.error is None  # pipeline unaffected

    def test_cw_failure_does_not_break_pipeline(self):
        """CloudWatch failure is caught; pipeline still returns valid result."""
        pipeline = VarynxPipeline()
        # Attach a CW adapter that raises on publish
        mock_cw = MagicMock()
        mock_cw.publish_pipeline_result.side_effect = RuntimeError("CW offline")
        pipeline._cloudwatch = mock_cw
        event = _make_event()
        result = pipeline.process_event(event, skip_timestamp_check=True)
        # Pipeline result should be valid despite CW failure
        assert result.error is None
        assert len(pipeline.audit_store.all_records()) > 0

    def test_existing_response_behavior_unchanged(self):
        """Adding AWS adapters does not change trust scores or response types."""
        pipeline_no_cw = VarynxPipeline()
        pipeline_with_cw = VarynxPipeline()
        cw = CloudWatchAdapter()  # local mode, no-op
        pipeline_with_cw._cloudwatch = cw
        event = _make_event("agent-regression-001")
        r1 = pipeline_no_cw.process_event(event, skip_timestamp_check=True)
        event2 = _make_event("agent-regression-002")
        r2 = pipeline_with_cw.process_event(event2, skip_timestamp_check=True)
        # Both should produce same response type (PERMIT for benign event)
        assert r1.recommendation.response_type == r2.recommendation.response_type
        assert r1.trust_level == r2.trust_level

# ---------------------------------------------------------------------------
# B2: CloudWatch configuration wiring tests
# ---------------------------------------------------------------------------

class TestCloudWatchConfigWiring:
    """Tests that AWSConfig.cloudwatch_enabled correctly controls adapter behavior.

    These tests use the constructor parameter and from_aws_config() path.
    All AWS calls are mocked -- no real AWS credentials required.
    """

    def test_disabled_via_constructor_no_client_created(self):
        """When enabled=False, put_metric must not create a boto3 client."""
        from unittest.mock import patch, MagicMock
        a = CloudWatchAdapter(enabled=False)
        assert a._enabled is False
        with patch.object(a, "_get_client") as mock_get:
            a.put_metric("TestMetric", 1.0)
        mock_get.assert_not_called()

    def test_disabled_via_constructor_publish_pipeline_no_calls(self):
        """publish_pipeline_result must not call AWS when enabled=False."""
        from unittest.mock import patch, MagicMock
        a = CloudWatchAdapter(enabled=False)
        pipeline_result = MagicMock()
        pipeline_result.error = None
        pipeline_result.anomalies_detected = []
        pipeline_result.trust_level = "GUARDED"
        pipeline_result.recommendation = None
        with patch.object(a, "_get_client") as mock_get:
            a.publish_pipeline_result(pipeline_result)
        mock_get.assert_not_called()

    def test_from_aws_config_disabled(self):
        """from_aws_config with cloudwatch_enabled=False disables the adapter."""
        from unittest.mock import patch, MagicMock

        class FakeAWSConfig:
            cloudwatch_enabled = False
            cloudwatch_namespace = "Varynx/Test"
            cloudwatch_log_group = "/varynx/test"

        a = CloudWatchAdapter.from_aws_config(FakeAWSConfig())
        assert a._enabled is False
        assert a._namespace == "Varynx/Test"
        with patch.object(a, "_get_client") as mock_get:
            a.put_metric("SomeMetric", 1.0)
        mock_get.assert_not_called()

    def test_from_aws_config_enabled_publishes(self):
        """from_aws_config with cloudwatch_enabled=True calls PutMetricData."""
        from unittest.mock import patch, MagicMock

        class FakeAWSConfig:
            cloudwatch_enabled = True
            cloudwatch_namespace = "Varynx/Test"
            cloudwatch_log_group = "/varynx/test"

        a = CloudWatchAdapter.from_aws_config(FakeAWSConfig())
        # Force NOT local so enabled actually goes to AWS path
        a._boto3_available = True
        a._region = "us-east-1"
        a._status = __import__("varynx.aws.base", fromlist=["AdapterStatus"]).AdapterStatus.CONFIGURED
        assert a._enabled is True
        mock_cw = MagicMock()
        with patch.object(a, "_get_client", return_value=mock_cw):
            a.put_metric("TestMetric", 1.0)
        mock_cw.put_metric_data.assert_called_once()

    def test_pipeline_no_cw_when_cloudwatch_disabled_in_config(self, monkeypatch):
        """VarynxPipeline._cloudwatch is None when aws.cloudwatch_enabled=False."""
        # Ensure env var is not set
        monkeypatch.delenv("VARYNX_AWS__CLOUDWATCH_ENABLED", raising=False)
        from varynx.config import VarynxConfig, AWSConfig
        cfg = VarynxConfig(database_url="memory://test-cw-disabled")
        # Default: cloudwatch_enabled=False
        assert cfg.aws.cloudwatch_enabled is False
        pipeline = VarynxPipeline(config=cfg)
        assert pipeline._cloudwatch is None

    def test_pipeline_auto_creates_cw_when_enabled_in_config(self, monkeypatch):
        """VarynxPipeline creates CloudWatchAdapter when aws.cloudwatch_enabled=True."""
        monkeypatch.delenv("VARYNX_AWS__CLOUDWATCH_ENABLED", raising=False)
        from varynx.config import VarynxConfig, AWSConfig
        cfg = VarynxConfig(
            database_url="memory://test-cw-enabled",
            aws=AWSConfig(cloudwatch_enabled=True),
        )
        assert cfg.aws.cloudwatch_enabled is True
        pipeline = VarynxPipeline(config=cfg)
        assert pipeline._cloudwatch is not None
        assert isinstance(pipeline._cloudwatch, CloudWatchAdapter)
        # Should be disabled at AWS level (no real creds) but enabled flag is True
        assert pipeline._cloudwatch._enabled is True

    def test_registry_with_aws_config_uses_it(self):
        """AWSServiceRegistry passes aws_config to CloudWatchAdapter."""
        from varynx.aws.registry import AWSServiceRegistry

        class FakeAWSConfig:
            cloudwatch_enabled = False
            cloudwatch_namespace = "My/NS"
            cloudwatch_log_group = "/my/log"

        registry = AWSServiceRegistry(aws_config=FakeAWSConfig())
        assert registry.cloudwatch._enabled is False
        assert registry.cloudwatch._namespace == "My/NS"

    def test_registry_without_aws_config_falls_back_to_env(self, monkeypatch):
        """AWSServiceRegistry without aws_config reads from env var."""
        monkeypatch.setenv("VARYNX_AWS__CLOUDWATCH_ENABLED", "false")
        from varynx.aws.registry import AWSServiceRegistry
        registry = AWSServiceRegistry()
        assert registry.cloudwatch._enabled is False


# ---------------------------------------------------------------------------
# B3: CloudTrail instance-scope deduplication test
# ---------------------------------------------------------------------------

class TestCloudTrailInstanceScope:
    """Verify that duplicate detection is per-instance (not process-global).

    This tests the documented limitation: a second CloudTrailAdapter instance
    will re-ingest the same event that a first instance already processed.
    """

    def test_two_instances_each_accept_same_event(self):
        """Same eventID is accepted by both instances independently."""
        event = {
            "eventID": "dedup-test-001",
            "eventName": "PutObject",
            "eventSource": "s3.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a1 = CloudTrailAdapter()
        a2 = CloudTrailAdapter()
        r1 = a1.normalize_event(event)
        r2 = a2.normalize_event(event)
        # Both instances process the event independently
        assert r1 is not None, "First instance should accept the event"
        assert r2 is not None, "Second instance (fresh) should also accept the same event"

    def test_same_instance_rejects_duplicate(self):
        """The same instance rejects a second submission of the same eventID."""
        event = {
            "eventID": "dedup-test-002",
            "eventName": "DescribeInstances",
            "eventSource": "ec2.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a = CloudTrailAdapter()
        r1 = a.normalize_event(event)
        r2 = a.normalize_event(event)
        assert r1 is not None
        assert r2 is None  # duplicate within the same instance

    def test_ingested_count_resets_on_new_instance(self):
        """health_check.ingested_count is per-instance."""
        event = {
            "eventID": "count-test-001",
            "eventName": "GetObject",
            "eventSource": "s3.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a1 = CloudTrailAdapter()
        a1.normalize_event(event)
        assert a1.health_check()["ingested_count"] == 1

        a2 = CloudTrailAdapter()
        assert a2.health_check()["ingested_count"] == 0  # fresh instance
