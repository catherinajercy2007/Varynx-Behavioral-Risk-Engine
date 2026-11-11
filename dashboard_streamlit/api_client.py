
"""HTTP client for the Varynx FastAPI backend.

Features:
- Short-lived caching for successful GET responses.
- Consistent timeout and connection-error handling.
- Safe handling of HTTP 429, 502, 503 and other errors.
- Detection of HTML challenge/proxy responses.
- No automatic retries that could amplify rate limiting.

All dashboard pages should use this module for backend communication.
"""
from __future__ import annotations

import os
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

GET_CACHE_TTL_SECONDS = 15
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 15
MAX_ERROR_MESSAGE_LENGTH = 500


def get_api_base() -> str:
    """Return the configured API base URL."""
    return os.environ.get(
        "VARYNX_API_URL",
        "http://127.0.0.1:8000/api/v1",
    ).rstrip("/")


def get_api_key() -> str | None:
    """Return the configured API key, if available."""
    key = os.environ.get("VARYNX_API_KEY")
    return key.strip() if key and key.strip() else None


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    key = get_api_key()
    if key:
        headers["X-API-Key"] = key

    return headers


# ---------------------------------------------------------------------
# API exceptions
# ---------------------------------------------------------------------

class APIError(Exception):
    """A safe, user-readable API communication error."""

    def __init__(
        self,
        status_code: int,
        message: str,
        retry_after: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after
        self.error_code = error_code

        super().__init__(message)


def _shorten_message(message: str) -> str:
    """Remove excessive whitespace and limit displayed error text."""
    message = " ".join(str(message).split())

    if len(message) > MAX_ERROR_MESSAGE_LENGTH:
        message = message[:MAX_ERROR_MESSAGE_LENGTH].rstrip() + "..."

    return message


def _retry_after_seconds(value: str | None) -> str | None:
    """Normalize Retry-After into a readable duration where possible."""
    if not value:
        return None

    try:
        seconds = int(value)
        return f"{seconds} seconds"
    except (TypeError, ValueError):
        pass

    try:
        retry_time = parsedate_to_datetime(value)
        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=UTC)

        now = UTC.now()
        seconds = max(0, int((retry_time - now).total_seconds()))
        return f"{seconds} seconds"
    except (TypeError, ValueError, OverflowError):
        return value


# ---------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------

def _handle(response: requests.Response) -> Any:
    """Validate an HTTP response and return its JSON payload."""

    status = response.status_code
    content_type = response.headers.get("Content-Type", "").lower()
    body = response.text or ""

    # Detect Cloudflare challenges and other HTML proxy responses.
    is_html = (
        "text/html" in content_type
        or body.lstrip().lower().startswith(
            ("<!doctype html", "<html")
        )
    )

    if status == 429:
        retry_after = _retry_after_seconds(
            response.headers.get("Retry-After")
        )

        if is_html and (
            "cloudflare" in body.lower()
            or "just a moment" in body.lower()
        ):
            message = (
                "The backend request was challenged or rate-limited "
                "by Cloudflare. This is an upstream access issue, not "
                "a Varynx JSON API response."
            )
        else:
            message = (
                "Varynx API rate limit exceeded. Wait before making "
                "another request."
            )

        if retry_after:
            message += f" Suggested wait: {retry_after}."

        raise APIError(
            status,
            message,
            retry_after=retry_after,
            error_code="UPSTREAM_RATE_LIMIT",
        )

    if status in (502, 503, 504):
        message = (
            "The backend or an upstream proxy is temporarily "
            f"unavailable (HTTP {status}). Check the backend service "
            "and its deployment logs."
        )

        if is_html:
            message += " The upstream returned an HTML error page."

        raise APIError(
            status,
            message,
            retry_after=_retry_after_seconds(
                response.headers.get("Retry-After")
            ),
            error_code="UPSTREAM_UNAVAILABLE",
        )

    if status >= 400:
        if is_html:
            message = (
                f"The server returned an HTML error page "
                f"(HTTP {status}). The response was not JSON."
            )
            raise APIError(status, message)

        try:
            payload = response.json()

            if isinstance(payload, dict):
                message = (
                    payload.get("message")
                    or payload.get("detail")
                    or payload.get("error")
                    or f"HTTP {status}"
                )
                error_code = payload.get("error_code")
            else:
                message = str(payload)
                error_code = None

        except (ValueError, requests.exceptions.JSONDecodeError):
            message = f"HTTP {status}: {_shorten_message(body)}"
            error_code = None

        raise APIError(
            status,
            _shorten_message(message),
            retry_after=_retry_after_seconds(
                response.headers.get("Retry-After")
            ),
            error_code=error_code,
        )

    if is_html:
        raise APIError(
            status,
            "The server returned HTML instead of JSON. "
            "Check the backend URL and any proxy or Cloudflare challenge.",
            error_code="NON_JSON_RESPONSE",
        )

    if status == 204 or not body.strip():
        return {}

    try:
        payload = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError) as exc:
        raise APIError(
            status,
            "The backend returned an invalid JSON response.",
            error_code="INVALID_JSON",
        ) from exc

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]

    return payload


# ---------------------------------------------------------------------
# HTTP request execution
# ---------------------------------------------------------------------

def _perform_request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    body: dict | None = None,
    api_key: str | None = None,
) -> Any:
    """Execute one request without automatic retries."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if api_key:
        headers["X-API-Key"] = api_key

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=body,
            timeout=(
                CONNECT_TIMEOUT_SECONDS,
                READ_TIMEOUT_SECONDS,
            ),
        )

    except requests.exceptions.Timeout as exc:
        raise APIError(
            0,
            "The backend request timed out. Check whether the Render "
            "service is awake and responding.",
            error_code="REQUEST_TIMEOUT",
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise APIError(
            0,
            "Cannot connect to the Varynx backend. Check the backend "
            "URL and Render service status.",
            error_code="CONNECTION_ERROR",
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise APIError(
            0,
            f"HTTP request failed: {_shorten_message(exc)}",
            error_code="REQUEST_ERROR",
        ) from exc

    return _handle(response)


# ---------------------------------------------------------------------
# Cached GET requests
# ---------------------------------------------------------------------

@st.cache_data(
    ttl=GET_CACHE_TTL_SECONDS,
    max_entries=256,
    show_spinner=False,
)
def _cached_get(
    url: str,
    params_items: tuple,
    api_key: str | None,
) -> Any:
    """Cache successful GET responses for a short period."""

    params = dict(params_items) if params_items else None

    return _perform_request(
        "GET",
        url,
        params=params,
        api_key=api_key,
    )


def clear_api_cache() -> None:
    """Clear cached API responses when explicitly required."""
    _cached_get.clear()


def _get(path: str, params: dict | None = None) -> Any:
    url = get_api_base() + path

    # Sorting produces a stable cache key regardless of dictionary order.
    params_items = tuple(
        sorted((params or {}).items())
    )

    return _cached_get(
        url,
        params_items,
        get_api_key(),
    )


def _post(path: str, body: dict | None = None) -> Any:
    return _perform_request(
        "POST",
        get_api_base() + path,
        body=body,
        api_key=get_api_key(),
    )


def _patch(path: str) -> Any:
    return _perform_request(
        "PATCH",
        get_api_base() + path,
        api_key=get_api_key(),
    )


def _delete(path: str) -> Any:
    return _perform_request(
        "DELETE",
        get_api_base() + path,
        api_key=get_api_key(),
    )


# ---------------------------------------------------------------------
# Public API methods
# ---------------------------------------------------------------------

def get_health() -> dict:
    return _get("/health")


def get_metrics() -> dict:
    return _get("/metrics")


def get_config() -> dict:
    return _get("/config")


def register_agent(
    agent_id: str,
    owning_principal: str,
    declared_capability_scope: list[str],
    authorized_resource_scope: list[str],
) -> dict:
    return _post("/agents", {
        "agent_id": agent_id,
        "owning_principal": owning_principal,
        "declared_capability_scope": declared_capability_scope,
        "authorized_resource_scope": authorized_resource_scope,
    })


def get_agent(agent_id: str) -> dict:
    return _get(f"/agents/{quote(agent_id, safe='')}")


def get_agent_profile(agent_id: str) -> dict:
    return _get(f"/agents/{quote(agent_id, safe='')}/profile")


def create_session(agent_id: str) -> dict:
    return _post("/sessions", {"agent_id": agent_id})


def get_session(session_id: str) -> dict:
    return _get(f"/sessions/{quote(session_id, safe='')}")


def create_lease(
    agent_id: str,
    session_id: str,
    capability: str,
    resource_scope: dict,
    issuing_principal: str,
) -> dict:
    return _post("/leases", {
        "agent_id": agent_id,
        "session_id": session_id,
        "capability": capability,
        "resource_scope": resource_scope,
        "issuing_principal": issuing_principal,
    })


def get_lease(lease_id: str) -> dict:
    return _get(f"/leases/{quote(lease_id, safe='')}")


def suspend_lease(lease_id: str) -> dict:
    return _patch(f"/leases/{quote(lease_id, safe='')}/suspend")


def revoke_lease(lease_id: str) -> dict:
    return _delete(f"/leases/{quote(lease_id, safe='')}")


def submit_event(
    agent_id: str,
    session_id: str,
    action_type: str,
    capability: str,
    target_resource: str,
    authorization_result: str = "allowed",
    is_simulated: bool = True,
) -> dict:
    from datetime import datetime

    return _post("/events", {
        "agent_id": agent_id,
        "session_id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "action_type": action_type,
        "capability_requested": capability,
        "target_resource": target_resource,
        "authorization_result": authorization_result,
        "is_simulated": is_simulated,
    })


def get_audit_records(
    agent_id: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
) -> dict:
    params = {"limit": limit}

    if agent_id:
        params["agent_id"] = agent_id

    if record_type:
        params["record_type"] = record_type

    return _get("/audit", params=params)


def verify_audit_chain() -> dict:
    return _get("/audit/verify")


def get_audit_record(record_id: str) -> dict:
    return _get(f"/audit/{quote(record_id, safe='')}")


def get_provenance(correlation_id: str) -> dict:
    return _get(
        f"/audit/provenance/{quote(correlation_id, safe='')}"
    )
