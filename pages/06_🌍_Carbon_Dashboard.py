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
                   SUM(co2e_kg) AS total_kg,
                   AVG(co2e_kg / NULLIF(distance_km * weight_tonnes, 0)) AS avg_intensity
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
                   SUM(co2e_kg) AS kg_co2,
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
            SELECT s.supplier_name,
                   SUM(ce.co2e_kg) AS total_kg,
                   AVG(ce.co2e_kg / NULLIF(ce.distance_km * ce.weight_tonnes, 0)) AS intensity,
                   COUNT(*) AS shipments
            FROM carbon_estimates ce
            JOIN shipments sh ON sh.shipment_id = ce.shipment_id
            JOIN purchase_orders po ON po.po_id = sh.po_id
            JOIN suppliers s ON s.supplier_id = po.supplier_id
            GROUP BY s.supplier_name
            ORDER BY total_kg DESC LIMIT 15
        """)).mappings().fetchall())

    if not sup_df.empty:
        fig = px.bar(sup_df, x="supplier_name", y="total_kg",
                    color="intensity",
                    color_continuous_scale="RdYlGn_r",
                    title="Top 15 Suppliers by CO₂ Emissions")
        fig.update_layout(xaxis_tickangle=-45, height=450,
                         margin=dict(b=120))
        st.plotly_chart(fig, use_container_width=True)

    # ── Route-level emissions ───────────────────────────────────────
    st.subheader("Top Emitting Routes")
    with ENGINE.connect() as conn:
        route_df = pd.DataFrame(conn.execute(text("""
            SELECT po_orig.port_name AS origin_port,
                   po_dest.port_name AS destination_port,
                   ce.transport_mode,
                   SUM(ce.co2e_kg) AS total_kg,
                   AVG(ce.distance_km) AS avg_dist_km,
                   COUNT(*) AS n
            FROM carbon_estimates ce
            JOIN shipments sh ON sh.shipment_id = ce.shipment_id
            LEFT JOIN ports po_orig ON po_orig.port_id = sh.origin_port_id
            LEFT JOIN ports po_dest ON po_dest.port_id = sh.destination_port_id
            GROUP BY po_orig.port_name, po_dest.port_name, ce.transport_mode
            ORDER BY total_kg DESC LIMIT 15
        """)).mappings().fetchall())

    if not route_df.empty:
        route_df["route"] = route_df["origin_port"] + " → " + route_df["destination_port"]
        fig = px.bar(route_df, x="route", y="total_kg",
                    color="transport_mode",
                    title="Top 15 Routes by Emissions")
        fig.update_layout(xaxis_tickangle=-45, height=450,
                         margin=dict(b=120))
        st.plotly_chart(fig, use_container_width=True)

    # ── Reduction opportunities ─────────────────────────────────────
    st.subheader("🟢 Mode-Shift Reduction Opportunities")
    from analytics.carbon_engine import get_reduction_opportunities
    opps = get_reduction_opportunities()

    if not opps.empty:
        st.dataframe(opps.style.format({
            "current_co2e": "{:,.0f}",
            "sea_co2e": "{:,.0f}",
            "reduction_if_sea": "{:,.0f}",
            "reduction_pct_sea": "{:.0f}%"
        }), use_container_width=True)

        total_savings = opps["reduction_if_sea"].sum()
        st.metric("Total Potential Savings",
                 f"{total_savings/1000:,.1f} tonnes CO₂")
    else:
        st.info("No mode-shift opportunities identified.")

except Exception as e:
    st.error(f"Database error: {e}")
