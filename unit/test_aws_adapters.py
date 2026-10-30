"""Tests for AWS service adapters in LOCAL_MODE."""
from __future__ import annotations
import os
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://test-aws")
# Ensure no AWS credentials in test environment
for k in ["AWS_REGION","AWS_DEFAULT_REGION","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY"]:
    os.environ.pop(k, None)

from varynx.aws.base import AdapterStatus
from varynx.aws.s3_adapter import S3Adapter
from varynx.aws.cloudwatch_adapter import CloudWatchAdapter
from varynx.aws.secrets_manager_adapter import SecretsManagerAdapter
from varynx.aws.rds_adapter import RDSAdapter
from varynx.aws.kms_adapter import KMSAdapter
from varynx.aws.lambda_adapter import LambdaAdapter
from varynx.aws.cloudtrail_adapter import CloudTrailAdapter
from varynx.aws.ecs_adapter import ECSAdapter
from varynx.aws.ecr_adapter import ECRAdapter
from varynx.aws.iam_adapter import IAMAdapter
from varynx.aws.ec2_adapter import EC2Adapter
from varynx.aws.registry import AWSServiceRegistry

class TestAdapterLocalMode:
    def test_all_adapters_are_local_without_credentials(self):
        for cls in [S3Adapter, CloudWatchAdapter, SecretsManagerAdapter, RDSAdapter,
                    KMSAdapter, LambdaAdapter, CloudTrailAdapter, ECSAdapter,
                    ECRAdapter, IAMAdapter, EC2Adapter]:
            a = cls()
            assert a.is_local, f"{cls.__name__} should be LOCAL_MODE without credentials"

    def test_all_adapters_have_health_check(self):
        for cls in [S3Adapter, CloudWatchAdapter, SecretsManagerAdapter]:
            a = cls()
            hc = a.health_check()
            assert "service" in hc
            assert "status" in hc

class TestS3LocalMode:
    def test_upload_writes_local_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        a = S3Adapter()
        path = a.upload_audit_log([{"event": "test"}])
        import pathlib
        assert pathlib.Path(path).exists()

    def test_upload_creates_jsonl(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        a = S3Adapter()
        path = a.upload_audit_log([{"a":1},{"b":2}])
        content = open(path).read()
        assert content.count("{") == 2

class TestSecretsManagerLocalMode:
    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "my-value")
        a = SecretsManagerAdapter()
        assert a.get_secret("MY_SECRET") == "my-value"

    def test_missing_returns_none(self):
        a = SecretsManagerAdapter()
        assert a.get_secret("NONEXISTENT_SECRET_XYZ_123") is None

class TestRDSLocalMode:
    def test_returns_memory_url(self):
        a = RDSAdapter()
        url = a.get_database_url()
        assert url == "memory://varynx"

class TestKMSLocalMode:
    def test_encrypt_decrypt_roundtrip(self):
        a = KMSAdapter()
        original = b"hello varynx"
        ciphertext = a.encrypt(original)
        assert ciphertext != original
        decrypted = a.decrypt(ciphertext)
        assert decrypted == original

    def test_encrypt_is_not_plaintext(self):
        a = KMSAdapter()
        ct = a.encrypt(b"secret data")
        assert b"secret data" not in ct

class TestLambdaLocalMode:
    def test_returns_mock_for_unknown_function(self):
        a = LambdaAdapter()
        r = a.invoke("unknown-function", {"key": "val"})
        assert "LOCAL_MOCK" in str(r) or "mode" in r

    def test_local_handler_invoked(self):
        a = LambdaAdapter()
        a.register_local_handler("test-fn", lambda p: {"result": p["x"] * 2})
        r = a.invoke("test-fn", {"x": 21})
        assert r["result"] == 42

class TestCloudTrailLocalMode:
    def test_trail_status_local(self):
        a = CloudTrailAdapter()
        s = a.get_trail_status()
        assert s.get("logging_enabled") is True

    def test_lookup_events_local_returns_empty_list(self):
        """LOCAL_MODE returns [] -- no fabricated events (per spec constraint)."""
        a = CloudTrailAdapter()
        events = a.lookup_events()
        assert isinstance(events, list)
        # LOCAL_MODE correctly returns empty; real events need AWS CloudTrail
        assert events == []

class TestECSLocalMode:
    def test_service_status_local(self):
        a = ECSAdapter()
        s = a.get_service_status()
        assert s["mode"] == "LOCAL_MODE"
        assert s["running_count"] == 1

class TestECRLocalMode:
    def test_image_metadata_local(self):
        a = ECRAdapter()
        img = a.get_latest_image()
        assert img["mode"] == "LOCAL_MODE"
        assert "digest" in img

class TestIAMLocalMode:
    def test_caller_identity_local(self):
        a = IAMAdapter()
        identity = a.get_caller_identity()
        assert identity["mode"] == "LOCAL_MODE"
        assert "aws_caller" in identity  # field renamed for identity separation clarity
        assert identity["aws_caller"] == "local-developer"
    def test_identity_separation_note_present(self):
        """Verify identity separation note is documented in local mode."""
        a = IAMAdapter()
        identity = a.get_caller_identity()
        assert "varynx_note" in identity

class TestEC2LocalMode:
    def test_metadata_local(self):
        a = EC2Adapter()
        meta = a.get_instance_metadata()
        assert "hostname" in meta

class TestAWSRegistry:
    def test_registry_creates_all_12_services(self):
        r = AWSServiceRegistry()
        assert len(r.all_adapters) == 12

    def test_status_report_has_all_services(self):
        r = AWSServiceRegistry()
        report = r.get_status_report()
        assert report["total"] == 12
        assert "services" in report

    def test_all_local_without_credentials(self):
        r = AWSServiceRegistry()
        # All real adapters should be LOCAL_MODE (no AWS credentials in test)
        assert r.get_status_report()["local_mode_count"] == 11  # github_oidc is None

    def test_emit_security_metric_does_not_raise(self):
        r = AWSServiceRegistry()
        r.emit_security_metric("test.metric", 1.0)  # Should log locally, not raise

    def test_upload_audit_export(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = AWSServiceRegistry()
        result = r.upload_audit_export([{"record": "test"}])
        import pathlib
        assert pathlib.Path(result).exists()