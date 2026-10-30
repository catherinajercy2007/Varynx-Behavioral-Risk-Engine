from __future__ import annotations
import base64, logging, os
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class KMSAdapter(AWSAdapter):
    service_name = "kms"
    def __init__(self) -> None:
        super().__init__()
        self._key_id = os.environ.get("VARYNX_KMS_KEY_ID")
        if not self.is_local and self._key_id: self._status = AdapterStatus.CONFIGURED
    def encrypt(self, plaintext: bytes) -> bytes:
        if self.is_local or not self._key_id:
            logger.debug("KMS[LOCAL] base64 only - not secure")
            return base64.b64encode(b"LOCAL:" + plaintext)
        try:
            c = self._get_client("kms")
            r = c.encrypt(KeyId=self._key_id, Plaintext=plaintext)
            self._status = AdapterStatus.CONNECTED; return r["CiphertextBlob"]
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc); raise
    def decrypt(self, ciphertext: bytes) -> bytes:
        if self.is_local or not self._key_id:
            d = base64.b64decode(ciphertext)
            return d[6:] if d.startswith(b"LOCAL:") else d
        try:
            c = self._get_client("kms")
            r = c.decrypt(CiphertextBlob=ciphertext)
            self._status = AdapterStatus.CONNECTED; return r["Plaintext"]
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc); raise
    def key_id(self) -> str | None: return self._key_id