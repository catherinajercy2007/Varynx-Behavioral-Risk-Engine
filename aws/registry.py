from __future__ import annotations
import logging
from varynx.aws.ec2_adapter import EC2Adapter
from varynx.aws.ecr_adapter import ECRAdapter
from varynx.aws.ecs_adapter import ECSAdapter
from varynx.aws.cloudtrail_adapter import CloudTrailAdapter
from varynx.aws.cloudwatch_adapter import CloudWatchAdapter
from varynx.aws.iam_adapter import IAMAdapter
from varynx.aws.kms_adapter import KMSAdapter
from varynx.aws.lambda_adapter import LambdaAdapter
from varynx.aws.rds_adapter import RDSAdapter
from varynx.aws.s3_adapter import S3Adapter
from varynx.aws.secrets_manager_adapter import SecretsManagerAdapter
from varynx.aws.github_oidc import get_workflow_yaml
logger = logging.getLogger(__name__)
class AWSServiceRegistry:
    """Central registry for all 12 AWS service adapters."""
    def __init__(self, aws_config=None) -> None:
        self.secrets = SecretsManagerAdapter()
        self.rds = RDSAdapter(secrets_adapter=self.secrets)
        self.s3 = S3Adapter()
        # Use aws_config when provided so the Pydantic-validated flag controls
        # the adapter; fall back to env-var-only construction otherwise.
        if aws_config is not None:
            self.cloudwatch = CloudWatchAdapter.from_aws_config(aws_config)
        else:
            self.cloudwatch = CloudWatchAdapter()
        self.kms = KMSAdapter()
        self.lambda_ = LambdaAdapter()
        self.cloudtrail = CloudTrailAdapter()
        self.ecs = ECSAdapter()
        self.ecr = ECRAdapter()
        self.iam = IAMAdapter()
        self.ec2 = EC2Adapter()
        self._github_oidc_workflow = get_workflow_yaml()
    @property
    def all_adapters(self) -> dict:
        return {"ec2":self.ec2,"s3":self.s3,"iam":self.iam,"lambda":self.lambda_,
                "cloudwatch":self.cloudwatch,"ecs_fargate":self.ecs,"ecr":self.ecr,
                "rds":self.rds,"secrets_manager":self.secrets,"kms":self.kms,
                "cloudtrail":self.cloudtrail,"github_oidc":None}
    def get_status_report(self) -> dict:
        statuses = {}
        for name, adapter in self.all_adapters.items():
            if adapter is None:
                statuses[name] = {"service":name,"status":"CONFIGURED",
                                   "note":"CI/CD only -- see docs/DEPLOYMENT_GUIDE.md"}
            else:
                statuses[name] = adapter.health_check()
        return {"services":statuses,"total":len(statuses),
                "local_mode_count":sum(1 for a in self.all_adapters.values() if a is not None and a.is_local)}
    def emit_security_metric(self, metric: str, value: float = 1.0, dims=None):
        self.cloudwatch.put_metric(metric, value, "Count", dims)
    def upload_audit_export(self, records: list) -> str:
        return self.s3.upload_audit_log(records, key_prefix="varynx-audit")