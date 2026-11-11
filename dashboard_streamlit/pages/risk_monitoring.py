
"""Risk Decision Monitoring and Security Event Submission."""

from __future__ import annotations

import json

import streamlit as st

from api_client import (
    APIError,
    get_audit_records,
    submit_event,
)
from components import api_error_box, metric_card, section_header


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def safe_dict(value):
    """Return a dictionary even if the backend field is malformed."""
    return value if isinstance(value, dict) else {}


def display_timestamp(record):
    return str(record.get("timestamp") or "Timestamp unavailable")


def display_record_details(record, title):
    payload = safe_dict(record.get("payload"))

    with st.container(border=True):
        left, right = st.columns([3, 1])

        with left:
            st.markdown(f"**{title}**")
            st.caption(
                f"Agent: {record.get('agent_id') or 'N/A'}"
            )

        with right:
            st.caption(display_timestamp(record))

        if payload:
            st.json(payload)
        else:
            st.caption("No additional payload information.")


# -------------------------------------------------------------------
# Page heading
# -------------------------------------------------------------------

section_header(
    "Risk Decision Monitoring",
    "Submit security events and monitor behavioral decisions "
    "and enforcement outcomes.",
)


# -------------------------------------------------------------------
# Event submission panel
# -------------------------------------------------------------------

st.subheader("Submit Security Event")

st.caption(
    "Send a security event to the Varynx backend. "
    "The backend is responsible for evaluating the event and "
    "generating any applicable recommendations and audit records."
)

with st.form("varynx_security_event_form", clear_on_submit=False):

    col1, col2 = st.columns(2)

    with col1:
        agent_id = st.text_input(
            "Agent ID",
            placeholder="e.g. varynx-finance-agent-002",
            help="Enter an agent ID that is already registered.",
        )

    with col2:
        session_id = st.text_input(
            "Session ID",
            placeholder="Enter an active session ID",
            help="Enter a session associated with this agent.",
        )

    col3, col4 = st.columns(2)

    with col3:
        action_type = st.selectbox(
            "Action Type",
            options=[
                "READ",
                "WRITE",
                "DELETE",
                "EXECUTE",
                "UPDATE",
                "CREATE",
            ],
        )

    with col4:
        capability = st.selectbox(
            "Requested Capability",
            options=[
                "READ",
                "WRITE",
                "DELETE",
                "EXECUTE",
            ],
        )

    target_resource = st.text_input(
        "Target Resource",
        placeholder="/finance/budget.csv",
        help="Enter the resource path the agent is attempting to access.",
    )

    authorization_result = st.selectbox(
        "Authorization Result",
        options=["allowed", "denied"],
        help=(
            "This is the authorization result supplied with the event. "
            "It is not the final behavioral risk decision."
        ),
    )

    is_simulated = st.checkbox(
        "Mark this event as simulated",
        value=True,
        help=(
            "Keep enabled for controlled demonstration and testing. "
            "Disable only when submitting a genuine event."
        ),
    )

    submitted = st.form_submit_button(
        "Submit Security Event",
        type="primary",
        use_container_width=True,
    )

    if submitted:
        missing = []

        if not agent_id.strip():
            missing.append("Agent ID")

        if not session_id.strip():
            missing.append("Session ID")

        if not target_resource.strip():
            missing.append("Target Resource")

        if missing:
            st.error(
                "Complete the following required fields: "
                + ", ".join(missing)
            )

        else:
            try:
                with st.spinner("Submitting event to Varynx backend..."):
                    result = submit_event(
                        agent_id=agent_id.strip(),
                        session_id=session_id.strip(),
                        action_type=action_type,
                        capability=capability,
                        target_resource=target_resource.strip(),
                        authorization_result=authorization_result,
                        is_simulated=is_simulated,
                    )

                # Preserve the real backend response across reruns.
                st.session_state["varynx_last_event_result"] = result
                st.session_state["varynx_last_event_error"] = None

                st.success("Security event submitted successfully.")

                # Refresh the page so audit records are fetched again.
                st.rerun()

            except APIError as exc:
                st.session_state["varynx_last_event_error"] = (
                    exc.status_code,
                    exc.message,
                )
                st.error(
                    f"Event submission failed "
                    f"(HTTP {exc.status_code}): {exc.message}"
                )


# -------------------------------------------------------------------
# Last event submission response
# -------------------------------------------------------------------

last_result = st.session_state.get("varynx_last_event_result")

if last_result is not None:
    with st.expander("Last Event Submission Response", expanded=True):
        st.json(last_result)

last_error = st.session_state.get("varynx_last_event_error")

if last_error:
    status_code, message = last_error
    st.warning(
        f"Previous submission error (HTTP {status_code}): {message}"
    )


st.divider()


# -------------------------------------------------------------------
# Risk monitoring and audit records
# -------------------------------------------------------------------

st.subheader("Security Decision Overview")

refresh_col, info_col = st.columns([1, 3])

with refresh_col:
    refresh_clicked = st.button(
        "Refresh Audit Records",
        use_container_width=True,
    )

with info_col:
    st.caption(
        "Decisions are reconstructed from backend audit records. "
        "This page does not invent decisions when records are absent."
    )

if refresh_clicked:
    st.rerun()


try:
    with st.spinner("Fetching recent audit records..."):
        data = get_audit_records(limit=100)

    if not isinstance(data, dict):
        st.error(
            "Unexpected audit API response. "
            "Expected an object containing audit records."
        )
        st.stop()

    records = data.get("records", [])

    if not isinstance(records, list):
        st.error("The audit API returned an invalid records field.")
        st.stop()

    response_recs = [
        record for record in records
        if isinstance(record, dict)
        and record.get("record_type") == "RESPONSE_RECOMMENDED"
    ]

    enforcement_recs = [
        record for record in records
        if isinstance(record, dict)
        and record.get("record_type") == "ENFORCEMENT_APPLIED"
    ]

    total_count = data.get("count", len(records))

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("Total Audit Records", total_count)

    with col2:
        metric_card(
            "Response Recommendations",
            len(response_recs),
        )

    with col3:
        metric_card(
            "Enforcement Actions",
            len(enforcement_recs),
        )

    st.divider()

    # ---------------------------------------------------------------
    # Recent recommendations
    # ---------------------------------------------------------------

    st.subheader("Recent Security Decisions")

    if response_recs:
        for index, record in enumerate(response_recs[-15:]):
            payload = safe_dict(record.get("payload"))

            response_type = payload.get(
                "response_type",
                "UNKNOWN",
            )

            reason_codes = payload.get("reason_codes", [])

            with st.container(border=True):
                st.markdown(f"**{response_type}**")
                st.caption(
                    f"Agent: {record.get('agent_id') or 'N/A'}"
                    f" | {display_timestamp(record)}"
                )

                if isinstance(reason_codes, list) and reason_codes:
                    st.write(
                        "Reason codes: "
                        + ", ".join(map(str, reason_codes))
                    )

                with st.expander(
                    f"View recommendation details #{index + 1}"
                ):
                    st.json(record)

    else:
        st.info(
            "No response recommendations were found in the "
            "recent audit records. Submit an event and verify "
            "that the backend generates a recommendation."
        )

    st.divider()

    # ---------------------------------------------------------------
    # Recent enforcement actions
    # ---------------------------------------------------------------

    st.subheader("Recent Enforcement Actions")

    if enforcement_recs:
        for index, record in enumerate(enforcement_recs[-10:]):
            payload = safe_dict(record.get("payload"))

            outcome = payload.get("outcome", "UNKNOWN")
            action = payload.get("action", "N/A")

            with st.container(border=True):
                st.markdown(f"**{outcome}**")
                st.caption(
                    f"Action: {action}"
                    f" | Agent: {record.get('agent_id') or 'N/A'}"
                )
                st.caption(display_timestamp(record))

                with st.expander(
                    f"View enforcement details #{index + 1}"
                ):
                    st.json(record)

    else:
        st.info(
            "No enforcement actions were found in the recent "
            "audit records. A submitted event does not guarantee "
            "that an enforcement action will be generated."
        )

except APIError as exc:
    api_error_box(exc)

except Exception as exc:
    st.error("Unexpected error while loading risk monitoring data.")
    st.exception(exc)
