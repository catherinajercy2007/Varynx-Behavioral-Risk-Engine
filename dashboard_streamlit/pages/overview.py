"""Security Overview page."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_health, get_metrics
from components import api_error_box, metric_card, section_header

section_header("Security Overview", "Real-time system metrics from the Varynx backend")

try:
    with st.spinner("Fetching health data..."):
        health = get_health()
    metrics = get_metrics()

    # Top row: connectivity + health
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Backend", "ONLINE" if health.get("status") == "healthy" else "OFFLINE")
    with col2:
        metric_card("Agents Registered", metrics.get("agents_tracked", "N/A"))
    with col3:
        metric_card("Active Sessions", metrics.get("sessions_active", "N/A"))
    with col4:
        metric_card("Active Leases", metrics.get("leases_active", "N/A"))

    col5, col6, col7 = st.columns(3)
    with col5:
        metric_card("Events Ingested", metrics.get("events_ingested", "N/A"))
    with col6:
        metric_card("Audit Records", metrics.get("audit_records", "N/A"))
    with col7:
        # storage.leases is an integer returned by the API, not a list
        _storage = health.get("storage", {})
        metric_card("Total Leases", _storage.get("leases", "N/A") if isinstance(_storage, dict) else "N/A")

    st.divider()

    # Subsystem status
    section_header("Subsystem Status")
    subsystems = health.get("subsystems", {})
    if subsystems:
        cols = st.columns(min(len(subsystems), 4))
        for i, (name, status) in enumerate(subsystems.items()):
            with cols[i % len(cols)]:
                color = "#00e676" if status == "ok" or "ok" in str(status) else "#ffb74d"
                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1e293b;'
                    f'border-radius:8px;padding:12px;margin:4px">'
                    f'<div style="color:#8b95a8;font-size:0.7rem;text-transform:uppercase">{name}</div>'
                    f'<div style="color:{color};font-weight:600">{status}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("No subsystem data available")

    st.divider()

    # Storage summary
    section_header("Storage Summary")
    storage = health.get("storage", {})
    if storage:
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            metric_card("Agents", storage.get("agents", 0))
        with col_b:
            metric_card("Sessions", storage.get("sessions", 0))
        with col_c:
            metric_card("Leases", storage.get("leases", 0))
        with col_d:
            metric_card("Audit Records", storage.get("audit_records", 0))
    else:
        st.info("No storage data available")

except APIError as exc:
    api_error_box(exc)
    st.stop()
except Exception as exc:
    st.error(f"Unexpected error: {exc}")
    st.stop()
