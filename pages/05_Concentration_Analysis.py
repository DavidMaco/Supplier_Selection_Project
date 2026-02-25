"""
AEGIS — Page 5: Concentration Analysis
HHI across supplier, country, currency, material, port dimensions.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Concentration", layout="wide")
st.title("🔎 Concentration & Diversification Analysis")

ENGINE = get_engine()

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    year_filter = st.selectbox("Calendar Year", [2024, 2023, 2022, 2025], index=0)
    if st.button("🔄 Refresh HHI Scores"):
        with st.spinner("Computing..."):
            from analytics.concentration import run_full_concentration_analysis
            run_full_concentration_analysis()
        st.success("Done")

# ── Key metrics ─────────────────────────────────────────────────────
try:
    with ENGINE.connect() as conn:
        rows = conn.execute(text("""
            SELECT dimension, hhi_score, category, top_entity,
                   top_entity_share_pct, entity_count
            FROM concentration_analysis
            WHERE YEAR(calculated_at) = :yr
            ORDER BY calculated_at DESC
            LIMIT 5
        """), {"yr": year_filter}).mappings().fetchall()

    if not rows:
        st.info("No concentration data yet. Click **Refresh HHI Scores** in the sidebar.")
        st.stop()

    df = pd.DataFrame(rows)

    # KPI row
    cols = st.columns(len(df))
    for i, row in df.iterrows():
        color = "🟢" if row["category"] == "Low" else "🟡" if row["category"] == "Moderate" else "🔴"
        cols[i].metric(
            f"{color} {row['dimension']}",
            f"HHI {row['hhi_score']:,.0f}",
            f"Top: {row['top_entity']} ({row['top_entity_share_pct']:.0f}%)")

    # ── HHI bar chart ───────────────────────────────────────────────
    st.subheader("HHI by Dimension")
    fig = go.Figure()
    colors = {"Low": "#59a14f", "Moderate": "#edc949", "High": "#e15759"}
    fig.add_trace(go.Bar(
        x=df["dimension"],
        y=df["hhi_score"],
        marker_color=[colors.get(c, "#4e79a7") for c in df["category"]],
        text=df["category"],
        textposition="outside"))
    fig.add_hline(y=1500, line_dash="dot", annotation_text="Moderate Threshold")
    fig.add_hline(y=2500, line_dash="dash", line_color="red",
                 annotation_text="High Threshold")
    fig.update_layout(yaxis_title="HHI Score", height=400,
                     showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # ── Spend treemaps ──────────────────────────────────────────────
    st.subheader("Spend Distribution")

    tab_sup, tab_country, tab_ccy, tab_mat = st.tabs([
        "By Supplier", "By Country", "By Currency", "By Material"])

    with tab_sup:
        with ENGINE.connect() as conn:
            sup_df = pd.DataFrame(conn.execute(text("""
                SELECT s.company_name AS label,
                       SUM(po.total_value_usd) AS spend
                FROM purchase_orders po
                JOIN suppliers s ON s.supplier_id = po.supplier_id
                WHERE YEAR(po.order_date) = :yr
                GROUP BY s.company_name ORDER BY spend DESC LIMIT 20
            """), {"yr": year_filter}).mappings().fetchall())
        if not sup_df.empty:
            fig = px.treemap(sup_df, path=["label"], values="spend",
                            title="Top 20 Suppliers by Spend")
            st.plotly_chart(fig, use_container_width=True)

    with tab_country:
        with ENGINE.connect() as conn:
            cty_df = pd.DataFrame(conn.execute(text("""
                SELECT c.country_name AS label,
                       SUM(po.total_value_usd) AS spend
                FROM purchase_orders po
                JOIN suppliers s ON s.supplier_id = po.supplier_id
                JOIN countries c ON c.country_id = s.country_id
                WHERE YEAR(po.order_date) = :yr
                GROUP BY c.country_name ORDER BY spend DESC
            """), {"yr": year_filter}).mappings().fetchall())
        if not cty_df.empty:
            fig = px.pie(cty_df, names="label", values="spend",
                        title="Spend by Country")
            st.plotly_chart(fig, use_container_width=True)

    with tab_ccy:
        with ENGINE.connect() as conn:
            fx_df = pd.DataFrame(conn.execute(text("""
                SELECT cu.currency_code AS label,
                       SUM(po.total_value_usd) AS spend
                FROM purchase_orders po
                JOIN suppliers s ON s.supplier_id = po.supplier_id
                JOIN countries c ON c.country_id = s.country_id
                JOIN currencies cu ON cu.currency_id = c.currency_id
                WHERE YEAR(po.order_date) = :yr
                GROUP BY cu.currency_code ORDER BY spend DESC
            """), {"yr": year_filter}).mappings().fetchall())
        if not fx_df.empty:
            fig = px.pie(fx_df, names="label", values="spend",
                        title="Spend by Currency")
            st.plotly_chart(fig, use_container_width=True)

    with tab_mat:
        with ENGINE.connect() as conn:
            mat_df = pd.DataFrame(conn.execute(text("""
                SELECT m.commodity_group AS label,
                       SUM(li.line_total) AS spend
                FROM po_line_items li
                JOIN materials m ON m.material_id = li.material_id
                JOIN purchase_orders po ON po.po_id = li.po_id
                WHERE YEAR(po.order_date) = :yr
                GROUP BY m.commodity_group ORDER BY spend DESC
            """), {"yr": year_filter}).mappings().fetchall())
        if not mat_df.empty:
            fig = px.treemap(mat_df, path=["label"], values="spend",
                            title="Spend by Material Group")
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Database error: {e}")
