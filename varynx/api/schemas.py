"""API response envelope and common schemas.

Satisfies: REQ-016 (standard response envelope)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


def success_response(data: Any, request_id: str | None = None) -> dict:
    """Standard success response envelope (design.md Section 15.3)."""
    return {
        "status": "success",
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }


def error_response(
    error_code: str,
    message: str,
    details: Any | None = None,
    request_id: str | None = None,
) -> dict:
    """Standard error response envelope (design.md Section 15.3)."""
    resp = {
        "status": "error",
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "error_code": error_code,
        "message": message,
    }
    if details is not None:
        resp["details"] = details
    return resp
