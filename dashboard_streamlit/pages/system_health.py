
"""Varynx System Health page."""
from __future__ import annotations

import streamlit as st

from api_client import APIError, get_config, get_health
from components import metric_card, section_header


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def get_subsystem_state(value: object) -> tuple[str, str]:
    """Classify subsystem status without treating stubs as operational."""

    text = str(value).strip().lower()

    if "stub" in text:
        return "STUB / LIMITED", "#ffb74d"

    if text == "ok" or text.startswith("ok "):
        return "OPERATIONAL", "#00e676"

    if text in {"healthy", "operational", "active"}:
        return "OPERATIONAL", "#00e676"

    if text in {"", "unknown", "none"}:
        return "UNKNOWN", "#8b95a8"

    return "WARNING", "#ff5252"


def redact_secrets(value):
    """Recursively redact configuration fields that may contain secrets."""

    sensitive_terms = (
        "api_key",
        "secret",
        "password",
        "token",
        "credential",
        "private_key",
        "access_key",
    )

    if isinstance(value, dict):
        safe = {}

        for key, item in value.items():
            key_text = str(key).lower()

            if any(term in key_text for term in sensitive_terms):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = redact_secrets(item)

        return safe

    if isinstance(value, list):
        return [redact_secrets(item) for item in value]

    return value


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------

section_header(
    "System Health",
    "Backend operational status, storage counts, subsystem "
    "availability and a redacted configuration snapshot.",
)


# ---------------------------------------------------------------------
# Health information
# ---------------------------------------------------------------------

try:
    with st.spinner("Checking backend health..."):
        health = get_health()

    if not isinstance(health, dict):
        st.error("Unexpected health response from the backend.")
        st.stop()

    status = str(
        health.get("status", "unknown")
    ).lower()

    timestamp = health.get("timestamp", "Not supplied")

    if status == "healthy":
        st.success("Backend health endpoint reports HEALTHY.")
    else:
        st.warning(
            f"Backend health endpoint reports: {status.upper()}"
        )

    st.caption(f"Last reported timestamp: {timestamp}")

    st.divider()

    # -----------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------

    section_header("Storage Counts")

    storage = health.get("storage", {})

    if not isinstance(storage, dict):
        storage = {}

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Agents", storage.get("agents", "N/A"))

    with col2:
        metric_card("Sessions", storage.get("sessions", "N/A"))

    with col3:
        metric_card("Leases", storage.get("leases", "N/A"))

    with col4:
        metric_card(
            "Audit Records",
            storage.get("audit_records", "N/A"),
        )

    st.divider()

    # -----------------------------------------------------------------
    # Subsystem status
    # -----------------------------------------------------------------

    section_header(
        "Subsystem Status",
        "Operational components are separated from stubs and warnings.",
    )

    subsystems = health.get("subsystems", {})

    if isinstance(subsystems, dict) and subsystems:
        for name, subsystem_value in subsystems.items():
            state, color = get_subsystem_state(subsystem_value)

            col_name, col_state = st.columns([3, 2])

            with col_name:
                st.write(f"**{name}**")
                st.caption(str(subsystem_value))

            with col_state:
                st.markdown(
                    f'<div style="text-align:right;'
                    f'color:{color};font-weight:700;'
                    f'padding-top:8px;">{state}</div>',
                    unsafe_allow_html=True,
                )

            st.divider()
    else:
        st.info("No subsystem information was returned.")

    # -----------------------------------------------------------------
    # Configuration snapshot
    # -----------------------------------------------------------------

    section_header(
        "Configuration Snapshot",
        "Sensitive configuration values are redacted before display.",
    )

    try:
        with st.spinner("Loading configuration..."):
            config = get_config()

        if isinstance(config, (dict, list)):
            st.json(redact_secrets(config))
        else:
            st.info(
                "The configuration endpoint returned no structured data."
            )

    except APIError as exc:
        st.warning(
            f"Configuration could not be retrieved. "
            f"HTTP {exc.status_code}: {exc.message}"
        )

except APIError as exc:
    st.error(
        f"Backend health request failed. "
        f"HTTP {exc.status_code}: {exc.message}"
    )
    st.stop()

except Exception:
    st.error(
        "An unexpected error occurred while loading System Health."
    )
    st.exception(Exception("System Health rendering failed."))
    st.stop()
