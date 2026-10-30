from __future__ import annotations
import logging, os
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class ECSAdapter(AWSAdapter):
    service_name = "ecs"
    def __init__(self) -> None:
        super().__init__()
        self._cluster = os.environ.get("VARYNX_ECS_CLUSTER","varynx-cluster")
        self._service = os.environ.get("VARYNX_ECS_SERVICE","varynx-api")
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def get_service_status(self) -> dict:
        if self.is_local:
            return {"mode":"LOCAL_MODE","cluster":self._cluster,"service":self._service,
                    "running_count":1,"desired_count":1,"status":"ACTIVE"}
        try:
            c = self._get_client("ecs")
            r = c.describe_services(cluster=self._cluster,services=[self._service])
            svcs = r.get("services",[])
            if svcs:
                s = svcs[0]; self._status = AdapterStatus.CONNECTED
                return {"cluster":self._cluster,"service":self._service,
                        "running_count":s.get("runningCount",0),
                        "desired_count":s.get("desiredCount",0),"status":s.get("status","?")}
            return {"error":"Service not found"}
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc); return {"error":str(exc)}