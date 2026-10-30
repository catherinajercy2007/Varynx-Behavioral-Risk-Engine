from __future__ import annotations
import logging, os
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)

class IAMAdapter(AWSAdapter):
    """AWS IAM adapter -- verifies caller identity and documents required permissions.

    IDENTITY SEPARATION:
    - AWS caller identity (this adapter): the IAM user/role Varynx uses to call AWS APIs.
      Verified via sts:GetCallerIdentity.
    - Varynx agent identity (registry.py): the autonomous AI agent being monitored.
      Tracked via agent_id in IdentitySessionRegistry.
    These are completely separate. A valid AWS identity does NOT grant Varynx agent
    authorization. Agent authorization follows the existing policy engine.

    Does NOT create IAM users, roles, or policies.
    Does NOT use AWS identity as a Varynx authorization decision.
    """

    service_name = "iam"

    REQUIRED_PERMISSIONS = {
        "s3": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
        "cloudwatch": ["cloudwatch:PutMetricData", "logs:PutLogEvents"],
        "cloudtrail": ["cloudtrail:GetTrailStatus", "cloudtrail:LookupEvents"],
        "sts": ["sts:GetCallerIdentity"],
    }

    def __init__(self) -> None:
        super().__init__()
        self._verify = os.environ.get("VARYNX_AWS__IAM_VERIFY_IDENTITY","").lower()=="true"
        self._cached: dict | None = None
        if not self.is_local: self._status = AdapterStatus.CONFIGURED

    def get_caller_identity(self, force_refresh: bool = False) -> dict:
        """Return AWS caller identity. Cached after first successful call.

        LOCAL_MODE: returns local-developer identity without AWS calls.
        AWS_MODE: calls sts:GetCallerIdentity.
        IMPORTANT: This is the identity Varynx uses to access AWS, NOT the
        identity of the autonomous agent being monitored by Varynx.
        """
        if self.is_local:
            return {"mode": "LOCAL_MODE",
                    "aws_caller": "local-developer",
                    "varynx_note": "Separate from Varynx agent identity",
                    "api_key_present": bool(os.environ.get("VARYNX_API_KEY")),
                    "account": "local",
                    "arn": "arn:aws:iam::local:user/developer"}
        if self._cached and not force_refresh:
            return self._cached
        try:
            c = self._get_client("sts")
            r = c.get_caller_identity()
            self._status = AdapterStatus.CONNECTED
            self._cached = {"aws_caller_account": r.get("Account"),
                             "aws_caller_user_id": r.get("UserId"),
                             "aws_caller_arn": r.get("Arn"),
                             "varynx_note": "Separate from Varynx agent identity"}
            logger.info("AWS caller verified: %s", r.get("Arn"))
            return self._cached
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc)
            logger.error("IAM get_caller_identity failed: %s", exc)
            return {"error": str(exc), "aws_caller_arn": None}

    def verify_varynx_permissions(self) -> dict:
        """Diagnose which AWS permissions are available to Varynx.

        Returns required permissions list. Does NOT check agent permissions.
        NOTE: iam:SimulatePrincipalPolicy not used to avoid requiring extra permissions.
        """
        if self.is_local:
            return {"mode": "LOCAL_MODE", "status": "NOT_VERIFIED",
                    "required_permissions": self.REQUIRED_PERMISSIONS,
                    "note": "Grant these permissions to the caller ARN in AWS."}
        identity = self.get_caller_identity()
        if "error" in identity:
            return {"error": identity["error"], "status": "IDENTITY_ERROR"}
        return {"aws_caller_arn": identity.get("aws_caller_arn"),
                "required_permissions": self.REQUIRED_PERMISSIONS,
                "status": "MANUAL_VERIFICATION_REQUIRED",
                "note": "Grant required_permissions to the caller ARN."}

    def health_check(self) -> dict:
        b = super().health_check()
        b["aws_identity"] = self.get_caller_identity()
        b["identity_separation"] = "AWS caller != Varynx agent_id (see registry.py)"
        return b