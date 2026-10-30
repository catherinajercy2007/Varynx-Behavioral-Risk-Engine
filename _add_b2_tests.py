import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\tests\integration\test_aws_integration.py')
existing = p.read_text(encoding='utf-8')

addition = '''

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
'''

new_content = existing + addition
p.write_text(new_content, encoding='utf-8')
print(f'Added B2 tests: {p.stat().st_size} bytes')