"""
AEGIS — Page 6: Carbon & Emissions Dashboard
Scope-3 Cat-4 transport emissions, reduction opportunities.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Carbon Dashboard", layout="wide")
st.title("🌍 Carbon & Emissions Dashboard")

ENGINE = get_engine()

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("🔄 Recalculate Emissions"):
        with st.spinner("Running carbon engine..."):
            from analytics.carbon_engine import calculate_emissions
            calculate_emissions()
        st.success("Done")

try:
    with ENGINE.connect() as conn:
        # ── KPI row ─────────────────────────────────────────────────
        kpi = conn.execute(text("""
            SELECT COUNT(*) AS estimates,
                   SUM(estimated_kg_co2) AS total_kg,
                   AVG(carbon_intensity_per_1000usd) AS avg_intensity
            FROM carbon_estimates
        """)).mappings().fetchone()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Estimates", f"{kpi['estimates']:,}")
        c2.metric("Total CO₂ (tonnes)", f"{(kpi['total_kg'] or 0)/1000:,.1f}")
        c3.metric("Avg Intensity (kg/$1k)", f"{(kpi['avg_intensity'] or 0):,.1f}")

    # ── Emissions by transport mode ─────────────────────────────────
    st.subheader("Emissions by Transport Mode")
    with ENGINE.connect() as conn:
        mode_df = pd.DataFrame(conn.execute(text("""
            SELECT transport_mode,
                   SUM(estimated_kg_co2) AS kg_co2,
                   COUNT(*) AS shipments,
                   AVG(distance_km) AS avg_dist
            FROM carbon_estimates
            GROUP BY transport_mode ORDER BY kg_co2 DESC
        """)).mappings().fetchall())

    if not mode_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(mode_df, x="transport_mode", y="kg_co2",
                        color="transport_mode",
                        title="Total CO₂ Emissions by Mode")
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.pie(mode_df, names="transport_mode", values="shipments",
                        title="Shipment Count by Mode")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    # ── Top emitting suppliers ──────────────────────────────────────
    st.subheader("Top Emitting Suppliers")
    with ENGINE.connect() as conn:
        sup_df = pd.DataFrame(conn.execute(text("""
            SELECT s.company_name,
                   SUM(ce.estimated_kg_co2) AS total_kg,
                   AVG(ce.carbon_intensity_per_1000usd) AS intensity,
                   COUNT(*) AS shipments
            FROM carbon_estimates ce
            JOIN shipments sh ON sh.shipment_id = ce.shipment_id
            JOIN purchase_orders po ON po.po_id = sh.po_id
            JOIN suppliers s ON s.supplier_id = po.supplier_id
            GROUP BY s.company_name
            ORDER BY total_kg DESC LIMIT 15
        """)).mappings().fetchall())

    if not sup_df.empty:
        fig = px.bar(sup_df, x="company_name", y="total_kg",
                    color="intensity",
                    color_continuous_scale="RdYlGn_r",
                    title="Top 15 Suppliers by CO₂ Emissions")
        fig.update_layout(xaxis_tickangle=-45, height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Route-level emissions ───────────────────────────────────────
    st.subheader("Top Emitting Routes")
    with ENGINE.connect() as conn:
        route_df = pd.DataFrame(conn.execute(text("""
            SELECT ce.origin_port, ce.destination_port,
                   ce.transport_mode,
                   SUM(ce.estimated_kg_co2) AS total_kg,
                   AVG(ce.distance_km) AS avg_dist_km,
                   COUNT(*) AS n
            FROM carbon_estimates ce
            GROUP BY ce.origin_port, ce.destination_port, ce.transport_mode
            ORDER BY total_kg DESC LIMIT 15
        """)).mappings().fetchall())

    if not route_df.empty:
        route_df["route"] = route_df["origin_port"] + " → " + route_df["destination_port"]
        fig = px.bar(route_df, x="route", y="total_kg",
                    color="transport_mode",
                    title="Top 15 Routes by Emissions")
        fig.update_layout(xaxis_tickangle=-45, height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Reduction opportunities ─────────────────────────────────────
    st.subheader("🟢 Mode-Shift Reduction Opportunities")
    with ENGINE.connect() as conn:
        from analytics.carbon_engine import get_reduction_opportunities
        opps = get_reduction_opportunities()

    if opps:
        opp_df = pd.DataFrame(opps)
        st.dataframe(opp_df.style.format({
            "current_kg_co2": "{:,.0f}",
            "potential_kg_co2": "{:,.0f}",
            "savings_kg_co2": "{:,.0f}",
            "reduction_pct": "{:.0f}%"
        }), use_container_width=True)

        total_savings = sum(o["savings_kg_co2"] for o in opps)
        st.metric("Total Potential Savings",
                 f"{total_savings/1000:,.1f} tonnes CO₂")
    else:
        st.info("No mode-shift opportunities identified.")

except Exception as e:
    st.error(f"Database error: {e}")
