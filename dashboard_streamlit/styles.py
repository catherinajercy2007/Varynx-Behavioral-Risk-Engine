"""Custom CSS for the Varynx dashboard -- dark navy cybersecurity theme."""

DARK_CSS = """
<style>
    /* Global background and typography */
    .stApp {
        background-color: #0a0e1a;
        color: #e0e6f0;
    }
    .stApp > header {
        background-color: transparent;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0d1320;
        border-right: 1px solid #1a2235;
    }
    section[data-testid="stSidebar"] .stMarkdown h1 {
        color: #00d4ff;
        font-size: 1.3rem;
        font-weight: 700;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        overflow: hidden;
        min-height: 80px;
    }
    div[data-testid="stMetric"] label {
        color: #8b95a8;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #e0e6f0;
        font-size: clamp(1.1rem, 2vw, 1.6rem);
        font-weight: 700;
        overflow-wrap: break-word;
        word-break: break-word;
        white-space: normal;
        line-height: 1.2;
    }

    /* Dataframes and tables */
    .stDataFrame, .stTable {
        border: 1px solid #1e293b;
        border-radius: 8px;
        overflow: hidden;
    }

    /* Buttons */
    .stButton > button {
        background-color: #00d4ff;
        color: #0a0e1a;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        padding: 8px 24px;
    }
    .stButton > button:hover {
        background-color: #00b4d8;
        color: #0a0e1a;
    }

    /* Status badges */
    .status-healthy {
        color: #00e676;
        font-weight: 600;
    }
    .status-unhealthy {
        color: #ff5252;
        font-weight: 600;
    }
    .status-warning {
        color: #ffb74d;
        font-weight: 600;
    }

    /* Section headers */
    .stMarkdown h2 {
        color: #00d4ff;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 8px;
    }
    .stMarkdown h3 {
        color: #b388ff;
    }

    /* Info boxes */
    .stAlert {
        border-radius: 8px;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background-color: #111827;
        color: #e0e6f0;
        border-radius: 6px;
    }
"""

def apply_dark_theme():
    """Inject the dark CSS into the Streamlit page."""
    import streamlit as st
    st.markdown(DARK_CSS, unsafe_allow_html=True)
