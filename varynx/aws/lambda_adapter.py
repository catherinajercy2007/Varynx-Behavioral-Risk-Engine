from __future__ import annotations
import json, logging, os
from typing import Any, Callable
from varynx.aws.base import AWSAdapter, AdapterStatus
logger = logging.getLogger(__name__)
class LambdaAdapter(AWSAdapter):
    service_name = "lambda"
    def __init__(self) -> None:
        super().__init__()
        self._handlers: dict[str, Callable] = {}
        self._prefix = os.environ.get("VARYNX_LAMBDA_PREFIX","varynx-")
        if not self.is_local: self._status = AdapterStatus.CONFIGURED
    def register_local_handler(self, name: str, fn: Callable): self._handlers[name] = fn
    def invoke(self, function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.is_local:
            if function_name in self._handlers:
                logger.info("Lambda[LOCAL] in-process: %s", function_name)
                return self._handlers[function_name](payload)
            logger.info("Lambda[LOCAL] no handler for %s", function_name)
            return {"statusCode": 200, "body": json.dumps({"mode": "LOCAL_MOCK", "fn": function_name})}
        fn = self._prefix + function_name
        try:
            client = self._get_client("lambda")
            resp = client.invoke(FunctionName=fn, InvocationType="RequestResponse", Payload=json.dumps(payload))
            self._status = AdapterStatus.CONNECTED
            return json.loads(resp["Payload"].read())
        except Exception as exc:
            self._status = AdapterStatus.ERROR; self._error = str(exc); raise