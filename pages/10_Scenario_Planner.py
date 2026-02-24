"""
AEGIS — Page 10: Scenario Planner
What-if analysis: supplier switch, currency hedge, nearshoring.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine, text
import config

st.set_page_config(page_title="AEGIS · Scenario Planner", layout="wide")
st.title("🔮 Scenario Planner")

ENGINE = create_engine(config.DATABASE_URL)

tab_switch, tab_hedge, tab_near = st.tabs([
    "🔄 Supplier Switch", "💱 Currency Hedge", "📍 Nearshoring"])

# ── Tab 1: Supplier Switch ──────────────────────────────────────────
with tab_switch:
    st.subheader("Supplier Switch Cost-Benefit Analysis")

    try:
        with ENGINE.connect() as conn:
            suppliers = pd.DataFrame(conn.execute(text(
                "SELECT supplier_id, company_name FROM suppliers ORDER BY company_name"
            )).mappings().fetchall())

        if suppliers.empty:
            st.info("No suppliers in database.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                from_sup = st.selectbox(
                    "Current Supplier",
                    suppliers["supplier_id"].tolist(),
                    format_func=lambda x: suppliers.loc[suppliers["supplier_id"] == x, "company_name"].iloc[0])
            with col2:
                to_sup = st.selectbox(
                    "Alternative Supplier",
                    [s for s in suppliers["supplier_id"].tolist() if s != from_sup],
                    format_func=lambda x: suppliers.loc[suppliers["supplier_id"] == x, "company_name"].iloc[0])

            if st.button("▶️ Analyse Switch", key="switch_btn"):
                from analytics.scenario_planner import scenario_supplier_switch
                result = scenario_supplier_switch(int(from_sup), int(to_sup))

                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Avg Cost",
                         f"${result.get('current_avg_cost', 0):,.2f}")
                c2.metric("Alternative Avg Cost",
                         f"${result.get('alt_avg_cost', 0):,.2f}")
                c3.metric("Cost Delta",
                         f"{result.get('cost_delta_pct', 0):+.1f}%")
                c4.metric("Lead-Time Delta",
                         f"{result.get('leadtime_delta_days', 0):+.1f} days")

                # Comparison radar
                categories = ["Cost", "Lead Time", "Quality", "ESG"]
                current_vals = [
                    result.get("current_avg_cost", 0),
                    result.get("current_avg_leadtime", 0),
                    result.get("current_defect_rate", 0),
                    result.get("current_esg", 0)]
                alt_vals = [
                    result.get("alt_avg_cost", 0),
                    result.get("alt_avg_leadtime", 0),
                    result.get("alt_defect_rate", 0),
                    result.get("alt_esg", 0)]

                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=current_vals, theta=categories, fill="toself",
                    name="Current"))
                fig.add_trace(go.Scatterpolar(
                    r=alt_vals, theta=categories, fill="toself",
                    name="Alternative"))
                fig.update_layout(title="Supplier Comparison", height=400)
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
                hedge_ccy, float(exposure), forward_premium)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Rate", f"{result.get('current_rate', 0):,.4f}")
            c2.metric("Forward Rate",
                     f"{result.get('forward_rate', 0):,.4f}")
            c3.metric("Unhedged VaR (95%)",
                     f"${result.get('unhedged_var', 0):,.0f}")
            c4.metric("Hedged VaR (95%)",
                     f"${result.get('hedged_var', 0):,.0f}")

            # Distribution comparison
            sim = result.get("simulation", {})
            if sim.get("terminal_rates"):
                import numpy as np
                rates = np.array(sim["terminal_rates"])
                unhedged_costs = exposure * rates
                hedged_costs = exposure * result.get("forward_rate", rates.mean())

                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=unhedged_costs, name="Unhedged",
                    marker_color="#e15759", opacity=0.6))
                fig.add_vline(x=hedged_costs, line_dash="dash",
                             line_color="blue", annotation_text="Hedged Cost")
                fig.update_layout(
                    title=f"Unhedged Cost Distribution ({hedge_ccy})",
                    xaxis_title="Cost (USD)", height=400)
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")

# ── Tab 3: Nearshoring ──────────────────────────────────────────────
with tab_near:
    st.subheader("Nearshoring vs Current Sourcing")

    col1, col2 = st.columns(2)
    with col1:
        current_country = st.text_input("Current Country", "China")
    with col2:
        near_country = st.text_input("Nearshore Country", "Turkey")

    col1, col2 = st.columns(2)
    with col1:
        cost_premium = st.number_input("Cost Premium (%)", -20.0, 50.0, 10.0,
                                      step=1.0) / 100
    with col2:
        freight_saving = st.number_input("Freight Saving (%)", 0.0, 80.0, 40.0,
                                        step=5.0) / 100

    if st.button("▶️ Analyse Nearshoring", key="near_btn"):
        try:
            from analytics.scenario_planner import scenario_nearshoring
            result = scenario_nearshoring(
                current_country, near_country,
                cost_premium, freight_saving)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Spend",
                     f"${result.get('current_spend', 0):,.0f}")
            c2.metric("Nearshore Est.",
                     f"${result.get('nearshore_spend', 0):,.0f}")
            c3.metric("Lead-Time Savings",
                     f"{result.get('leadtime_saving_days', 0):.0f} days")
            c4.metric("Carbon Reduction",
                     f"{result.get('carbon_reduction_pct', 0):.0f}%")

            # Cost comparison bar
            comp_data = pd.DataFrame([
                {"Category": "Material Cost", "Current": result.get("current_spend", 0),
                 "Nearshore": result.get("nearshore_spend", 0)},
                {"Category": "Freight", "Current": result.get("current_freight", 0),
                 "Nearshore": result.get("nearshore_freight", 0)},
            ])
            fig = px.bar(comp_data.melt(id_vars="Category"),
                        x="Category", y="value", color="variable",
                        barmode="group", title="Cost Comparison")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
