"""
AEGIS — Page 2: Supplier Scorecards
MCDA-based ranking with interactive weight adjustment.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from sqlalchemy import text
from utils.db import get_engine
import config

st.set_page_config(page_title="AEGIS · Supplier Scorecards", layout="wide")
ENGINE = get_engine()

st.title("🏆 Supplier Scorecards")
st.markdown("MCDA-based supplier ranking with adjustable AHP weights")

# ─── Sidebar Controls ───────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ MCDA Settings")
    method = st.selectbox("Methodology", ["TOPSIS", "PROMETHEE", "WSM"])
    year = st.selectbox("Year", [2025, 2024, 2023, 2022], index=0)

    st.markdown("---")
    st.subheader("📊 Weight Adjustment")
    st.caption("Drag sliders to adjust criteria weights (auto-normalized)")

    w_cost = st.slider("Cost", 0, 100, 20)
    w_quality = st.slider("Quality", 0, 100, 18)
    w_delivery = st.slider("Delivery", 0, 100, 15)
    w_risk = st.slider("Risk", 0, 100, 15)
    w_esg = st.slider("ESG", 0, 100, 12)
    w_innovation = st.slider("Innovation", 0, 100, 10)
    w_financial = st.slider("Financial Health", 0, 100, 10)

    total = w_cost + w_quality + w_delivery + w_risk + w_esg + w_innovation + w_financial
    if total > 0:
        weights = {
            "cost": w_cost/total, "quality": w_quality/total,
            "delivery": w_delivery/total, "risk": w_risk/total,
            "esg": w_esg/total, "innovation": w_innovation/total,
            "compliance": w_financial/total,
        }
    else:
        weights = config.MCDA_DEFAULT_WEIGHTS

    run_btn = st.button("🔄 Run MCDA", type="primary", use_container_width=True)

# ─── Run or Load Results ─────────────────────────────────────────
if run_btn:
    with st.spinner(f"Running {method} analysis..."):
        from analytics.mcda_engine import run_mcda
        df = run_mcda(method, year, custom_weights=weights)
        st.success(f"✓ {method} completed — {len(df)} suppliers scored")
else:
    # Load latest from DB
    try:
        with ENGINE.connect() as conn:
            df = pd.read_sql(text("""
                SELECT sc.*, s.supplier_name
                FROM supplier_scorecards sc
                JOIN suppliers s ON sc.supplier_id = s.supplier_id
                WHERE sc.scorecard_id IN (
                    SELECT MAX(scorecard_id) FROM supplier_scorecards
                    GROUP BY supplier_id
                )
                ORDER BY sc.`rank`
            """), conn)
    except Exception:
        df = pd.DataFrame()

if df is not None and not df.empty:
    # ─── Summary Metrics ────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Suppliers Scored", len(df))
    c2.metric("Avg Score", f"{df['composite_score'].mean():.1f}")
    strategic = len(df[df["tier_recommendation"] == "Strategic"])
    c3.metric("Strategic Tier", strategic)
    blocked = len(df[df["tier_recommendation"] == "Blocked"])
    c4.metric("Blocked/Conditional", blocked + len(df[df["tier_recommendation"] == "Conditional"]))

    st.markdown("---")

    # ─── Rankings Table (full width) ─────────────────────────────
    st.subheader("📋 Supplier Rankings")
    display_cols = ["rank", "supplier_name", "composite_score",
                   "cost_score", "quality_score", "delivery_score",
                   "risk_score", "esg_score", "tier_recommendation"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available].style.background_gradient(
            subset=["composite_score"], cmap="RdYlGn", vmin=0, vmax=100),
        use_container_width=True, hide_index=True, height=450)

    # ─── Tier Distribution + Top Supplier Radar (side by side) ──
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🎯 Tier Distribution")
        tier_counts = df["tier_recommendation"].value_counts().reset_index()
        tier_counts.columns = ["Tier", "Count"]
        fig = px.pie(tier_counts, values="Count", names="Tier",
                     color="Tier",
                     color_discrete_map={
                         "Strategic": "#1a9850", "Preferred": "#91cf60",
                         "Approved": "#fee08b", "Conditional": "#fc8d59",
                         "Blocked": "#d73027"})
        fig.update_layout(height=380, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Radar chart for top supplier
        if len(df) > 0:
            top = df.iloc[0]
            st.subheader(f"🏅 Top Supplier: {top.get('supplier_name', 'N/A')}")
            dims = ["cost_score", "quality_score", "delivery_score",
                    "risk_score", "esg_score", "innovation_score", "financial_score"]
            available_dims = [d for d in dims if d in df.columns]
            if available_dims:
                vals = [float(top[d]) for d in available_dims]
                labels = [d.replace("_score", "").title() for d in available_dims]
                fig = go.Figure(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=labels + [labels[0]],
                    fill="toself", name=top.get("supplier_name", "Top")))
                fig.update_layout(
                    polar=dict(radialaxis=dict(range=[0, 100])),
                    height=380, margin=dict(t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)

    # ─── Score Distribution ─────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Score Distribution")
    fig = px.histogram(df, x="composite_score", nbins=20,
                       color="tier_recommendation",
                       color_discrete_map={
                           "Strategic": "#1a9850", "Preferred": "#91cf60",
                           "Approved": "#fee08b", "Conditional": "#fc8d59",
                           "Blocked": "#d73027"},
                       title="Composite Score Distribution")
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No scorecard data. Click **Run MCDA** to generate supplier rankings.")
