"""
AEGIS — Export Utilities
Generate Excel and CSV exports for dashboard data.
"""

import io
import datetime as dt
import pandas as pd
from utils.logging_config import get_logger

log = get_logger("export")


def to_excel_bytes(dataframes: dict[str, pd.DataFrame]) -> bytes:
    """
    Convert multiple DataFrames into a single Excel workbook (bytes).
    Keys become sheet names.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in dataframes.items():
            # Truncate sheet names to 31 chars (Excel limit)
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Convert a single DataFrame to CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


def generate_executive_summary(engine) -> dict[str, pd.DataFrame]:
    """
    Pull key executive summary data from the database.
    Returns dict of DataFrames ready for Excel export.
    """
    from sqlalchemy import text

    sheets = {}

    try:
        with engine.connect() as conn:
            # Supplier Scorecards
            sheets["Supplier Scorecards"] = pd.read_sql(
                "SELECT s.supplier_name, sc.overall_score, sc.tier, sc.assessment_date "
                "FROM supplier_scorecards sc "
                "JOIN suppliers s ON s.supplier_id = sc.supplier_id "
                "ORDER BY sc.overall_score DESC",
                conn,
            )

            # Risk Assessments
            sheets["Risk Assessments"] = pd.read_sql(
                "SELECT s.supplier_name, r.composite_score, r.risk_tier, r.assessed_at "
                "FROM risk_assessments r "
                "JOIN suppliers s ON s.supplier_id = r.supplier_id "
                "ORDER BY r.composite_score DESC",
                conn,
            )

            # Concentration Analysis
            sheets["Concentration"] = pd.read_sql(
                "SELECT dimension, entity_name, market_share_pct, hhi_score, risk_level "
                "FROM concentration_analysis "
                "ORDER BY dimension, hhi_score DESC",
                conn,
            )

            # Spend Summary
            sheets["Spend Summary"] = pd.read_sql(
                "SELECT s.supplier_name, COUNT(po.po_id) AS po_count, "
                "       SUM(li.line_total) AS total_spend "
                "FROM suppliers s "
                "LEFT JOIN purchase_orders po ON po.supplier_id = s.supplier_id "
                "LEFT JOIN po_line_items li ON li.po_id = po.po_id "
                "GROUP BY s.supplier_name "
                "ORDER BY total_spend DESC",
                conn,
            )

            # Carbon Estimates
            sheets["Carbon Emissions"] = pd.read_sql(
                "SELECT * FROM carbon_estimates ORDER BY total_co2_kg DESC",
                conn,
            )

    except Exception as e:
        log.warning("Executive summary export partial: %s", e)

    return sheets
