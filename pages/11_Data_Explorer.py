"""
AEGIS — Page 11: Data Explorer
Browse all tables, run ad-hoc queries, export to CSV.
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text, inspect
import config

st.set_page_config(page_title="AEGIS · Data Explorer", layout="wide")
st.title("🗄️ Data Explorer")

ENGINE = create_engine(config.DATABASE_URL)

tab_browse, tab_query = st.tabs(["📋 Table Browser", "🔍 Ad-Hoc Query"])

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
        q_lower = query.strip().lower()
        blocked = ["drop", "delete", "truncate", "alter", "update", "insert", "create"]
        if any(q_lower.startswith(b) for b in blocked):
            st.error("⛔ Only SELECT queries are permitted in the explorer.")
        else:
            try:
                with ENGINE.connect() as conn:
                    result_df = pd.DataFrame(
                        conn.execute(text(query)).mappings().fetchall())

                if not result_df.empty:
                    st.success(f"✓ {len(result_df)} rows returned")
                    st.dataframe(result_df, use_container_width=True, height=500)

                    csv = result_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download CSV", csv,
                        "query_result.csv", "text/csv")
                else:
                    st.info("Query returned 0 rows.")

            except Exception as e:
                st.error(f"Query error: {e}")

    # Quick templates
    with st.expander("📝 Query Templates"):
        st.code("""-- Top 10 suppliers by spend
SELECT s.company_name, SUM(po.total_value_usd) AS total_spend
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
GROUP BY s.company_name
ORDER BY total_spend DESC LIMIT 10;""", language="sql")

        st.code("""-- FX rate trend for NGN
SELECT rate_date, rate_to_usd
FROM fx_rates
JOIN currencies c ON c.currency_id = fx_rates.currency_id
WHERE c.currency_code = 'NGN'
ORDER BY rate_date;""", language="sql")

        st.code("""-- Overdue shipments
SELECT sh.shipment_id, s.company_name, sh.estimated_arrival,
       sh.actual_arrival, sh.delay_days
FROM shipments sh
JOIN purchase_orders po ON po.po_id = sh.po_id
JOIN suppliers s ON s.supplier_id = po.supplier_id
WHERE sh.delay_days > 7
ORDER BY sh.delay_days DESC LIMIT 20;""", language="sql")
