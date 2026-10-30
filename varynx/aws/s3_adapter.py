from __future__ import annotations
"""S3 Adapter -- artifact storage for evaluation reports, audit exports, datasets.

LOCAL_MODE: writes to local output/ directory.
AWS_MODE: uploads to configured S3 bucket with unique key names.

Security constraints:
  - Never creates buckets or changes bucket policies.
  - Never makes objects public.
  - Never deletes existing objects.
  - Uses unique timestamped keys to avoid silent overwrites.
  - Preserves local copy even when S3 upload fails.

Required IAM permissions for S3 uploads:
  s3:PutObject on arn:aws:s3:::<bucket>/<prefix>*
  s3:GetObject on arn:aws:s3:::<bucket>/<prefix>* (for downloads)
  s3:ListBucket on arn:aws:s3:::<bucket>
"""
import json, logging, os, pathlib
from datetime import UTC, datetime
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
LOCAL_OUTPUT = pathlib.Path("output")


class S3Adapter(AWSAdapter):
    """S3 storage adapter for Varynx evaluation and audit artifacts.

    Upload workflow:
    1. Always write local copy first (preserves artifact on S3 failure).
    2. If S3 is configured and enabled, upload local copy to S3.
    3. Return the S3 URI on success, or the local path on failure/disabled.
    """

    service_name = "s3"

    def __init__(self) -> None:
        super().__init__()
        self._bucket = (os.environ.get("VARYNX_S3_BUCKET") or
                         os.environ.get("VARYNX_AWS__S3_BUCKET"))
        self._prefix = (os.environ.get("VARYNX_AWS__S3_PREFIX","varynx/"))
        self._enabled = (os.environ.get("VARYNX_AWS__S3_ENABLED","").lower() == "true")
        if not self.is_local and self._bucket: self._status = AdapterStatus.CONFIGURED

    def _local_write(self, filename: str, content: str) -> pathlib.Path:
        """Always write local copy. Returns the local path."""
        LOCAL_OUTPUT.mkdir(parents=True, exist_ok=True)
        path = LOCAL_OUTPUT / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _s3_key(self, filename: str) -> str:
        """Build an S3 object key with prefix."""
        return self._prefix.rstrip("/") + "/" + filename

    def upload_artifact(self, content: str, key_prefix: str,
                         extension: str = "json") -> dict:
        """Upload a text artifact. Local copy is ALWAYS written first.

        Returns:
            {"local_path": str, "s3_uri": str | None, "uploaded": bool}
        """
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = key_prefix + "_" + ts + "." + extension
        local_path = self._local_write(filename, content)
        logger.info("Artifact written locally: %s", local_path)
        if self.is_local or not self._bucket or not self._enabled:
            return {"local_path":str(local_path),"s3_uri":None,"uploaded":False}
        try:
            client = self._get_client("s3")
            key = self._s3_key(filename)
            client.put_object(Bucket=self._bucket, Key=key, Body=content.encode(),
                               ContentType="application/json")
            self._status = AdapterStatus.CONNECTED
            s3_uri = "s3://" + self._bucket + "/" + key
            logger.info("Artifact uploaded to S3: %s", s3_uri)
            return {"local_path":str(local_path),"s3_uri":s3_uri,"uploaded":True}
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc)
            logger.error("S3 upload failed for %s: %s -- local copy preserved at %s",
                          filename, exc, local_path)
            return {"local_path":str(local_path),"s3_uri":None,"uploaded":False,
                    "error":str(exc)}

    def upload_audit_log(self, records: list, key_prefix: str = "audit") -> str:
        """Upload audit records as JSONL. Returns local path or S3 URI."""
        content = "\n".join(json.dumps(r, default=str) for r in records)
        result = self.upload_artifact(content, key_prefix, "jsonl")
        return result.get("s3_uri") or result["local_path"]

    def upload_evaluation_report(self, report: dict, scenario_name: str = "eval") -> dict:
        """Upload an evaluation report dict as JSON.

        Connected to ScenarioRunner output. Preserves local copy on S3 failure.
        """
        content = json.dumps(report, indent=2, default=str)
        return self.upload_artifact(content, "report_" + scenario_name, "json")

    def upload_evaluation_dataset(self, dataset: list[dict], name: str = "dataset") -> dict:
        """Upload a scenario dataset as JSONL for reproducibility artifacts."""
        content = "\n".join(json.dumps(r, default=str) for r in dataset)
        return self.upload_artifact(content, "dataset_" + name, "jsonl")

    def download_object(self, key: str) -> bytes:
        """Download an S3 object. Falls back to local file read in LOCAL_MODE."""
        if self.is_local:
            p = LOCAL_OUTPUT / key
            if p.exists(): return p.read_bytes()
            raise FileNotFoundError("LOCAL: " + key + " not found in " + str(LOCAL_OUTPUT))
        if not self._bucket:
            raise ValueError("S3_BUCKET not configured")
        client = self._get_client("s3")
        return client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def health_check(self) -> dict:
        b = super().health_check()
        b["bucket"] = self._bucket or "(not configured)"
        b["prefix"] = self._prefix
        b["s3_enabled"] = self._enabled
        return b