from __future__ import annotations
import logging, os
from enum import Enum
logger = logging.getLogger(__name__)

class AdapterStatus(str, Enum):
    LOCAL_MODE = "LOCAL_MODE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"

class AWSAdapter:
    service_name: str = "unknown"
    def __init__(self) -> None:
        self._status = AdapterStatus.LOCAL_MODE
        self._error: str | None = None
        self._boto3_available = self._check_boto3()
        self._region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if self._boto3_available and self._region:
            self._status = AdapterStatus.NOT_CONFIGURED
        else:
            self._status = AdapterStatus.LOCAL_MODE
    def _check_boto3(self) -> bool:
        try:
            import boto3; return True
        except ImportError:
            return False
    @property
    def status(self): return self._status
    @property
    def is_local(self) -> bool: return self._status == AdapterStatus.LOCAL_MODE
    def health_check(self) -> dict: return {"service": self.service_name, "status": self._status.value, "error": self._error}
    def _get_client(self, service: str):
        if not self._boto3_available: raise RuntimeError(f"boto3 not installed; {self.service_name} in LOCAL_MODE")
        import boto3; return boto3.client(service, region_name=self._region)