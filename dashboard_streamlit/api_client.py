
"""HTTP client for the Varynx FastAPI backend."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import requests


def get_api_base() -> str:
    return os.environ.get(
        "VARYNX_API_URL",
        "http://127.0.0.1:8000/api/v1",
    ).rstrip("/")


def get_api_key() -> str | None:
    return os.environ.get("VARYNX_API_KEY")


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = get_api_key()
    if key:
        headers["X-API-Key"] = key
    return headers


class APIError(Exception):
    """Raised when the API returns an error or cannot be reached."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _handle(response: requests.Response) -> Any:
    """Parse API responses without exposing HTML proxy/challenge pages."""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not response.ok:
        if isinstance(payload, dict):
            message = (
                payload.get("message")
                or payload.get("detail")
                or payload.get("error")
                or f"API request failed with HTTP {response.status_code}"
            )
        else:
            message = (
                f"API request failed with HTTP {response.status_code}. "
                "The server returned a non-JSON response."
            )
        raise APIError(response.status_code, str(message))

    if payload is None:
        raise APIError(
            response.status_code,
            "The backend returned an empty or invalid JSON response.",
        )

    # Support both {"data": ...} and direct JSON responses.
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]

    return payload


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    body: dict | None = None,
) -> Any:
    url = f"{get_api_base()}{path}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=_headers(),
            params=params,
            json=body,
            timeout=(5, 20),
        )
    except requests.Timeout as exc:
        raise APIError(0, f"Request timed out: {url}") from exc
    except requests.ConnectionError as exc:
        raise APIError(
            0,
            f"Cannot connect to the Varynx backend: {url}",
        ) from exc
    except requests.RequestException as exc:
        raise APIError(0, f"Network request failed: {exc}") from exc

    return _handle(response)


def _get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def _post(path: str, body: dict | None = None) -> Any:
    return _request("POST", path, body=body or {})


def _patch(path: str) -> Any:
    return _request("PATCH", path)


def _delete(path: str) -> Any:
    return _request("DELETE", path)


# -------------------------------------------------------------------
# Health, metrics and configuration
# -------------------------------------------------------------------

def get_health() -> dict:
    return _get("/health")


def get_metrics() -> dict:
    return _get("/metrics")


def get_config() -> dict:
    return _get("/config")


# -------------------------------------------------------------------
# Agent management
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Session management
# -------------------------------------------------------------------

def create_session(agent_id: str) -> dict:
    return _post("/sessions", {"agent_id": agent_id})


def get_session(session_id: str) -> dict:
    return _get(f"/sessions/{quote(session_id, safe='')}")


# -------------------------------------------------------------------
# Lease management
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Security event ingestion
# -------------------------------------------------------------------

def submit_event(
    agent_id: str,
    session_id: str,
    action_type: str,
    capability: str,
    target_resource: str,
    authorization_result: str = "allowed",
    is_simulated: bool = True,
) -> dict:
    """Submit one security event to POST /api/v1/events."""
    event = {
        "agent_id": agent_id,
        "session_id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "action_type": action_type,
        "capability_requested": capability,
        "target_resource": target_resource,
        "authorization_result": authorization_result,
        "is_simulated": is_simulated,
    }
    return _post("/events", event)


# -------------------------------------------------------------------
# Audit and provenance
# -------------------------------------------------------------------

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
