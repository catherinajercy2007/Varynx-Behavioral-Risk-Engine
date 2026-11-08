"""Reusable Streamlit UI components."""
from __future__ import annotations

import streamlit as st


def metric_card(label: str, value, help_text: str | None = None) -> None:
    """Render a compact metric card."""
    st.metric(label=label, value=value, help=help_text)


def status_badge(label: str, status: str) -> str:
    """Return an HTML span with colored text for status display."""
    color = {
        "healthy": "#00e676",
        "unhealthy": "#ff5252",
        "warning": "#ffb74d",
        "info": "#00d4ff",
        "active": "#00e676",
        "suspended": "#ffb74d",
        "revoked": "#ff5252",
        "expired": "#ff5252",
    }.get(status.lower(), "#8b95a8")
    return f'<span style="color:{color};font-weight:600">{label}</span>'


def api_error_box(exc) -> None:
    """Display an API error in a styled error box."""
    st.error(f"API Error {getattr(exc, 'status_code', '?')}: {exc}", icon="🚨")


def empty_state(message: str) -> None:
    """Display an empty state message."""
    st.info(message, icon="📭")


def loading_spinner(message: str = "Loading..."):
    """Return a spinner context manager."""
    return st.spinner(message)


def section_header(title: str, subtitle: str | None = None) -> None:
    """Render a section header with optional subtitle."""
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
