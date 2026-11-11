
"""Varynx System Health Dashboard.

Displays:
- Backend health status
- Backend response timestamp
- Storage statistics
- Subsystem operational status
- Phase 1 stub identification
- Redacted configuration snapshot

All backend communication is handled through api_client.py.
"""

from __future__ import annotations

import html

import streamlit as st

from api_client import APIError, get_config, get_health
from components import metric_card, section_header


# ============================================================
# PAGE CONFIGURATION
# ============================================================

section_header(
    "System Health",
    "Monitor backend availability, subsystem status, storage "
    "statistics and configuration.",
)

st.caption(
    "Health and configuration GET requests use the API client's "
    "15-second cache."
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def classify_subsystem(value: object) -> tuple[str, str]:
    """Classify subsystem status without treating stubs as healthy."""

    status = str(value).strip().lower()

    if "stub" in status:
        return "STUB / LIMITED", "#ffb74d"

    if status == "ok" or status.startswith("ok "):
        return "OPERATIONAL", "#00e676"

    if status in {"healthy", "operational", "active"}:
        return "OPERATIONAL", "#00e676"

    if status in {"", "unknown", "none"}:
        return "UNKNOWN", "#8b95a8"

    return "WARNING", "#ff5252"


def redact_secrets(value):
    """Recursively redact sensitive configuration fields."""

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
        safe_data = {}

        for key, item in value.items():
            key_name = str(key).lower()

            if any(term in key_name for term in sensitive_terms):
                safe_data[key] = "[REDACTED]"
            else:
                safe_data[key] = redact_secrets(item)

        return safe_data

    if isinstance(value, list):
        return [redact_secrets(item) for item in value]

    return value


def render_subsystem(name: str, value: object) -> None:
    """Render one subsystem with an accurate status indicator."""

    state, color = classify_subsystem(value)

    safe_name = html.escape(str(name))
    safe_value = html.escape(str(value))

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(f"**{safe_name}**")
        st.caption(safe_value)

    with col2:
        st.markdown(
            f"""
            <div style="
                text-align:right;
                padding-top:8px;
                color:{color};
                font-weight:700;
                font-size:0.85rem;
            ">
                {state}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()


# ============================================================
# BACKEND HEALTH
# ============================================================

try:

    with st.spinner("Checking Varynx backend health..."):
        health = get_health()

    if not isinstance(health, dict):
        st.error("Invalid response received from the health endpoint.")
        st.stop()

    backend_status = str(
        health.get("status", "unknown")
    ).strip().lower()

    health_timestamp = health.get(
        "timestamp",
        "Not available",
    )

    # --------------------------------------------------------
    # Backend status indicator
    # --------------------------------------------------------

    section_header("Backend Status")

    if backend_status == "healthy":
        st.success("Varynx backend reports HEALTHY status.")

    elif backend_status == "unhealthy":
        st.error("Varynx backend reports UNHEALTHY status.")

    else:
        st.warning(
            f"Backend status: {backend_status.upper()}"
        )

    st.caption(f"Last reported timestamp: {health_timestamp}")

    st.divider()

    # ========================================================
    # STORAGE STATISTICS
    # ========================================================

    section_header(
        "Storage Statistics",
        "Counts reported by the backend health endpoint.",
    )

    storage = health.get("storage", {})

    if not isinstance(storage, dict):
        storage = {}

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Registered Agents",
            storage.get("agents", "N/A"),
        )

    with col2:
        metric_card(
            "Active Sessions",
            storage.get("sessions", "N/A"),
        )

    with col3:
        metric_card(
            "Active Leases",
            storage.get("leases", "N/A"),
        )

    with col4:
        metric_card(
            "Audit Records",
            storage.get("audit_records", "N/A"),
        )

    st.divider()

    # ========================================================
    # SUBSYSTEM HEALTH
    # ========================================================

    section_header(
        "Subsystem Health",
        "Operational components, limited implementations and warnings.",
    )

    subsystems = health.get("subsystems", {})

    if isinstance(subsystems, dict) and subsystems:

        operational_count = 0
        stub_count = 0
        warning_count = 0

        for name, value in subsystems.items():

            state, _ = classify_subsystem(value)

            if state == "OPERATIONAL":
                operational_count += 1

            elif state == "STUB / LIMITED":
                stub_count += 1

            else:
                warning_count += 1

            render_subsystem(name, value)

        # Summary of subsystem states
        st.subheader("Subsystem Summary")

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Operational",
                operational_count,
            )

        with col2:
            metric_card(
                "Stub / Limited",
                stub_count,
            )

        with col3:
            metric_card(
                "Warning / Unknown",
                warning_count,
            )

    else:
        st.info(
            "The backend did not provide subsystem health information."
        )

    st.divider()

    # ========================================================
    # CONFIGURATION SNAPSHOT
    # ========================================================

    section_header(
        "Configuration Snapshot",
        "Configuration returned by the backend with sensitive "
        "values redacted.",
    )

    with st.expander(
        "View Backend Configuration",
        expanded=False,
    ):

        try:

            with st.spinner("Loading backend configuration..."):
                config = get_config()

            if isinstance(config, (dict, list)):

                safe_config = redact_secrets(config)

                st.json(safe_config)

            else:
                st.info(
                    "The configuration endpoint returned no "
                    "structured configuration data."
                )

        except APIError as exc:

            st.warning(
                f"Configuration unavailable. "
                f"HTTP {exc.status_code}: {exc.message}"
            )

    st.divider()

    # ========================================================
    # IMPLEMENTATION NOTES
    # ========================================================

    section_header("Implementation Information")

    st.info(
        """
        **Health reporting:** Subsystem status is obtained from the
        backend health endpoint.

        **Stub identification:** Components whose reported status
        contains the word `stub` are classified as limited
        implementations, not fully operational engines.

        **Storage reporting:** Agent, session, lease and audit counts
        reflect the values returned by the backend.

        **Configuration security:** Sensitive configuration fields
        are redacted before they are displayed in the dashboard.

        **API caching:** Successful GET responses are cached for
        15 seconds by the API client.
        """
    )

except APIError as exc:

    st.error(
        f"Backend health request failed. "
        f"HTTP {exc.status_code}: {exc.message}"
    )

    if exc.status_code == 429:
        st.warning(
            "The request was rate-limited or challenged upstream. "
            "Wait before trying again. Do not repeatedly refresh."
        )

    elif exc.status_code in (502, 503, 504):
        st.warning(
            "Check the backend Render service, deployment logs "
            "and upstream proxy configuration."
        )

    st.stop()

except Exception as exc:

    st.error(
        "An unexpected error occurred while rendering System Health."
    )

    st.exception(exc)
    st.stop()
