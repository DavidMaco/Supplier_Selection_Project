"""
AEGIS — Adaptive Engine for Global Intelligent Sourcing
Main Streamlit Application
"""

import streamlit as st

st.set_page_config(
    page_title="AEGIS — Procurement Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Authentication Gate ─────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.auth import login_gate

if not login_gate():
    st.stop()

# ─── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; max-width: 1400px; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
    .stMetric label { font-size: 0.85rem; color: #6c757d; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; }
    div[data-testid="stSidebar"] { background: linear-gradient(180deg, #1a1a2e, #16213e); }
    div[data-testid="stSidebar"] .stMarkdown { color: #e0e0e0; }
    h1, h2, h3 { color: #1a1a2e; }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar Navigation ─────────────────────────────────────────────
st.sidebar.image("https://via.placeholder.com/250x80/1a1a2e/e0e0e0?text=AEGIS",
                 use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")

# Data freshness indicator
try:
    from utils.freshness import freshness_badge

    @st.cache_data(ttl=120, show_spinner=False)
    def _cached_freshness():
        return freshness_badge()

    st.sidebar.markdown(f"**Data:** {_cached_freshness()}")
except Exception:
    pass

# Version
st.sidebar.markdown("---")
if st.sidebar.button("🔒 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()
st.sidebar.caption("AEGIS v1.0.0 · © 2025")


# ─── Landing Page ────────────────────────────────────────────────────
st.title("🛡️ AEGIS — Procurement Intelligence Platform")
st.markdown("""
**Adaptive Engine for Global Intelligent Sourcing**

> Investment-grade procurement analytics platform combining MCDA supplier
> selection, Monte Carlo risk simulation, ESG compliance tracking, and
> should-cost modelling across a 40+ table normalized schema.
""")

st.markdown("---")

# Key metrics from database
from sqlalchemy import text
from utils.db import get_engine
import config


@st.cache_data(ttl=300, show_spinner=False)
def _load_landing_stats():
    """Load all KPI stats in a single query (cached 5 min)."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT "
            "(SELECT COUNT(*) FROM suppliers WHERE status='Active'),"
            "(SELECT COUNT(*) FROM purchase_orders),"
            "(SELECT COALESCE(SUM(line_total),0) FROM po_line_items),"
            "(SELECT COUNT(DISTINCT country_id) FROM suppliers),"
            "(SELECT COUNT(*) FROM shipments),"
            "(SELECT COUNT(*) FROM materials)"
        )).fetchone()
    return {
        "suppliers": row[0], "pos": row[1], "spend": float(row[2]),
        "countries": row[3], "shipments": row[4], "materials": row[5],
    }


_db_available = False

try:
    stats = _load_landing_stats()

    row1 = st.columns(3)
    row1[0].metric("Active Suppliers", f"{stats['suppliers']:,}")
    row1[1].metric("Purchase Orders", f"{stats['pos']:,}")
    row1[2].metric("Total Spend", f"${stats['spend']:,.0f}")
    row2 = st.columns(3)
    row2[0].metric("Countries", stats["countries"])
    row2[1].metric("Shipments", f"{stats['shipments']:,}")
    row2[2].metric("Materials", stats["materials"])
    _db_available = True

except Exception as e:
    st.warning("Database connection is not available.")
    with st.expander("Connection details"):
        _masked_url = config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else "not configured"
        st.code(f"Target: {_masked_url}")
        if os.getenv("AEGIS_DEBUG", "false").lower() in ("1", "true", "yes"):
            st.text(f"Error: {e}")

    st.info(
        "**Local setup:** Run `python run_aegis_pipeline.py` to initialize the database.\n\n"
        "**Streamlit Cloud:** Add your MySQL connection details in "
        "**App Settings → Secrets** using this format:\n"
        "```toml\n"
        "[database]\n"
        "DB_HOST = \"your-mysql-host.example.com\"\n"
        "DB_PORT = \"3306\"\n"
        "DB_USER = \"aegis_user\"\n"
        "DB_PASSWORD = \"your-password\"\n"
        "DB_NAME = \"aegis_procurement\"\n"
        "```"
    )

st.markdown("---")

# Navigation cards
st.subheader("📊 Analytics Modules")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    #### 🏆 Supplier Scorecards
    MCDA-based ranking using TOPSIS, PROMETHEE, or WSM.
    7-dimension weighted scoring with AHP weights.
    """)
    st.markdown("""
    #### ⚡ Risk Radar
    7-dimension risk assessment across all suppliers.
    Real-time composite risk with tier classification.
    """)

with col2:
    st.markdown("""
    #### 🎲 Monte Carlo Lab
    FX, lead-time, disruption, and cost simulations.
    10,000-path GBM with VaR/CVaR reporting.
    """)
    st.markdown("""
    #### 📊 Concentration Analysis
    HHI calculation across 5 dimensions.
    Geographic, supplier, and currency diversification.
    """)

with col3:
    st.markdown("""
    #### 🌍 Carbon Dashboard
    GHG Protocol Scope 3 emissions tracking.
    Mode-shifting opportunities and reduction targets.
    """)
    st.markdown("""
    #### 💰 Should-Cost Model
    Bottom-up cost estimation with leakage detection.
    Material, freight, customs, overhead decomposition.
    """)

st.markdown("---")
st.markdown("""
#### 🔗 Additional Modules
- **Working Capital** — DPO trends, early payment optimization
- **ESG Compliance** — EcoVadis-style ratings, OECD due diligence
- **Scenario Planner** — What-if analysis for sourcing decisions
- **Data Explorer** — Direct SQL access to all 40+ tables
- **Settings** — MCDA weights, risk thresholds, FX config
""")
