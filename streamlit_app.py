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

# Version
st.sidebar.markdown("---")
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
from sqlalchemy import create_engine, text
import config

ENGINE = create_engine(config.DATABASE_URL, echo=False)

try:
    with ENGINE.connect() as conn:
        stats = {}
        stats["suppliers"] = conn.execute(text(
            "SELECT COUNT(*) FROM suppliers WHERE status='Active'")).scalar() or 0
        stats["pos"] = conn.execute(text(
            "SELECT COUNT(*) FROM purchase_orders")).scalar() or 0
        stats["spend"] = conn.execute(text(
            "SELECT COALESCE(SUM(li.line_total), 0) FROM po_line_items li"
        )).scalar() or 0
        stats["countries"] = conn.execute(text(
            "SELECT COUNT(DISTINCT country_id) FROM suppliers")).scalar() or 0
        stats["shipments"] = conn.execute(text(
            "SELECT COUNT(*) FROM shipments")).scalar() or 0
        stats["materials"] = conn.execute(text(
            "SELECT COUNT(*) FROM materials")).scalar() or 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Active Suppliers", f"{stats['suppliers']:,}")
    col2.metric("Purchase Orders", f"{stats['pos']:,}")
    col3.metric("Total Spend", f"${stats['spend']:,.0f}")
    col4.metric("Countries", stats["countries"])
    col5.metric("Shipments", f"{stats['shipments']:,}")
    col6.metric("Materials", stats["materials"])

except Exception as e:
    st.warning(f"Database connection pending. Run the pipeline first. ({e})")
    st.info("Run: `python run_aegis_pipeline.py` to initialize the database.")

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
