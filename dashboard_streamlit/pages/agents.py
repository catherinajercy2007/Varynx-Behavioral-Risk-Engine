"""Agent Management page."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_agent, register_agent
from components import api_error_box, section_header

section_header("Agent Management", "Register and inspect autonomous AI agents")

# --- Registration form ---
with st.form("register_agent_form"):
    st.subheader("Register New Agent")
    agent_id = st.text_input("Agent ID", placeholder="e.g. agent-prod-001")
    owning_principal = st.text_input("Owning Principal", placeholder="e.g. security-team")
    declared_caps = st.text_input(
        "Declared Capability Scope (comma-separated)",
        placeholder="READ, WRITE",
        help="Action types this agent is declared to perform",
    )
    authorized_resources = st.text_input(
        "Authorized Resource Scope (comma-separated)",
        placeholder="/data, /tmp",
        help="Resource roots this agent is authorized to access",
    )
    submitted = st.form_submit_button("Register Agent", type="primary")

if submitted:
    if not agent_id or not owning_principal:
        st.error("Agent ID and Owning Principal are required")
    else:
        caps = [c.strip() for c in declared_caps.split(",") if c.strip()] if declared_caps else []
        resources = [r.strip() for r in authorized_resources.split(",") if r.strip()] if authorized_resources else []
        try:
            with st.spinner("Registering agent..."):
                result = register_agent(agent_id, owning_principal, caps, resources)
            st.success(f"Agent '{agent_id}' registered successfully")
            st.json(result)
        except APIError as exc:
            api_error_box(exc)

st.divider()

# --- Agent lookup ---
section_header("Agent Lookup")
lookup_id = st.text_input("Agent ID to inspect", key="lookup_agent_id")
if lookup_id:
    try:
        with st.spinner("Fetching agent..."):
            agent = get_agent(lookup_id)
        st.subheader(f"Agent: {lookup_id}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Owning Principal:** {agent.get('owning_principal', 'N/A')}")
            st.markdown(f"**Registered At:** {agent.get('registered_at', 'N/A')}")
            st.markdown(f"**Scope Escalation Count:** {agent.get('scope_escalation_count', 0)}")
        with col2:
            st.markdown("**Declared Capability Scope:**")
            for cap in agent.get("declared_capability_scope", []):
                st.markdown(f"- {cap}")
            st.markdown("**Authorized Resource Scope:**")
            for res in agent.get("authorized_resource_scope", []):
                st.markdown(f"- {res}")
    except APIError as exc:
        api_error_box(exc)
