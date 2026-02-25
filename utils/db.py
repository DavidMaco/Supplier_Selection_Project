"""
AEGIS — Shared database connection helper for Streamlit pages.
Provides a cached engine and a connection-test function so every page
can degrade gracefully when MySQL is unreachable.
"""

import streamlit as st
from sqlalchemy import create_engine, text
import config


@st.cache_resource(show_spinner=False)
def get_engine():
    """Return a SQLAlchemy engine (cached once per Streamlit session)."""
    return create_engine(
        config.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 5},
    )


def check_connection(engine=None) -> bool:
    """Return True if the database is reachable, False otherwise."""
    eng = engine or get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def show_connection_error():
    """Display a standard error banner when the DB is offline."""
    st.error("Database connection is not available.")
    _masked = config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else "not set"
    st.info(
        f"**Target:** `{_masked}`\n\n"
        "**Local:** run `python run_aegis_pipeline.py` first.\n\n"
        "**Streamlit Cloud:** add your MySQL credentials in "
        "**App Settings → Secrets** (see `.streamlit/secrets.toml.example`)."
    )
