"""
AEGIS — Page 11: Data Explorer
Browse all tables, run ad-hoc queries, export to Excel/CSV.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import re
from sqlalchemy import text, inspect
from utils.db import get_engine

st.set_page_config(page_title="AEGIS · Data Explorer", layout="wide")
st.title("🗄️ Data Explorer")

ENGINE = get_engine()

tab_browse, tab_query, tab_export = st.tabs([
    "📋 Table Browser", "🔍 Ad-Hoc Query", "📥 Executive Export"])


def _is_safe_read_only_sql(query: str) -> tuple[bool, str]:
    q = (query or "").strip()
    if not q:
        return False, "Query cannot be empty."

    core = q[:-1] if q.endswith(";") else q
    if ";" in core:
        return False, "Only a single statement is allowed."

    stripped = re.sub(r"--.*?$", "", q, flags=re.MULTILINE)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL).strip()
    if not re.match(r"^(select|with)\b", stripped, flags=re.IGNORECASE):
        return False, "Only SELECT/CTE read-only queries are allowed."

    blocked = (
        r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|"
        r"replace|merge|call|execute|set|use)\b"
    )
    if re.search(blocked, stripped, flags=re.IGNORECASE):
        return False, "Write/DDL statements are not allowed."

    return True, ""


# ── Tab 1: Table Browser ────────────────────────────────────────────
with tab_browse:
    try:
        inspector = inspect(ENGINE)
        tables = sorted(inspector.get_table_names())

        col1, col2 = st.columns([1, 3])
        with col1:
            selected_table = st.selectbox("Table", tables)
            row_limit = st.number_input("Row Limit", 10, 5000, 100, step=50)

        # Show schema
        with col2:
            cols_info = inspector.get_columns(selected_table)
            schema_df = pd.DataFrame([{
                "Column": c["name"],
                "Type": str(c["type"]),
                "Nullable": c.get("nullable", True),
                "Default": c.get("default", "-")
            } for c in cols_info])
            with st.expander(f"📐 Schema: {selected_table} ({len(cols_info)} columns)", expanded=False):
                st.dataframe(schema_df, use_container_width=True)

        # Fetch data
        with ENGINE.connect() as conn:
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM `{selected_table}`")).scalar()
            st.caption(f"**{selected_table}** — {count:,} rows total, showing ≤{row_limit}")

            df = pd.DataFrame(conn.execute(
                text(f"SELECT * FROM `{selected_table}` LIMIT :lim"),
                {"lim": row_limit}).mappings().fetchall())

        if not df.empty:
            st.dataframe(df, use_container_width=True, height=500)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV", csv,
                f"{selected_table}.csv", "text/csv")
        else:
            st.info("Table is empty.")

        # Quick stats
        if not df.empty:
            with st.expander("📊 Quick Stats"):
                st.dataframe(df.describe(include="all").T, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 2: Ad-Hoc Query ─────────────────────────────────────────────
with tab_query:
    st.markdown("Run a **read-only** SQL query against the AEGIS database.")

    query = st.text_area("SQL Query", value="SELECT * FROM suppliers LIMIT 10;",
                        height=120)

    col1, col2 = st.columns([1, 4])
    with col1:
        run_btn = st.button("▶️ Execute")

    if run_btn:
        ok, reason = _is_safe_read_only_sql(query)
        if not ok:
            st.error(f"⛔ {reason}")
        else:
            try:
                with ENGINE.connect() as conn:
                    result_df = pd.DataFrame(
                        conn.execute(text(query.rstrip(";"))).mappings().fetchall())

                if not result_df.empty:
                    st.success(f"✓ {len(result_df)} rows returned")
                    st.dataframe(result_df, use_container_width=True, height=500)

                    csv = result_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download CSV", csv,
                        "query_result.csv", "text/csv")
                else:
                    st.info("Query returned 0 rows.")

            except Exception:
                st.error("Query failed. Check SQL syntax and read permissions.")

    # Quick templates
    with st.expander("📝 Query Templates"):
        st.code("""-- Top 10 suppliers by spend
SELECT s.supplier_name, SUM(po.total_value_usd) AS total_spend
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
GROUP BY s.supplier_name
ORDER BY total_spend DESC LIMIT 10;""", language="sql")

        st.code("""-- FX rate trend for NGN
SELECT rate_date, rate_to_usd
FROM fx_rates
JOIN currencies c ON c.currency_id = fx_rates.currency_id
WHERE c.currency_code = 'NGN'
ORDER BY rate_date;""", language="sql")

        st.code("""-- Overdue shipments
SELECT sh.shipment_id, s.supplier_name, sh.eta_date,
       sh.actual_arrival, sh.delay_days
FROM shipments sh
JOIN purchase_orders po ON po.po_id = sh.po_id
JOIN suppliers s ON s.supplier_id = po.supplier_id
WHERE sh.delay_days > 7
ORDER BY sh.delay_days DESC LIMIT 20;""", language="sql")

# ── Tab 3: Executive Export ──────────────────────────────────────────
with tab_export:
    st.subheader("📥 Executive Report Export")
    st.markdown(
        "Download a multi-sheet Excel workbook containing scorecards, "
        "risk assessments, concentration analysis, spend summary, and carbon data."
    )

    if st.button("📊 Generate Executive Report", type="primary"):
        with st.spinner("Building report..."):
            try:
                from utils.export import generate_executive_summary, to_excel_bytes

                sheets = generate_executive_summary(ENGINE)
                if sheets:
                    excel_data = to_excel_bytes(sheets)
                    st.success(f"Report ready — {len(sheets)} sheets, "
                              f"{sum(len(df) for df in sheets.values())} total rows")

                    for name, df in sheets.items():
                        with st.expander(f"{name} ({len(df)} rows)"):
                            st.dataframe(df.head(10), use_container_width=True)

                    st.download_button(
                        "⬇️ Download Excel",
                        excel_data,
                        "AEGIS_Executive_Report.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.warning("No data available. Run the pipeline first.")
            except Exception as e:
                st.error(f"Export failed: {e}")
