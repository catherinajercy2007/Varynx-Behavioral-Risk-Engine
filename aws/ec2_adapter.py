from __future__ import annotations
import logging, socket
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class EC2Adapter(AWSAdapter):
    service_name = "ec2"
    def __init__(self) -> None:
        super().__init__()
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def get_instance_metadata(self) -> dict:
        if self.is_local:
            return {"mode":"LOCAL_MODE","hostname":socket.gethostname(),
                    "instance_id":"local","availability_zone":"local","instance_type":"local"}
        import urllib.request
        IMDS = "http://169.254.169.254/latest"
        try:
            treq = urllib.request.Request(IMDS+"/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds":"21600"},method="PUT")
            with urllib.request.urlopen(treq,timeout=2) as r: token = r.read().decode()
            def _g(path):
                req = urllib.request.Request(IMDS+"/meta-data/"+path,
                    headers={"X-aws-ec2-metadata-token":token})
                with urllib.request.urlopen(req,timeout=2) as r: return r.read().decode()
            self._status = AdapterStatus.CONNECTED
            return {"instance_id":_g("instance-id"),"availability_zone":_g("placement/availability-zone"),
                    "instance_type":_g("instance-type"),"hostname":socket.gethostname()}
        except Exception as exc:
            self._status = AdapterStatus.DEGRADED; self._error = str(exc)
            return {"mode":"IMDS_UNAVAILABLE","hostname":socket.gethostname(),"error":str(exc)}