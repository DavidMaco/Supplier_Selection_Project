"""
AEGIS — Page 4: Monte Carlo Lab
Interactive simulation for FX, lead-time, disruptions, cost.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from sqlalchemy import create_engine, text
import config

st.set_page_config(page_title="AEGIS · Monte Carlo Lab", layout="wide")

st.title("🎲 Monte Carlo Simulation Lab")

tab_fx, tab_lt, tab_dis, tab_cost = st.tabs([
    "💱 FX Risk", "📦 Lead Time", "💥 Disruption", "💰 Total Cost"])

# ────────────────────────────────────────────────────────────────────
#  TAB 1: FX Risk
# ────────────────────────────────────────────────────────────────────
with tab_fx:
    st.subheader("FX Rate Simulation (Geometric Brownian Motion)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        currency = st.selectbox("Currency", list(config.FX_ANCHOR_RATES.keys()))
    with col2:
        n_paths = st.number_input("Simulations", 1000, 100000, 10000, step=1000)
    with col3:
        horizon = st.number_input("Horizon (days)", 30, 365, 90)
    with col4:
        vol_override = st.number_input(
            "Vol Override (σ)", 0.01, 1.0,
            float(config.FX_VOLATILITIES.get(currency, 0.10)),
            step=0.01, format="%.2f")

    if st.button("▶️ Run FX Simulation", key="fx_btn"):
        with st.spinner("Simulating..."):
            from analytics.monte_carlo import simulate_fx, save_simulation
            result = simulate_fx(currency, int(n_paths), int(horizon),
                                annual_vol=vol_override)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Current Rate", f"{result['current_rate']:,.2f}")
        c2.metric("Mean (sim)", f"{result['mean']:,.2f}")
        c3.metric("95th %ile", f"{result['p95']:,.2f}")
        c4.metric("VaR (95%)", f"{result['var_95']:,.2f}")
        c5.metric("CVaR (95%)", f"{result['cvar_95']:,.2f}")

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=result["terminal_rates"], nbinsx=80, name="Distribution",
            marker_color="#4e79a7"))
        fig.add_vline(x=result["current_rate"], line_dash="dash",
                     line_color="red", annotation_text="Current")
        fig.add_vline(x=result["p95"], line_dash="dot",
                     line_color="orange", annotation_text="P95")
        fig.update_layout(
            title=f"{currency}/USD — {n_paths:,} Paths, {horizon} Days",
            xaxis_title="Rate", yaxis_title="Frequency", height=400)
        st.plotly_chart(fig, use_container_width=True)

        save_simulation("FX", f"{currency} {horizon}d", result, int(n_paths))
        st.caption("✓ Results saved to simulation_runs table")

# ────────────────────────────────────────────────────────────────────
#  TAB 2: Lead Time
# ────────────────────────────────────────────────────────────────────
with tab_lt:
    st.subheader("Lead-Time Distribution (Log-Normal)")

    col1, col2 = st.columns(2)
    with col1:
        lt_n = st.number_input("Simulations", 1000, 50000, 10000, step=1000, key="lt_n")
    with col2:
        lt_sid = st.number_input("Supplier ID (0=all)", 0, 100, 0, key="lt_sid")

    if st.button("▶️ Run Lead-Time Simulation", key="lt_btn"):
        with st.spinner("Simulating..."):
            from analytics.monte_carlo import simulate_lead_time, save_simulation
            sid = int(lt_sid) if lt_sid > 0 else None
            result = simulate_lead_time(sid, int(lt_n))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Historical Mean", f"{result['hist_mean']:.1f} days")
        c2.metric("Simulated Mean", f"{result['mean']:.1f} days")
        c3.metric("P95", f"{result['p95']:.1f} days")
        c4.metric("Std Dev", f"{result['std_dev']:.1f} days")

        fig = go.Figure()
        fig.add_trace(go.Histogram(x=result["simulated"], nbinsx=60,
                                   marker_color="#59a14f"))
        fig.add_vline(x=result["p95"], line_dash="dot", line_color="red",
                     annotation_text="P95")
        fig.update_layout(title="Lead-Time Distribution",
                         xaxis_title="Days", yaxis_title="Frequency", height=400)
        st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────────────────────────────────────────
#  TAB 3: Disruption
# ────────────────────────────────────────────────────────────────────
with tab_dis:
    st.subheader("Disruption Impact Simulation")

    col1, col2, col3 = st.columns(3)
    with col1:
        scenario = st.selectbox("Scenario",
            ["port_closure", "supplier_failure", "sanctions", "natural_disaster"])
    with col2:
        entity = st.text_input("Affected Entity", "Lagos")
    with col3:
        duration = st.number_input("Duration (days)", 7, 180, 30)

    if st.button("▶️ Run Disruption Simulation", key="dis_btn"):
        with st.spinner("Simulating..."):
            from analytics.monte_carlo import simulate_disruption, save_simulation
            result = simulate_disruption(scenario, entity, int(duration))

        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline Spend", f"${result['baseline_spend']:,.0f}")
        c2.metric("Cost Impact (Mean)", f"${result['cost_impact_mean']:,.0f}")
        c3.metric("Cost Impact (P95)", f"${result['cost_impact_p95']:,.0f}")

        st.metric("Lead-Time Addition (P95)", f"{result['lt_addition_p95']:.0f} days")
        st.metric("CVaR (95%)", f"${result['cvar_95']:,.0f}")

# ────────────────────────────────────────────────────────────────────
#  TAB 4: Total Cost
# ────────────────────────────────────────────────────────────────────
with tab_cost:
    st.subheader("Total Procurement Cost Under Uncertainty")

    col1, col2 = st.columns(2)
    with col1:
        cost_n = st.number_input("Simulations", 1000, 50000, 10000, step=1000, key="cost_n")
    with col2:
        cost_ccys = st.multiselect("FX Currencies",
            list(config.FX_ANCHOR_RATES.keys()),
            default=["NGN", "EUR", "GBP"])

    if st.button("▶️ Run Cost Simulation", key="cost_btn"):
        with st.spinner("Simulating..."):
            from analytics.monte_carlo import simulate_cost_scenario, save_simulation
            result = simulate_cost_scenario(int(cost_n), cost_ccys)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Baseline", f"${result['baseline_spend']:,.0f}")
        c2.metric("Mean Cost", f"${result['mean_cost']:,.0f}")
        c3.metric("P95 Cost", f"${result['p95_cost']:,.0f}")
        c4.metric("VaR (95%)", f"${result['var_95']:,.0f}")

        fig = go.Figure()
        fig.add_trace(go.Histogram(x=result["cost_distribution"], nbinsx=80,
                                   marker_color="#e15759"))
        fig.add_vline(x=result["baseline_spend"], line_dash="dash",
                     line_color="blue", annotation_text="Baseline")
        fig.add_vline(x=result["p95_cost"], line_dash="dot",
                     line_color="red", annotation_text="P95")
        fig.update_layout(title="Total Cost Distribution",
                         xaxis_title="USD", yaxis_title="Frequency", height=400)
        st.plotly_chart(fig, use_container_width=True)
