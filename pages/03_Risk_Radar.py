"""
AEGIS — Page 3: Risk Radar
7-dimension supplier risk heatmap and drill-down.
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

st.set_page_config(page_title="AEGIS · Risk Radar", layout="wide")
ENGINE = get_engine()

st.title("⚡ Risk Radar")

with st.sidebar:
    st.subheader("⚙️ Controls")
    if st.button("🔄 Refresh Risk Scores", type="primary", use_container_width=True):
        with st.spinner("Computing risk scores..."):
            from analytics.risk_scoring import run_risk_scoring
            run_risk_scoring()
            st.success("✓ Risk scores updated")

    risk_filter = st.multiselect(
        "Risk Tier Filter",
        ["Low", "Medium", "High", "Critical"],
        default=["Low", "Medium", "High", "Critical"])

try:
    with ENGINE.connect() as conn:
        df = pd.read_sql(text("""
            SELECT ra.*, s.supplier_name, s.tier_level, c.country_name, c.region
            FROM risk_assessments ra
            JOIN suppliers s ON ra.supplier_id = s.supplier_id
            LEFT JOIN countries c ON s.country_id = c.country_id
            WHERE ra.risk_assessment_id IN (
                SELECT MAX(risk_assessment_id) FROM risk_assessments
                GROUP BY supplier_id
            )
            ORDER BY ra.composite_risk DESC
        """), conn)

    if not df.empty:
        df = df[df["risk_tier"].isin(risk_filter)]

        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suppliers Assessed", len(df))
        c2.metric("Avg Risk Score", f"{df['composite_risk'].mean():.1f}")
        critical = len(df[df["risk_tier"] == "Critical"])
        c3.metric("Critical Risk", critical, delta=f"{'⚠️' if critical > 0 else '✅'}")
        high = len(df[df["risk_tier"] == "High"])
        c4.metric("High Risk", high)

        st.markdown("---")

        # ── Heatmap (full width) ──────────────────────────────────
        st.subheader("🗺️ Risk Heatmap")
        risk_dims = ["financial_risk", "operational_risk", "geopolitical_risk",
                    "compliance_risk", "concentration_risk", "esg_risk", "cyber_risk"]
        heatmap_data = df.set_index("supplier_name")[risk_dims].head(20)
        heatmap_data.columns = [c.replace("_risk", "").title() for c in risk_dims]

        fig = px.imshow(
            heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            color_continuous_scale="RdYlGn_r",
            aspect="auto",
            title="Risk Heatmap (Top 20 Riskiest)")
        fig.update_layout(height=550, margin=dict(l=180))
        st.plotly_chart(fig, use_container_width=True)

        # ── Tier Distribution + Region Risk (side by side) ────────
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("🎯 Risk Tier Distribution")
            tier_ct = df["risk_tier"].value_counts().reset_index()
            tier_ct.columns = ["Tier", "Count"]
            fig = px.pie(tier_ct, values="Count", names="Tier",
                        color="Tier",
                        color_discrete_map={
                            "Low": "#1a9850", "Medium": "#fee08b",
                            "High": "#fc8d59", "Critical": "#d73027"})
            fig.update_layout(height=350, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("🌍 Risk by Region")
            by_region = df.groupby("region")["composite_risk"].mean().reset_index()
            by_region = by_region.sort_values("composite_risk", ascending=False)
            fig = px.bar(by_region, x="region", y="composite_risk",
                        color="composite_risk",
                        color_continuous_scale="RdYlGn_r")
            fig.update_layout(height=350, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # Detailed table
        st.markdown("---")
        st.subheader("📋 Detailed Risk Scores")
        display = ["supplier_name", "country_name", "tier_level",
                   "composite_risk", "risk_tier"] + risk_dims
        available = [c for c in display if c in df.columns]
        st.dataframe(
            df[available].style.background_gradient(
                subset=["composite_risk"], cmap="RdYlGn_r", vmin=0, vmax=100),
            use_container_width=True, hide_index=True)

        # Drill-down
        st.markdown("---")
        st.subheader("🔍 Supplier Risk Drill-Down")
        selected = st.selectbox("Select Supplier",
                               df["supplier_name"].tolist())
        if selected:
            row = df[df["supplier_name"] == selected].iloc[0]
            dims = [d.replace("_risk", "").title() for d in risk_dims]
            vals = [float(row[d]) for d in risk_dims]

            fig = go.Figure(go.Scatterpolar(
                r=vals + [vals[0]],
                theta=dims + [dims[0]],
                fill="toself"))
            fig.update_layout(
                polar=dict(radialaxis=dict(range=[0, 100])),
                title=f"Risk Profile: {selected} (Composite: {row['composite_risk']:.1f})",
                height=400)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No risk data. Click **Refresh Risk Scores** to compute.")

except Exception as e:
    st.error(f"Database error: {e}")
