"""
AEGIS — Page 7: Should-Cost Analysis
Bottom-up cost model, leakage detection.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Should-Cost", layout="wide")
st.title("💲 Should-Cost Analysis & Leakage Detection")

ENGINE = get_engine()

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    year = st.selectbox("Year", [2024, 2023, 2022, 2025], key="sc_yr")
    flag_filter = st.multiselect(
        "Leakage Flag",
        ["Within Range", "Investigate", "Escalate", "Red Flag"],
        default=["Investigate", "Escalate", "Red Flag"])

try:
    from analytics.should_cost import build_should_cost, get_leakage_summary

    with st.spinner("Building should-cost model..."):
        df = build_should_cost(year=year)

    if df is None or (hasattr(df, 'empty') and df.empty):
        st.info("No should-cost data for the selected year. "
                "Ensure `supplier_material_catalog` is populated.")
        st.stop()

    if isinstance(df, list):
        df = pd.DataFrame(df)

    # ── KPI row ─────────────────────────────────────────────────────
    total_quoted = df["quoted_usd"].sum()
    total_should = df["should_cost_usd"].sum()
    leakage_usd = total_quoted - total_should
    leakage_pct = (leakage_usd / total_should * 100) if total_should else 0
    flags = df["leakage_flag"].value_counts().to_dict()

    r1 = st.columns(3)
    r1[0].metric("Items Analysed", f"{len(df):,}")
    r1[1].metric("Total Quoted", f"${total_quoted:,.0f}")
    r1[2].metric("Total Should-Cost", f"${total_should:,.0f}")
    r2 = st.columns(2)
    r2[0].metric("Total Leakage", f"${leakage_usd:,.0f}")
    r2[1].metric("Leakage %", f"{leakage_pct:+.1f}%")

    # ── Leakage flag distribution ───────────────────────────────────
    st.subheader("Leakage Classification")
    flag_colors = {
        "Within Range": "#59a14f", "Investigate": "#edc949",
        "Escalate": "#f28e2b", "Red Flag": "#e15759"
    }
    flag_df = pd.DataFrame([
        {"flag": k, "count": v} for k, v in flags.items()
    ])
    if not flag_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(flag_df, x="flag", y="count",
                        color="flag",
                        color_discrete_map=flag_colors,
                        title="Items by Leakage Classification")
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.pie(flag_df, names="flag", values="count",
                        color="flag",
                        color_discrete_map=flag_colors,
                        title="Leakage Distribution")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    # ── Cost breakdown waterfall (sample item) ──────────────────────
    st.subheader("Cost Decomposition — Worst Leakage Item")
    worst = df.sort_values("cost_variance_pct", ascending=False).iloc[0]

    fig = go.Figure(go.Waterfall(
        name="Should-Cost",
        orientation="v",
        x=["Material", "Freight", "Customs", "Overhead",
           "Margin", "Should-Cost", "Quoted", "Variance"],
        y=[worst["material_cost"], worst["freight_cost"],
           worst["customs_cost"], worst["overhead_cost"],
           worst["margin_cost"], 0,
           worst["quoted_usd"],
           worst["quoted_usd"] - worst["should_cost_usd"]],
        measure=["relative", "relative", "relative", "relative",
                 "relative", "total", "total", "relative"],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#e15759"}},
        decreasing={"marker": {"color": "#59a14f"}},
        totals={"marker": {"color": "#4e79a7"}}
    ))
    fig.update_layout(
        title=f"Cost Decomposition: {worst.get('material_name', 'Item')}",
        yaxis_title="USD", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # ── Leakage detail table ────────────────────────────────────────
    st.subheader("Leakage Detail")
    filtered = df[df["leakage_flag"].isin(flag_filter)] if flag_filter else df
    display_cols = ["material_name", "supplier_name", "quoted_usd",
                    "should_cost_usd", "cost_variance_pct", "leakage_flag"]
    available_cols = [c for c in display_cols if c in filtered.columns]
    if available_cols:
        st.dataframe(
            filtered[available_cols].sort_values("cost_variance_pct", ascending=False)
            .style.format({"quoted_usd": "${:,.2f}",
                          "should_cost_usd": "${:,.2f}",
                          "cost_variance_pct": "{:+.1f}%"}),
            use_container_width=True, height=400)

except Exception as e:
    st.error(f"Error: {e}")
