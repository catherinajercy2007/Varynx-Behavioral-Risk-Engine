from __future__ import annotations
"""CloudTrail Adapter -- AWS account activity ingestion.

LOCAL_MODE: returns mock trail status and fixture events.
AWS_MODE: queries CloudTrail for real trail status and events.

ARCHITECTURAL CONSTRAINT: CloudTrail records AWS account API activity.
It does NOT capture all autonomous agent internal actions.
Do not describe CloudTrail as a complete agent-activity monitor.

Normalization translates CloudTrail records to Varynx audit schema fields
while preserving the original CloudTrail context in source_metadata.
Normalized events are SUPPLEMENTARY evidence, not primary behavioral signals.
"""
import hashlib, json, logging, os
from datetime import UTC, datetime, timedelta
from typing import Any
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)

# Required field present in a valid CloudTrail event
_REQUIRED_FIELDS = {"eventID", "eventName", "eventSource", "eventTime"}


class CloudTrailAdapter(AWSAdapter):
    """Ingest and normalize AWS CloudTrail events for Varynx audit analysis.

    Identity distinction:
    - AWS caller identity (who made the API call) = userIdentity.arn
    - Varynx agent_id = agent registered in Varynx registry, separate concept
    - CloudTrail events annotate with source=CLOUDTRAIL to distinguish them
      from events generated internally by the Varynx pipeline.

    Scope and limitations:
    -----------------------
    * **Instance-scoped deduplication only**: `_ingested_ids` is a per-instance
      in-memory set.  Duplicate suppression is only active within the lifetime of a
      single `CloudTrailAdapter` instance.  A second instance, a restarted process,
      or a new Lambda invocation will re-ingest the same events.  If cross-process
      deduplication is required, store processed `eventID` values externally.

    * **Single AWS account and region**: `LookupEvents` returns events visible to
      the caller's IAM identity in the configured region.  It does **not** cover
      other accounts in an AWS Organization.  For organization-wide coverage, use
      CloudTrail Lake with an organization data store and query via Athena.

    * **Management events only by default**: `LookupEvents` returns management
      events (control-plane API calls).  S3 data events, Lambda invocations, and
      other high-volume data events require a separate trail configuration and are
      **not** returned by this adapter.

    * **10-day lookback limit**: `LookupEvents` returns events from the past 90
      days only (reduced to 10 days for high-volume accounts).  For longer retention,
      a CloudTrail trail must deliver logs to S3.

    * **Not a complete agent-activity monitor**: CloudTrail records AWS API calls
      made by the AWS credentials used by an autonomous agent.  It does **not**
      capture in-process agent behavior, non-AWS network calls, file-system
      operations, or any action that does not result in an AWS API call.

    * **Supplementary evidence only**: Normalized CloudTrail events are labelled
      `source=CLOUDTRAIL` and must never be treated as primary Varynx behavioral
      evidence without additional correlation.

    * Does not create or modify CloudTrail trails.
    * Does not assume a trail, S3 destination, or event data store exists.
    """

    service_name = "cloudtrail"

    def __init__(self) -> None:
        super().__init__()
        self._trail = (os.environ.get("VARYNX_CLOUDTRAIL_NAME") or
                        os.environ.get("VARYNX_AWS__CLOUDTRAIL_TRAIL_NAME"))
        self._ingested_ids: set[str] = set()  # duplicate-event guard
        self._enabled = (os.environ.get("VARYNX_AWS__CLOUDTRAIL_ENABLED","").lower() == "true")
        if not self.is_local: self._status = AdapterStatus.CONFIGURED

    def get_trail_status(self) -> dict:
        """Check CloudTrail logging status. Returns LOCAL_MODE info when offline."""
        if self.is_local:
            return {"mode":"LOCAL_MODE","logging_enabled":True,"trail_name":"local-mock",
                    "note":"No real CloudTrail trail in LOCAL_MODE"}
        try:
            c = self._get_client("cloudtrail")
            if self._trail:
                s = c.get_trail_status(Name=self._trail)
                self._status = AdapterStatus.CONNECTED
                return {"trail_name":self._trail,
                        "logging_enabled":s.get("IsLogging",False),
                        "latest_delivery":str(s.get("LatestDeliveryTime",""))}
            t = c.describe_trails()
            self._status = AdapterStatus.CONNECTED
            return {"trails":[x.get("Name") for x in t.get("trailList",[])],
                    "logging_enabled":True}
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc)
            return {"error":str(exc),"logging_enabled":False}

    def validate_event(self, raw: Any) -> tuple[bool, str]:
        """Validate a raw CloudTrail event record.

        Returns (is_valid, reason). Invalid records are rejected safely.
        """
        if not isinstance(raw, dict):
            return False, "NOT_A_DICT"
        missing = _REQUIRED_FIELDS - set(raw.keys())
        if missing:
            return False, "MISSING_FIELDS:" + ",".join(sorted(missing))
        event_id = raw.get("eventID","")
        if not event_id:
            return False, "EMPTY_EVENT_ID"
        return True, "OK"

    def normalize_event(self, raw: dict) -> dict | None:
        """Normalize a raw CloudTrail event into Varynx audit schema fields.

        Preserves the full original event in source_metadata.
        Returns None when the event is invalid or already processed.

        Normalized output fields:
            source          -- always "CLOUDTRAIL" (distinguishes from internal events)
            event_id        -- CloudTrail eventID (unique, deduplicated)
            event_name      -- e.g. "PutObject", "DescribeInstances"
            event_source    -- e.g. "s3.amazonaws.com"
            event_time      -- ISO-8601 UTC
            aws_account_id  -- AWS account where event occurred
            aws_region      -- AWS region
            principal_arn   -- IAM identity ARN (from userIdentity.arn)
            principal_type  -- IAMUser | AssumedRole | AWSService | etc.
            request_id      -- AWS request ID for correlation
            source_ip       -- caller source IP (may be absent)
            error_code      -- AWS error code if request failed
            error_message   -- AWS error message (truncated for safety)
            resources       -- list of AWS resources involved
            source_metadata -- full original CloudTrail event (preserved)
        """
        valid, reason = self.validate_event(raw)
        if not valid:
            logger.warning("CloudTrail event rejected: %s | raw=%s", reason,
                           str(raw)[:200])
            return None
        event_id = raw["eventID"]
        if event_id in self._ingested_ids:
            logger.debug("CloudTrail duplicate skipped: %s", event_id)
            return None
        # Normalize eventTime to ISO-8601 UTC
        raw_time = raw.get("eventTime","")
        try:
            if isinstance(raw_time, str):
                event_time = raw_time
            elif isinstance(raw_time, datetime):
                event_time = raw_time.astimezone(UTC).isoformat()
            else:
                event_time = str(raw_time)
        except Exception:
            event_time = str(raw_time)
        # Extract identity (safe: may be missing)
        identity = raw.get("userIdentity") or {}
        principal_arn = identity.get("arn") or identity.get("principalId","unknown")
        principal_type = identity.get("type","unknown")
        # Resources (may be absent)
        resources = []
        for r in raw.get("resources") or []:
            resources.append({"arn":r.get("ARN",""),"type":r.get("resourceType",""),
                               "name":r.get("resourceName","")})
        # Error (truncate message to prevent log injection)
        error_msg = raw.get("errorMessage","")
        if error_msg: error_msg = str(error_msg)[:200]
        normalized = {
            "source": "CLOUDTRAIL",
            "event_id": event_id,
            "event_name": raw.get("eventName",""),
            "event_source": raw.get("eventSource",""),
            "event_time": event_time,
            "aws_account_id": raw.get("recipientAccountId") or raw.get("userIdentity",{}).get("accountId",""),
            "aws_region": raw.get("awsRegion",""),
            "principal_arn": principal_arn,
            "principal_type": principal_type,
            "request_id": raw.get("requestID",""),
            "source_ip": raw.get("sourceIPAddress",""),
            "error_code": raw.get("errorCode",""),
            "error_message": error_msg,
            "resources": resources,
            "source_metadata": raw,
        }
        self._ingested_ids.add(event_id)
        logger.info("CloudTrail event normalized: %s/%s", normalized["event_source"],
                    normalized["event_name"])
        return normalized

    def ingest_batch(self, events: list[Any]) -> list[dict]:
        """Normalize a batch of raw CloudTrail events.

        Returns list of successfully normalized events.
        Invalid and duplicate events are logged and skipped.
        """
        results = []
        for ev in events:
            n = self.normalize_event(ev)
            if n is not None:
                results.append(n)
        logger.info("CloudTrail batch: %d/%d events normalized", len(results), len(events))
        return results

    def lookup_events(self, hours: int = 1) -> list[dict]:
        """Fetch and normalize recent CloudTrail events.

        LOCAL_MODE: returns empty list (no mock events to avoid fabricating data).
        AWS_MODE: calls CloudTrail LookupEvents API.
        """
        if self.is_local:
            return []  # No fabricated events in local mode
        if not self._enabled:
            return []
        try:
            c = self._get_client("cloudtrail")
            end = datetime.now(UTC); start = end - timedelta(hours=hours)
            r = c.lookup_events(StartTime=start, EndTime=end, MaxResults=50)
            self._status = AdapterStatus.CONNECTED
            raw_events = r.get("Events",[])
            return self.ingest_batch(raw_events)
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc)
            logger.error("CloudTrail lookup_events failed: %s", exc)
            return []

    def health_check(self) -> dict:
        b = super().health_check()
        b["trail_name"] = self._trail or "(not configured)"
        b["ingested_count"] = len(self._ingested_ids)
        return b