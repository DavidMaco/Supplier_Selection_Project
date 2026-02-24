"""
AEGIS — Dashboard Authentication Gate
Simple password-based login using Streamlit session state.
Credentials are configured via environment variables or config.py.
"""

import os
import hashlib
import streamlit as st

# Default credentials (override via env vars for production)
_DEFAULT_USER = "admin"
_DEFAULT_HASH = hashlib.sha256("aegis2025".encode()).hexdigest()

DASHBOARD_USER = os.getenv("AEGIS_DASHBOARD_USER", _DEFAULT_USER)
DASHBOARD_PASS_HASH = os.getenv(
    "AEGIS_DASHBOARD_PASS_HASH", _DEFAULT_HASH
)


def _check_password(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == DASHBOARD_PASS_HASH


def login_gate() -> bool:
    """
    Show a login form if the user is not yet authenticated.
    Returns True if authenticated, False otherwise (page should stop).
    """
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<div style='text-align:center; padding-top: 60px;'>"
        "<h1>🛡️ AEGIS</h1>"
        "<p style='color:#6c757d;'>Procurement Intelligence Platform</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", type="primary",
                                              use_container_width=True)

            if submitted:
                if username == DASHBOARD_USER and _check_password(password):
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = username
                    st.rerun()
                else:
                    st.error("Invalid credentials. Default: admin / aegis2025")

        st.caption("Set `AEGIS_DASHBOARD_USER` and `AEGIS_DASHBOARD_PASS_HASH` "
                   "env vars in production.")
    return False
