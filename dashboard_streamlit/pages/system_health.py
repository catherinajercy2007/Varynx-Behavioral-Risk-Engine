
"""System Health page."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_config, get_health
from components import api_error_box, metric_card, section_header

section_header(
    "System Health",
    "Backend operational status and configuration snapshot",
)

try:
    with st.spinner("Fetching health data..."):
        health = get_health()

    # Health status
    status = str(health.get("status", "unknown")).lower()

    if status == "healthy":
        color = "#00e676"
        status_label = "HEALTHY"
    else:
        color = "#ff5252"
        status_label = status.upper()

    st.markdown(
        f"""
        <div style="
            background:#111827;
            border:1px solid #1e293b;
            border-radius:8px;
            padding:16px;
            margin:8px;
        ">
            <span style="
                color:{color};
                font-size:1.2rem;
                font-weight:700;
            ">
                ● {status_label}
            </span>
            <span style="
                color:#8b95a8;
                margin-left:12px;
            ">
                {health.get("timestamp", "")[:19]}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Storage counts
    st.subheader("Storage Counts")

    storage = health.get("storage", {})

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Agents", storage.get("agents", 0))

    with col2:
        metric_card("Sessions", storage.get("sessions", 0))

    with col3:
        metric_card("Leases", storage.get("leases", 0))

    with col4:
        metric_card("Audit Records", storage.get("audit_records", 0))

    st.divider()

    # Subsystem status
    st.subheader("Subsystem Status")

    subsystems = health.get("subsystems", {})

    if subsystems:
        for name, subsystem_status in subsystems.items():

            status_text = str(subsystem_status)

            color = (
                "#00e676"
                if status_text.lower() == "ok"
                or "ok" in status_text.lower()
                else "#ffb74d"
            )

            st.markdown(
                f"""
                <div style="
                    background:#111827;
                    border:1px solid #1e293b;
                    border-radius:6px;
                    padding:10px;
                    margin:4px;
                    display:flex;
                    justify-content:space-between;
                ">
                    <span style="color:#e0e6f0">
                        {name}
                    </span>
                    <span style="
                        color:{color};
                        font-weight:600;
                    ">
                        {status_text}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # Configuration snapshot
    st.subheader("Configuration Snapshot")

    try:
        config = get_config()
        st.json(config)

    except APIError:
        st.info(
            "**Simulated Resource Gateway:** Varynx evaluates behavioral "
            "risk and produces security decisions. It does not directly "
            "enforce operations on real files, cloud storage, or "
            "third-party APIs. Enforcement modifies internal lease state "
            "and records audit events.\n\n"

            "**Phase 2 Engines:** BCSE returns `is_stub=False` when "
            "alternative policies are supplied; otherwise it remains "
            "a stub. The predictive engine uses OLS regression over "
            "trust history and remains a stub until the required "
            "history and session-age conditions are satisfied.\n\n"

            "**Storage:** Persistence depends on the active backend "
            "configuration. Check the configured storage implementation "
            "before assuming that state is lost on server restart.",
            icon="ℹ️",
        )

except APIError as exc:
    api_error_box(exc)
