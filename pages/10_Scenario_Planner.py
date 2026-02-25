"""
AEGIS — Page 10: Scenario Planner
What-if analysis: supplier switch, currency hedge, nearshoring.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Scenario Planner", layout="wide")
st.title("🔮 Scenario Planner")

ENGINE = get_engine()

tab_switch, tab_hedge, tab_near = st.tabs([
    "🔄 Supplier Switch", "💱 Currency Hedge", "📍 Nearshoring"])

# ── Tab 1: Supplier Switch ──────────────────────────────────────────
with tab_switch:
    st.subheader("Supplier Switch Cost-Benefit Analysis")

    try:
        with ENGINE.connect() as conn:
            suppliers = pd.DataFrame(conn.execute(text(
                "SELECT supplier_id, supplier_name FROM suppliers ORDER BY supplier_name"
            )).mappings().fetchall())

        if suppliers.empty:
            st.info("No suppliers in database.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                from_sup = st.selectbox(
                    "Current Supplier",
                    suppliers["supplier_id"].tolist(),
                    format_func=lambda x: suppliers.loc[suppliers["supplier_id"] == x, "supplier_name"].iloc[0])
            with col2:
                to_sup = st.selectbox(
                    "Alternative Supplier",
                    [s for s in suppliers["supplier_id"].tolist() if s != from_sup],
                    format_func=lambda x: suppliers.loc[suppliers["supplier_id"] == x, "supplier_name"].iloc[0])

            if st.button("▶️ Analyse Switch", key="switch_btn"):
                from analytics.scenario_planner import scenario_supplier_switch
                result = scenario_supplier_switch(int(from_sup), int(to_sup))

                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Spend",
                         f"${result.get('current_spend', 0):,.2f}")
                c2.metric("Estimated New Spend",
                         f"${result.get('estimated_new_spend', 0):,.2f}")
                c3.metric("Cost Impact",
                         f"{result.get('cost_impact_pct', 0):+.1f}%")
                c4.metric("Delay Change",
                         f"{result.get('delay_change', 0):+.1f} days")

                # Comparison radar
                categories = ["Cost Impact %", "Delay Change", "Quality Change", "ESG Change"]
                vals = [
                    result.get("cost_impact_pct", 0),
                    result.get("delay_change", 0),
                    result.get("quality_change", 0),
                    result.get("esg_change", 0)]

                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=vals, theta=categories, fill="toself",
                    name="Impact"))
                fig.update_layout(title="Switch Impact Analysis", height=400)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 2: Currency Hedge ────────────────────────────────────────────
with tab_hedge:
    st.subheader("Currency Hedge Scenario")

    col1, col2, col3 = st.columns(3)
    with col1:
        hedge_ccy = st.selectbox("Currency",
            list(config.FX_ANCHOR_RATES.keys()), key="hedge_ccy")
    with col2:
        exposure = st.number_input("Exposure (USD)", 100000, 50000000,
                                  5000000, step=500000)
    with col3:
        forward_premium = st.number_input("Forward Premium (%)", 0.0, 20.0,
                                         3.0, step=0.5) / 100

    if st.button("▶️ Analyse Hedge", key="hedge_btn"):
        try:
            from analytics.scenario_planner import scenario_currency_hedge
            result = scenario_currency_hedge(
                hedge_ccy, float(exposure) / 1e6 if exposure > 1 else 0.80,
                float(forward_premium) * 100)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Exposure (USD)", f"${result.get('exposure_usd', 0):,.0f}")
            c2.metric("Hedge %",
                     f"{result.get('hedge_pct', 0) * 100:.0f}%")
            c3.metric("Unhedged VaR (P95)",
                     f"${result.get('unhedged_worst_case_p95', 0):,.0f}")
            c4.metric("Hedged VaR (P95)",
                     f"${result.get('hedged_worst_case_p95', 0):,.0f}")

            savings = result.get('savings_at_p95', 0)
            if savings:
                st.success(f"Hedge saves **${savings:,.0f}** at P95 vs unhedged")

        except Exception as e:
            st.error(f"Error: {e}")

# ── Tab 3: Nearshoring ──────────────────────────────────────────────
with tab_near:
    st.subheader("Nearshoring vs Current Sourcing")

    col1, col2 = st.columns(2)
    with col1:
        target_region = st.selectbox("Target Region",
            ["Africa", "Europe", "Asia", "Americas", "Oceania"], key="near_region")
    with col2:
        realloc_pct = st.slider("Reallocation %", 5, 80, 30, step=5,
                                key="near_pct") / 100

    if st.button("▶️ Analyse Nearshoring", key="near_btn"):
        try:
            from analytics.scenario_planner import scenario_nearshoring
            result = scenario_nearshoring(target_region, realloc_pct)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Reallocation Amount",
                     f"${result.get('reallocation_amount', 0):,.0f}")
            c2.metric("Cost Premium Impact",
                     f"${result.get('cost_premium_impact', 0):,.0f}")
            c3.metric("Freight Savings",
                     f"${result.get('freight_savings', 0):,.0f}")
            c4.metric("Net Cost Impact",
                     f"${result.get('net_cost_impact', 0):,.0f}")

            st.markdown(f"**Lead-time improvement:** {result.get('lead_time_improvement_pct', 0):.0f}%")
            st.markdown(f"**Carbon reduction (est.):** {result.get('carbon_reduction_pct', 0):.0f}%")

            # Regional spend breakdown if available
            by_region = result.get("by_region")
            if by_region is not None and not by_region.empty:
                fig = px.pie(by_region, names="region", values="spend",
                            title="Current Spend by Region")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
