"""
AEGIS — Page 1: Executive Dashboard
KPIs, spend trends, supplier health, alerts.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Executive Dashboard", layout="wide")
ENGINE = get_engine()

st.title("📈 Executive Dashboard")

with st.sidebar:
    analysis_year = st.selectbox(
        "Analysis Year", [2025, 2024, 2023, 2022], index=0, key="exec_yr")

try:
    yr = int(analysis_year)
    with ENGINE.connect() as conn:
        # ─── KPIs ────────────────────────────────────────────────
        total_spend = float(conn.execute(text(
            "SELECT COALESCE(SUM(line_total),0) FROM po_line_items li "
            "JOIN purchase_orders po ON li.po_id=po.po_id WHERE YEAR(po.order_date)=:yr"
        ), {"yr": yr}).scalar())

        active_suppliers = conn.execute(text(
            "SELECT COUNT(*) FROM suppliers WHERE status='Active'"
        )).scalar()

        on_time = conn.execute(text(
            "SELECT AVG(CASE WHEN delay_days<=0 THEN 100 ELSE 0 END) FROM shipments "
            "WHERE YEAR(dispatch_date)=:yr"
        ), {"yr": yr}).scalar() or 0

        avg_defect = conn.execute(text(
            "SELECT AVG(defect_rate_pct) FROM quality_inspections qi "
            "JOIN shipments sh ON qi.shipment_id=sh.shipment_id "
            "WHERE YEAR(sh.dispatch_date)=:yr"
        ), {"yr": yr}).scalar() or 0

        maverick_pct = conn.execute(text(
            "SELECT AVG(is_maverick)*100 FROM purchase_orders WHERE YEAR(order_date)=:yr"
        ), {"yr": yr}).scalar() or 0

        overdue_amt = float(conn.execute(text(
            "SELECT COALESCE(SUM(amount_usd),0) FROM invoices "
            "WHERE status='Overdue' AND YEAR(invoice_date)=:yr"
        ), {"yr": yr}).scalar())

    r1 = st.columns(3)
    r1[0].metric(f"{yr} Spend", f"${total_spend:,.0f}")
    r1[1].metric("Active Suppliers", active_suppliers)
    r1[2].metric("On-Time Delivery", f"{on_time:.1f}%")
    r2 = st.columns(3)
    r2[0].metric("Avg Defect Rate", f"{avg_defect:.1f}%")
    r2[1].metric("Maverick Spend", f"{maverick_pct:.1f}%")
    r2[2].metric("Overdue Invoices", f"${overdue_amt:,.0f}")

    st.markdown("---")

    # ─── Spend by Month ──────────────────────────────────────────
    with ENGINE.connect() as conn:
        spend_trend = pd.read_sql(text("""
            SELECT DATE_FORMAT(po.order_date, '%%Y-%%m') AS month,
                   SUM(li.line_total) AS spend
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            WHERE YEAR(po.order_date) BETWEEN :yr_start AND :yr
            GROUP BY month ORDER BY month
        """), conn, params={"yr": yr, "yr_start": yr - 2})

        spend_by_region = pd.read_sql(text("""
            SELECT c.region, SUM(li.line_total) AS spend
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            JOIN suppliers s ON po.supplier_id = s.supplier_id
            JOIN countries c ON s.country_id = c.country_id
            WHERE YEAR(po.order_date) = :yr
            GROUP BY c.region ORDER BY spend DESC
        """), conn, params={"yr": yr})

        tier_dist = pd.read_sql(text("""
            SELECT tier_level, COUNT(*) AS count
            FROM suppliers WHERE status='Active'
            GROUP BY tier_level
        """), conn)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.line(spend_trend, x="month", y="spend",
                      title="Monthly Procurement Spend Trend",
                      labels={"spend": "Spend (USD)", "month": "Month"})
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.pie(spend_by_region, values="spend", names="region",
                     title=f"{yr} Spend by Region", hole=0.4)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig = px.bar(tier_dist, x="tier_level", y="count",
                     title="Supplier Tier Distribution",
                     color="tier_level",
                     color_discrete_map={
                         "Strategic": "#1a9850", "Preferred": "#91cf60",
                         "Approved": "#fee08b", "Conditional": "#fc8d59",
                         "Blocked": "#d73027"})
        fig.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        # Alerts
        st.subheader("⚠️ Active Alerts")
        with ENGINE.connect() as conn:
            alerts = pd.read_sql(text("""
                SELECT s.supplier_name, qi.category, qi.severity, qi.incident_date
                FROM quality_incidents qi
                JOIN suppliers s ON qi.supplier_id = s.supplier_id
                WHERE qi.capa_status IN ('Open','In Progress')
                ORDER BY qi.incident_date DESC LIMIT 8
            """), conn)
        if not alerts.empty:
            st.dataframe(alerts, use_container_width=True, hide_index=True)
        else:
            st.success("No active alerts")

except Exception as e:
    st.error(f"Database error: {e}")
    st.info("Run `python run_aegis_pipeline.py` to initialize.")
