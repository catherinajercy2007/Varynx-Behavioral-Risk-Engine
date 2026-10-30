from __future__ import annotations
import json, logging, os
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class RDSAdapter(AWSAdapter):
    service_name = "rds"
    def __init__(self, secrets_adapter=None) -> None:
        super().__init__()
        self._secrets = secrets_adapter
        self._endpoint = os.environ.get("VARYNX_RDS_ENDPOINT")
        self._secret = os.environ.get("VARYNX_RDS_SECRET_NAME")
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def get_database_url(self) -> str:
        explicit = os.environ.get("VARYNX_DATABASE_URL")
        if explicit and not explicit.startswith("memory://"): return explicit
        if self.is_local or not self._endpoint: return "memory://varynx"
        if self._secrets and self._secret:
            raw = self._secrets.get_secret(self._secret)
            if raw:
                try:
                    c = json.loads(raw)
                    u,p,d,pt = c.get("username","varynx"),c.get("password",""),c.get("dbname","varynx"),c.get("port",5432)
                    self._status = AdapterStatus.CONNECTED
                    return "postgresql://" + u + ":" + p + "@" + self._endpoint + ":" + str(pt) + "/" + d
                except Exception as exc:
                    self._status = AdapterStatus.ERROR; self._error = str(exc)
        return "postgresql://varynx@" + self._endpoint + "/varynx"