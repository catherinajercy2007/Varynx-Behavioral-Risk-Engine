"""Agent Details page -- full security profile."""
from __future__ import annotations

import streamlit as st
from api_client import APIError, get_agent_profile
from components import api_error_box, metric_card, section_header

section_header("Agent Details", "Full security profile including trust state and leases")

agent_id = st.text_input("Agent ID", placeholder="e.g. agent-prod-001")

if agent_id:
    try:
        with st.spinner("Fetching agent profile..."):
            profile = get_agent_profile(agent_id)

        agent = profile.get("agent", {})
        trust = profile.get("trust")
        leases = profile.get("leases", [])

        # Agent identity
        st.subheader("Agent Identity")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Agent ID:** {agent.get('agent_id', 'N/A')}")
        with col2:
            st.markdown(f"**Owning Principal:** {agent.get('owning_principal', 'N/A')}")
        with col3:
            st.markdown(f"**Escalations:** {agent.get('scope_escalation_count', 0)}")

        st.markdown("**Declared Capability Scope:**")
        caps = agent.get("declared_capability_scope", [])
        if caps:
            st.markdown(", ".join(caps))
        else:
            st.caption("None declared")

        st.markdown("**Authorized Resource Scope:**")
        resources = agent.get("authorized_resource_scope", [])
        if resources:
            st.markdown(", ".join(resources))
        else:
            st.caption("None authorized")

        st.divider()

        # Trust state
        st.subheader("Trust State")
        if trust:
            col1, col2, col3 = st.columns(3)
            with col1:
                metric_card("Current Score", f"{trust.get('current_score', 0):.3f}")
            with col2:
                metric_card("Trust Level", trust.get("level", "N/A"))
            with col3:
                metric_card("History Entries", len(trust.get("history", [])))

            history = trust.get("history", [])
            if history:
                with st.expander(f"Trust History ({len(history)} entries)"):
                    for i, entry in enumerate(history[-10:]):
                        st.markdown(
                            f"- **{entry.get('timestamp', '')[:19]}**: "
                            f"score {entry.get('new_score', 0):.3f} "
                            f"(delta {entry.get('delta', 0):+.3f})"
                        )
        else:
            st.info("No trust state -- agent has not been observed by the pipeline yet")

        st.divider()

        # Leases
        st.subheader(f"Capability Leases ({len(leases)})")
        if leases:
            for lease in leases:
                state = lease.get("state", "UNKNOWN")
                color = {"ACTIVE": "#00e676", "SUSPENDED": "#ffb74d",
                         "REVOKED": "#ff5252", "EXPIRED": "#ff5252"}.get(state, "#8b95a8")
                with st.expander(f"{lease.get('capability', 'N/A')} -- {state}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Lease ID:** {lease.get('lease_id', 'N/A')[:36]}")
                        st.markdown(f"**Capability:** {lease.get('capability', 'N/A')}")
                        st.markdown(f"**State:** <span style='color:{color};font-weight:600'>{state}</span>",
                                    unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"**Activated:** {str(lease.get('activation_timestamp', ''))[:19]}")
                        st.markdown(f"**Expires:** {str(lease.get('expiry_timestamp', 'None'))[:19]}")
                        st.markdown(f"**Issuing Principal:** {lease.get('issuing_principal', 'N/A')}")
                    scope = lease.get("resource_scope", {})
                    if scope and scope.get("resources"):
                        st.markdown(f"**Resource Scope:** {', '.join(scope['resources'])}")
                    else:
                        st.markdown("**Resource Scope:** {} (deny-all)")
        else:
            st.info("No capability leases for this agent")

    except APIError as exc:
        api_error_box(exc)
