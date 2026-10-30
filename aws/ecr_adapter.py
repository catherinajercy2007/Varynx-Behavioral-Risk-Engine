from __future__ import annotations
import logging, os
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class ECRAdapter(AWSAdapter):
    service_name = "ecr"
    def __init__(self) -> None:
        super().__init__()
        self._repo = os.environ.get("VARYNX_ECR_REPOSITORY","varynx-api")
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def get_latest_image(self, tag: str = "latest") -> dict:
        if self.is_local:
            return {"mode":"LOCAL_MODE","repository":self._repo,"tag":tag,
                    "digest":"sha256:local-mock","pushed_at":"LOCAL"}
        try:
            c = self._get_client("ecr")
            r = c.describe_images(repositoryName=self._repo,imageIds=[{"imageTag":tag}])
            imgs = r.get("imageDetails",[])
            if imgs:
                i = imgs[0]; self._status = AdapterStatus.CONNECTED
                return {"repository":self._repo,"tag":tag,
                        "digest":i.get("imageDigest","?"),
                        "pushed_at":str(i.get("imagePushedAt","")),
                        "size_mb":round(i.get("imageSizeInBytes",0)/1048576,1)}
            return {"error":"Image not found"}
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc); return {"error":str(exc)}