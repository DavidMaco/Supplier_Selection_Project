"""
AEGIS — Page 9: ESG & Compliance Centre
ESG ratings, compliance checks, OECD due-diligence tracker.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · ESG & Compliance", layout="wide")
st.title("🌱 ESG & Compliance Centre")

ENGINE = get_engine()

tab_esg, tab_comp, tab_dd = st.tabs([
    "🏅 ESG Ratings", "✅ Compliance", "📋 Due Diligence"])

# ── Tab 1: ESG Ratings ──────────────────────────────────────────────
with tab_esg:
    try:
        with ENGINE.connect() as conn:
            esg_df = pd.DataFrame(conn.execute(text("""
                SELECT s.company_name, e.assessment_year,
                       e.environmental_score, e.social_score,
                       e.governance_score, e.composite_score,
                       e.esg_rating
                FROM esg_assessments e
                JOIN suppliers s ON s.supplier_id = e.supplier_id
                ORDER BY e.assessment_year DESC, e.composite_score DESC
            """)).mappings().fetchall())

        if esg_df.empty:
            st.info("No ESG data.")
            st.stop()

        latest = esg_df[esg_df["assessment_year"] == esg_df["assessment_year"].max()]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Assessed Suppliers", f"{len(latest)}")
        c2.metric("Avg Composite", f"{latest['composite_score'].mean():.1f}")
        c3.metric("A/B Rated", f"{len(latest[latest['esg_rating'].isin(['A', 'B'])])}")
        c4.metric("D/F Rated", f"{len(latest[latest['esg_rating'].isin(['D', 'F'])])}")

        # Rating distribution
        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(latest, x="esg_rating",
                             color="esg_rating",
                             color_discrete_map={
                                 "A": "#59a14f", "B": "#76b7b2",
                                 "C": "#edc949", "D": "#f28e2b",
                                 "F": "#e15759"},
                             title="ESG Rating Distribution")
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.scatter(latest, x="environmental_score",
                           y="social_score", size="governance_score",
                           color="esg_rating",
                           hover_name="company_name",
                           title="E vs S Score (bubble = G)",
                           color_discrete_map={
                               "A": "#59a14f", "B": "#76b7b2",
                               "C": "#edc949", "D": "#f28e2b",
                               "F": "#e15759"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        # Radar for selected supplier
        st.subheader("Supplier ESG Detail")
        sel = st.selectbox("Select Supplier", latest["company_name"].tolist())
        row = latest[latest["company_name"] == sel].iloc[0]
        fig = go.Figure(go.Scatterpolar(
            r=[row["environmental_score"], row["social_score"],
               row["governance_score"], row["composite_score"]],
            theta=["Environmental", "Social", "Governance", "Composite"],
            fill="toself", line_color="#4e79a7"))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])),
                         height=350, title=f"ESG Profile: {sel}")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 2: Compliance ───────────────────────────────────────────────
with tab_comp:
    try:
        with ENGINE.connect() as conn:
            comp_df = pd.DataFrame(conn.execute(text("""
                SELECT s.company_name, cf.framework_name,
                       cc.check_date, cc.status, cc.findings
                FROM compliance_checks cc
                JOIN suppliers s ON s.supplier_id = cc.supplier_id
                JOIN compliance_frameworks cf ON cf.framework_id = cc.framework_id
                ORDER BY cc.check_date DESC
            """)).mappings().fetchall())

        if not comp_df.empty:
            status_counts = comp_df["status"].value_counts()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Checks", f"{len(comp_df)}")
            c2.metric("Compliant", f"{status_counts.get('Compliant', 0)}")
            c3.metric("Non-Compliant", f"{status_counts.get('Non-Compliant', 0)}")

            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(comp_df, names="status",
                            title="Compliance Status Distribution",
                            color="status",
                            color_discrete_map={
                                "Compliant": "#59a14f",
                                "Non-Compliant": "#e15759",
                                "Partial": "#edc949"})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fw_df = comp_df.groupby("framework_name")["status"].value_counts().reset_index()
                fig = px.bar(fw_df, x="framework_name", y="count",
                            color="status", barmode="stack",
                            title="Compliance by Framework",
                            color_discrete_map={
                                "Compliant": "#59a14f",
                                "Non-Compliant": "#e15759",
                                "Partial": "#edc949"})
                fig.update_layout(xaxis_tickangle=-45, height=350)
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(comp_df, use_container_width=True, height=400)
        else:
            st.info("No compliance data.")

    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 3: Due Diligence ────────────────────────────────────────────
with tab_dd:
    try:
        with ENGINE.connect() as conn:
            dd_df = pd.DataFrame(conn.execute(text("""
                SELECT s.company_name, d.dd_type, d.oecd_step,
                       d.start_date, d.completion_date, d.status,
                       d.risk_level, d.findings_summary
                FROM due_diligence_records d
                JOIN suppliers s ON s.supplier_id = d.supplier_id
                ORDER BY d.start_date DESC
            """)).mappings().fetchall())

        if not dd_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("DD Records", f"{len(dd_df)}")
            c2.metric("In Progress", f"{len(dd_df[dd_df['status'] == 'In Progress'])}")
            c3.metric("High Risk", f"{len(dd_df[dd_df['risk_level'] == 'High'])}")

            fig = px.histogram(dd_df, x="oecd_step", color="status",
                             barmode="group",
                             title="OECD 6-Step Due Diligence Progress")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(dd_df, use_container_width=True, height=400)
        else:
            st.info("No due diligence records.")

    except Exception as e:
        st.error(f"Error: {e}")
