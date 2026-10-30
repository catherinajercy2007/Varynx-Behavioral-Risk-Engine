from __future__ import annotations
import json, logging, os, time
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
_CACHE_TTL = 300
class SecretsManagerAdapter(AWSAdapter):
    service_name = "secretsmanager"
    def __init__(self) -> None:
        super().__init__()
        self._cache: dict = {}
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def get_secret(self, secret_name: str, env_fallback: str | None = None) -> str | None:
        if self.is_local:
            return os.environ.get(env_fallback or secret_name)
        now = time.monotonic()
        if secret_name in self._cache:
            v, exp = self._cache[secret_name]
            if now < exp: return v
        try:
            client = self._get_client("secretsmanager")
            resp = client.get_secret_value(SecretId=secret_name)
            raw = resp.get("SecretString") or resp.get("SecretBinary",b"").decode()
            self._cache[secret_name] = (raw, now + _CACHE_TTL)
            self._status = AdapterStatus.CONNECTED
            logger.info("SecretsManager: retrieved %s (redacted)", secret_name)
            return raw
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc)
            logger.error("SecretsManager %s failed: %s", secret_name, exc)
            return None
    def invalidate_cache(self, name: str | None = None):
        if name: self._cache.pop(name, None)
        else: self._cache.clear()