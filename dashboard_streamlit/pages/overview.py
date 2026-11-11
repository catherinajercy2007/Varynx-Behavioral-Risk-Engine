
"""Varynx Security Overview page."""
from __future__ import annotations

import streamlit as st

from api_client import APIError, get_health, get_metrics
from components import (
    api_error_box,
    metric_card,
    section_header,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def subsystem_state(value: object) -> tuple[str, str]:
    """Return a display state and color for a subsystem."""

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


# ---------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------

section_header(
    "Security Overview",
    "Backend metrics and subsystem status. Successful GET responses "
    "are cached for 15 seconds.",
)


# ---------------------------------------------------------------------
# Backend data
# ---------------------------------------------------------------------

try:
    with st.spinner("Loading Varynx security metrics..."):
        health = get_health()
        metrics = get_metrics()

    if not isinstance(health, dict):
        raise APIError(
            0,
            "The backend health endpoint returned an unexpected response.",
        )

    if not isinstance(metrics, dict):
        raise APIError(
            0,
            "The backend metrics endpoint returned an unexpected response.",
        )

    health_status = str(
        health.get("status", "unknown")
    ).lower()

    if health_status == "healthy":
        st.success("Backend is responding with healthy status.")
    else:
        st.warning(
            f"Backend responded with status: {health_status}"
        )

    # -----------------------------------------------------------------
    # Main metrics
    # -----------------------------------------------------------------

    st.subheader("Security Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Backend",
            "ONLINE" if health_status == "healthy" else "WARNING",
        )

    with col2:
        metric_card(
            "Agents Registered",
            metrics.get("agents_tracked", "N/A"),
        )

    with col3:
        metric_card(
            "Active Sessions",
            metrics.get("sessions_active", "N/A"),
        )

    with col4:
        metric_card(
            "Active Leases",
            metrics.get("leases_active", "N/A"),
        )

    col5, col6, col7 = st.columns(3)

    with col5:
        metric_card(
            "Events Ingested",
            metrics.get("events_ingested", "N/A"),
        )

    with col6:
        metric_card(
            "Audit Records",
            metrics.get("audit_records", "N/A"),
        )

    with col7:
        storage = health.get("storage", {})
        total_leases = (
            storage.get("leases", "N/A")
            if isinstance(storage, dict)
            else "N/A"
        )

        metric_card(
            "Total Leases",
            total_leases,
        )

    st.caption(
        f"Health timestamp: {health.get('timestamp', 'Not supplied')}"
    )

    st.divider()

    # -----------------------------------------------------------------
    # Subsystem status
    # -----------------------------------------------------------------

    section_header(
        "Subsystem Status",
        "A stub is not considered a fully operational subsystem.",
    )

    subsystems = health.get("subsystems", {})

    if isinstance(subsystems, dict) and subsystems:
        columns = st.columns(min(len(subsystems), 4))

        for index, (name, value) in enumerate(subsystems.items()):
            state, color = subsystem_state(value)

            with columns[index % len(columns)]:
                st.markdown(
                    f"""
                    <div style="
                        background:#111827;
                        border:1px solid #263244;
                        border-radius:10px;
                        padding:14px;
                        margin:5px 0;
                        min-height:105px;
                    ">
                        <div style="
                            color:#8b95a8;
                            font-size:0.72rem;
                            text-transform:uppercase;
                            margin-bottom:10px;
                        ">
                            {name}
                        </div>
                        <div style="
                            color:{color};
                            font-size:0.95rem;
                            font-weight:700;
                        ">
                            {state}
                        </div>
                        <div style="
                            color:#aab4c5;
                            font-size:0.75rem;
                            margin-top:7px;
                            overflow-wrap:anywhere;
                        ">
                            {value}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("The backend did not provide subsystem information.")

    st.divider()

    # -----------------------------------------------------------------
    # Storage summary
    # -----------------------------------------------------------------

    section_header(
        "Storage Summary",
        "Counts reported by the backend health endpoint.",
    )

    storage = health.get("storage", {})

    if isinstance(storage, dict) and storage:
        col_a, col_b, col_c, col_d = st.columns(4)

        with col_a:
            metric_card("Agents", storage.get("agents", 0))

        with col_b:
            metric_card("Sessions", storage.get("sessions", 0))

        with col_c:
            metric_card("Leases", storage.get("leases", 0))

        with col_d:
            metric_card(
                "Audit Records",
                storage.get("audit_records", 0),
            )
    else:
        st.info("No storage summary was returned by the backend.")

except APIError as exc:
    api_error_box(exc)
    st.stop()

except Exception as exc:
    st.error(
        "Unable to render the Security Overview because an "
        "unexpected dashboard error occurred."
    )
    st.exception(exc)
    st.stop()
