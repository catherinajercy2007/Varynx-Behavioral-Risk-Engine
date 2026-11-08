"""Varynx Behavioral Risk Control Engine -- Streamlit Dashboard.

Entry point. Run with:
    streamlit run dashboard_streamlit/app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Add dashboard_streamlit/ to sys.path so pages can import api_client etc.
_DASH_DIR = Path(__file__).resolve().parent
if str(_DASH_DIR) not in sys.path:
    sys.path.insert(0, str(_DASH_DIR))

from api_client import APIError, get_health  # noqa: E402
from styles import apply_dark_theme  # noqa: E402

st.set_page_config(
    page_title="Varynx Security Dashboard",
    page_icon=":shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_dark_theme()

st.sidebar.markdown("# :shield: Varynx")
st.sidebar.caption("Behavioral Risk Control Engine")

PAGES = {
    "Security Overview": "pages/overview.py",
    "Agent Management": "pages/agents.py",
    "Agent Details": "pages/agent_details.py",
    "Risk Monitoring": "pages/risk_monitoring.py",
    "Audit Trail": "pages/audit.py",
    "System Health": "pages/system_health.py",
}

selection = st.sidebar.radio("Navigate", list(PAGES.keys()))
st.sidebar.divider()

api_url = os.environ.get("VARYNX_API_URL", "http://127.0.0.1:8000/api/v1")
st.sidebar.caption(f"API: {api_url}")

try:
    get_health()
    st.sidebar.markdown(
        '<span style="color:#00e676">&#9679; Backend connected</span>',
        unsafe_allow_html=True,
    )
except APIError:
    st.sidebar.markdown(
        '<span style="color:#ff5252">&#9679; Backend offline</span>',
        unsafe_allow_html=True,
    )

st.sidebar.divider()
st.sidebar.caption("Phase 1 MVP | Research Platform")

# Dispatch to selected page using absolute path (works from any cwd)
page_abs = _DASH_DIR / PAGES[selection]
page_src = page_abs.read_text(encoding="utf-8")
exec(compile(page_src, str(page_abs), "exec"), globals())  # noqa: S102
