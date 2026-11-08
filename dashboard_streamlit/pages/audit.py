"""Audit Trail page."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_audit_records, verify_audit_chain
from components import api_error_box, metric_card, section_header

section_header("Audit Trail", "Tamper-evident hash-chained audit records")

# --- Filter controls ---
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    filter_agent = st.text_input("Filter by Agent ID", key="audit_agent")
with col2:
    filter_type = st.selectbox("Filter by Record Type", [
        "(all)", "EVENT_INGESTED", "EVIDENCE_PRODUCED", "TRUST_UPDATED",
        "RESPONSE_RECOMMENDED", "ENFORCEMENT_APPLIED",
        "LEASE_STATE_CHANGED", "SESSION_CREATED", "SESSION_TERMINATED",
    ])
with col3:
    limit = st.number_input("Limit", min_value=10, max_value=1000, value=100, step=10)

# --- Fetch records ---
try:
    with st.spinner("Fetching audit records..."):
        record_type = None if filter_type == "(all)" else filter_type
        data = get_audit_records(agent_id=filter_agent or None,
                                  record_type=record_type, limit=limit)
    records = data.get("records", [])

    col1, col2 = st.columns(2)
    with col1:
        metric_card("Records Returned", data.get("count", len(records)))
    with col2:
        metric_card("Total Audit Records", "—")  # Not available via API directly

    st.divider()

    # --- Hash chain verification ---
    st.subheader("Hash Chain Integrity")
    if st.button("Verify Audit Chain", type="primary"):
        try:
            with st.spinner("Verifying..."):
                result = verify_audit_chain()
            if result.get("chain_valid"):
                st.success(
                    f"✅ Chain VALID -- {result.get('record_count', 0)} records verified"
                )
            else:
                st.error(
                    f"❌ Chain INVALID -- {len(result.get('violations', []))} violations found"
                )
                for v in result.get("violations", []):
                    st.markdown(f"- {v}")
        except APIError as exc:
            api_error_box(exc)

    st.divider()

    # --- Records table ---
    st.subheader("Audit Records")
    if records:
        # Flatten for display
        display_rows = []
        for r in records:
            display_rows.append({
                "Timestamp": str(r.get("timestamp", ""))[:19],
                "Type": r.get("record_type", ""),
                "Agent ID": r.get("agent_id", ""),
                "Source": str(r.get("source_entity_id", ""))[:36],
                "Record ID": str(r.get("record_id", ""))[:36],
            })
        st.dataframe(display_rows, use_container_width=True, height=400)

        # Detail view for selected record
        st.subheader("Record Detail")
        selected_idx = st.selectbox(
            "Select record to inspect",
            range(len(records)),
            format_func=lambda i: f"{records[i].get('record_type', '')} -- {str(records[i].get('timestamp', ''))[:19]}",
        )
        if selected_idx is not None:
            rec = records[selected_idx]
            st.json(rec)
    else:
        st.info("No audit records found matching the filters")

except APIError as exc:
    api_error_box(exc)
