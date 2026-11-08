"""Risk Decision Monitoring page."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_audit_records
from components import api_error_box, metric_card, section_header

section_header("Risk Decision Monitoring",
               "Behavioral evaluation results and enforcement outcomes from audit records")

st.info(
    "The backend does not expose a dedicated historical-decisions endpoint. "
    "This page reconstructs recent decisions from audit records "
    "(RESPONSE_RECOMMENDED and ENFORCEMENT_APPLIED types).",
    icon="ℹ️",
)

try:
    with st.spinner("Fetching recent decisions..."):
        data = get_audit_records(limit=100)

    records = data.get("records", [])
    response_recs = [r for r in records if r.get("record_type") == "RESPONSE_RECOMMENDED"]
    enforcement_recs = [r for r in records if r.get("record_type") == "ENFORCEMENT_APPLIED"]

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Total Audit Records", data.get("count", len(records)))
    with col2:
        metric_card("Response Recommendations", len(response_recs))
    with col3:
        metric_card("Enforcement Actions", len(enforcement_recs))

    st.divider()

    # Recent response recommendations
    st.subheader("Recent Security Decisions")
    if response_recs:
        for rec in response_recs[-15:]:
            payload = rec.get("payload", {})
            response_type = payload.get("response_type", "UNKNOWN")
            agent_id = rec.get("agent_id", "N/A")
            timestamp = str(rec.get("timestamp", ""))[:19]
            reason_codes = payload.get("reason_codes", [])

            color = {"PERMIT": "#00e676", "WARN": "#ffb74d", "RESTRICT": "#ff9800",
                     "SUSPEND": "#ff5252", "TERMINATE": "#ff1744",
                     "ESCALATE": "#b388ff"}.get(response_type, "#8b95a8")

            st.markdown(
                f'<div style="background:#111827;border:1px solid #1e293b;'
                f'border-radius:8px;padding:12px;margin:4px">'
                f'<div style="display:flex;justify-content:space-between">'
                f'<span style="color:{color};font-weight:700">{response_type}</span>'
                f'<span style="color:#8b95a8;font-size:0.8rem">{timestamp}</span>'
                f'</div>'
                f'<div style="color:#e0e6f0;font-size:0.9rem;margin-top:4px">'
                f'Agent: <code>{agent_id}</code></div>'
                f'<div style="color:#8b95a8;font-size:0.8rem;margin-top:4px">'
                f'Reason: {", ".join(reason_codes) if reason_codes else "N/A"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No response recommendations in recent audit records. "
                "Submit events via POST /api/v1/events to generate decisions.")

    st.divider()

    # Recent enforcement actions
    st.subheader("Recent Enforcement Actions")
    if enforcement_recs:
        for rec in enforcement_recs[-10:]:
            payload = rec.get("payload", {})
            outcome = payload.get("outcome", "UNKNOWN")
            action = payload.get("action", "N/A")
            agent_id = rec.get("agent_id", "N/A")
            timestamp = str(rec.get("timestamp", ""))[:19]

            color = {"SUCCESS": "#00e676", "FAILED": "#ff5252",
                     "SKIPPED": "#ffb74d"}.get(outcome, "#8b95a8")

            st.markdown(
                f'<div style="background:#111827;border:1px solid #1e293b;'
                f'border-radius:8px;padding:12px;margin:4px">'
                f'<div style="display:flex;justify-content:space-between">'
                f'<span style="color:{color};font-weight:700">{outcome}</span>'
                f'<span style="color:#8b95a8;font-size:0.8rem">{timestamp}</span>'
                f'</div>'
                f'<div style="color:#e0e6f0;font-size:0.9rem;margin-top:4px">'
                f'Action: <code>{action}</code> | Agent: <code>{agent_id}</code></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No enforcement actions in recent audit records")

except APIError as exc:
    api_error_box(exc)
