"""
AEGIS — Page 8: Working Capital Optimizer
DPO/DSO analysis, invoice aging, early payment optimisation.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine, text
import config

st.set_page_config(page_title="AEGIS · Working Capital", layout="wide")
st.title("🏦 Working Capital Optimizer")

ENGINE = create_engine(config.DATABASE_URL)

tab_overview, tab_aging, tab_epd = st.tabs([
    "📊 Overview", "📅 Invoice Aging", "💰 Early Payment Discounts"])

# ── Tab 1: Overview ─────────────────────────────────────────────────
with tab_overview:
    try:
        from analytics.working_capital import analyze_working_capital
        wc = analyze_working_capital()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg DPO", f"{wc['avg_dpo']:.0f} days")
        c2.metric("Total Outstanding", f"${wc['total_outstanding']:,.0f}")
        c3.metric("Overdue Invoices", f"{wc['overdue_count']:,}")
        c4.metric("Overdue Amount", f"${wc['overdue_amount']:,.0f}")

        # DPO trend
        if wc.get("dpo_trend"):
            dpo_df = pd.DataFrame(wc["dpo_trend"])
            fig = px.line(dpo_df, x="month", y="avg_dpo",
                         title="Average DPO Trend (Monthly)")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        # Top suppliers by outstanding
        st.subheader("Top Suppliers by Outstanding Balance")
        with ENGINE.connect() as conn:
            outstanding_df = pd.DataFrame(conn.execute(text("""
                SELECT s.company_name,
                       COUNT(*) AS pending_invoices,
                       SUM(i.total_amount_usd) AS outstanding_usd,
                       AVG(DATEDIFF(CURDATE(), i.invoice_date)) AS avg_age_days
                FROM invoices i
                JOIN purchase_orders po ON po.po_id = i.po_id
                JOIN suppliers s ON s.supplier_id = po.supplier_id
                WHERE i.payment_status IN ('Pending', 'Overdue')
                GROUP BY s.company_name
                ORDER BY outstanding_usd DESC LIMIT 15
            """)).mappings().fetchall())

        if not outstanding_df.empty:
            fig = px.bar(outstanding_df, x="company_name", y="outstanding_usd",
                        color="avg_age_days",
                        color_continuous_scale="RdYlGn_r",
                        title="Outstanding by Supplier (coloured by age)")
            fig.update_layout(xaxis_tickangle=-45, height=400)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 2: Invoice Aging ────────────────────────────────────────────
with tab_aging:
    try:
        with ENGINE.connect() as conn:
            aging_df = pd.DataFrame(conn.execute(text("""
                SELECT
                    CASE
                        WHEN DATEDIFF(CURDATE(), invoice_date) <= 30 THEN '0-30 days'
                        WHEN DATEDIFF(CURDATE(), invoice_date) <= 60 THEN '31-60 days'
                        WHEN DATEDIFF(CURDATE(), invoice_date) <= 90 THEN '61-90 days'
                        ELSE '90+ days'
                    END AS aging_bucket,
                    payment_status,
                    COUNT(*) AS invoice_count,
                    SUM(total_amount_usd) AS total_usd
                FROM invoices
                GROUP BY aging_bucket, payment_status
                ORDER BY aging_bucket
            """)).mappings().fetchall())

        if not aging_df.empty:
            fig = px.bar(aging_df, x="aging_bucket", y="total_usd",
                        color="payment_status",
                        barmode="stack",
                        title="Invoice Aging by Payment Status")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(aging_df.style.format({"total_usd": "${:,.0f}"}),
                        use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 3: Early Payment Discount ──────────────────────────────────
with tab_epd:
    st.subheader("Early Payment Discount Optimizer")

    col1, col2 = st.columns(2)
    with col1:
        budget = st.number_input("Available Budget ($)", 100000, 10000000,
                                1000000, step=100000)
    with col2:
        cost_of_capital = st.number_input("Cost of Capital (%)", 1.0, 20.0,
                                         8.0, step=0.5) / 100

    if st.button("▶️ Optimize Payments"):
        try:
            from analytics.working_capital import optimize_payment_timing
            result = optimize_payment_timing(float(budget), cost_of_capital)

            c1, c2, c3 = st.columns(3)
            c1.metric("Invoices Selected", f"{result['selected_count']:,}")
            c2.metric("Total Investment", f"${result['total_investment']:,.0f}")
            c3.metric("Net Savings", f"${result['net_savings']:,.0f}")

            if result.get("details"):
                det_df = pd.DataFrame(result["details"])
                st.dataframe(det_df.style.format({
                    "invoice_amount": "${:,.0f}",
                    "discount_earned": "${:,.0f}",
                    "annualized_return_pct": "{:.1f}%"
                }), use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")
