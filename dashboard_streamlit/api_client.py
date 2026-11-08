"""HTTP client for the Varynx FastAPI backend.

All dashboard pages use this module to communicate with the API.
Never invent responses -- every call returns the real API result or an error.
"""
from __future__ import annotations

import os
from datetime import UTC
from typing import Any

import requests


def get_api_base() -> str:
    """Return the configured API base URL."""
    return os.environ.get(
        "VARYNX_API_URL",
        "http://127.0.0.1:8000/api/v1",
    )


def get_api_key() -> str | None:
    """Return the configured API key, if any."""
    return os.environ.get("VARYNX_API_KEY")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    key = get_api_key()
    if key:
        h["X-API-Key"] = key
    return h


class APIError(Exception):
    """Raised when the API returns an error or is unreachable."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _get(path: str, params: dict | None = None) -> Any:
    url = get_api_base() + path
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
    except requests.ConnectionError as exc:
        raise APIError(0, f"Cannot connect to {url}. Is the backend running?") from exc
    except requests.Timeout as exc:
        raise APIError(0, f"Request timed out: {url}") from exc
    return _handle(r)


def _post(path: str, body: dict | None = None) -> Any:
    url = get_api_base() + path
    try:
        r = requests.post(url, headers=_headers(), json=body, timeout=10)
    except requests.ConnectionError as exc:
        raise APIError(0, f"Cannot connect to {url}. Is the backend running?") from exc
    except requests.Timeout as exc:
        raise APIError(0, f"Request timed out: {url}") from exc
    return _handle(r)


def _patch(path: str) -> Any:
    url = get_api_base() + path
    try:
        r = requests.patch(url, headers=_headers(), timeout=10)
    except requests.ConnectionError as exc:
        raise APIError(0, f"Cannot connect to {url}. Is the backend running?") from exc
    return _handle(r)


def _delete(path: str) -> Any:
    url = get_api_base() + path
    try:
        r = requests.delete(url, headers=_headers(), timeout=10)
    except requests.ConnectionError as exc:
        raise APIError(0, f"Cannot connect to {url}. Is the backend running?") from exc
    return _handle(r)


def _handle(r: requests.Response) -> Any:
    if r.status_code >= 400:
        try:
            detail = r.json()
            msg = detail.get("message") or detail.get("detail") or str(detail)
        except Exception:
            msg = r.text or f"HTTP {r.status_code}"
        raise APIError(r.status_code, msg)
    return r.json().get("data")


# --- Public API methods ---

def get_health() -> dict:
    return _get("/health")

def get_metrics() -> dict:
    return _get("/metrics")

def get_config() -> dict:
    return _get("/config")

def register_agent(agent_id: str, owning_principal: str,
                   declared_capability_scope: list[str],
                   authorized_resource_scope: list[str]) -> dict:
    return _post("/agents", {
        "agent_id": agent_id,
        "owning_principal": owning_principal,
        "declared_capability_scope": declared_capability_scope,
        "authorized_resource_scope": authorized_resource_scope,
    })

def get_agent(agent_id: str) -> dict:
    return _get(f"/agents/{agent_id}")

def get_agent_profile(agent_id: str) -> dict:
    return _get(f"/agents/{agent_id}/profile")

def create_session(agent_id: str) -> dict:
    return _post("/sessions", {"agent_id": agent_id})

def get_session(session_id: str) -> dict:
    return _get(f"/sessions/{session_id}")

def create_lease(agent_id: str, session_id: str, capability: str,
                 resource_scope: dict, issuing_principal: str) -> dict:
    return _post("/leases", {
        "agent_id": agent_id,
        "session_id": session_id,
        "capability": capability,
        "resource_scope": resource_scope,
        "issuing_principal": issuing_principal,
    })

def get_lease(lease_id: str) -> dict:
    return _get(f"/leases/{lease_id}")

def suspend_lease(lease_id: str) -> dict:
    return _patch(f"/leases/{lease_id}/suspend")

def revoke_lease(lease_id: str) -> dict:
    return _delete(f"/leases/{lease_id}")

def submit_event(agent_id: str, session_id: str, action_type: str,
                 capability: str, target_resource: str,
                 authorization_result: str = "allowed",
                 is_simulated: bool = True) -> dict:
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

def get_audit_records(agent_id: str | None = None,
                       record_type: str | None = None,
                       limit: int = 100) -> dict:
    params = {"limit": limit}
    if agent_id:
        params["agent_id"] = agent_id
    if record_type:
        params["record_type"] = record_type
    return _get("/audit", params=params)

def verify_audit_chain() -> dict:
    return _get("/audit/verify")

def get_audit_record(record_id: str) -> dict:
    return _get(f"/audit/{record_id}")

def get_provenance(correlation_id: str) -> dict:
    return _get(f"/audit/provenance/{correlation_id}")
