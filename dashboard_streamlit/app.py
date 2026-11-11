
"""Varynx Behavioral Risk Control Engine -- Streamlit Dashboard.

Entry point:
    streamlit run dashboard_streamlit/app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure dashboard modules can be imported from any working directory.
_DASH_DIR = Path(__file__).resolve().parent

if str(_DASH_DIR) not in sys.path:
    sys.path.insert(0, str(_DASH_DIR))

from api_client import APIError, get_health  # noqa: E402
from styles import apply_dark_theme  # noqa: E402


# ---------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Varynx | Security Operations",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_dark_theme()


# ---------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------

st.sidebar.markdown("# 🛡️ Varynx")
st.sidebar.caption("Behavioral Risk Control Engine")

PAGES = {
    "Security Overview": "pages/overview.py",
    "Agent Management": "pages/agents.py",
    "Agent Details": "pages/agent_details.py",
    "Risk Monitoring": "pages/risk_monitoring.py",
    "Audit Trail": "pages/audit.py",
    "System Health": "pages/system_health.py",
}

selection = st.sidebar.radio(
    "Navigation",
    list(PAGES.keys()),
)

st.sidebar.divider()

api_url = os.environ.get(
    "VARYNX_API_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")

st.sidebar.caption(f"Backend endpoint: {api_url}")


# ---------------------------------------------------------------------
# Cached backend connection indicator
# ---------------------------------------------------------------------

try:
    health = get_health()

    if str(health.get("status", "")).lower() == "healthy":
        st.sidebar.markdown(
            '<span style="color:#00e676">'
            '● Backend healthy</span>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<span style="color:#ffb74d">'
            '● Backend responded with a warning</span>',
            unsafe_allow_html=True,
        )

except APIError as exc:
    st.sidebar.markdown(
        '<span style="color:#ff5252">'
        '● Backend unavailable</span>',
        unsafe_allow_html=True,
    )

    st.sidebar.caption(
        f"HTTP {exc.status_code}: {exc.message}"
    )

except Exception:
    st.sidebar.markdown(
        '<span style="color:#ff5252">'
        '● Connection status unavailable</span>',
        unsafe_allow_html=True,
    )


st.sidebar.divider()
st.sidebar.caption("Research Platform | Phase 1 MVP")


# ---------------------------------------------------------------------
# Page dispatch
# ---------------------------------------------------------------------

page_abs = _DASH_DIR / PAGES[selection]

if not page_abs.is_file():
    st.error(f"Dashboard page not found: {PAGES[selection]}")
    st.stop()

page_src = page_abs.read_text(encoding="utf-8")

exec(
    compile(page_src, str(page_abs), "exec"),
    globals(),
)
