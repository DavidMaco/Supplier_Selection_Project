"""
AEGIS — Risk Scoring Engine
7-dimension supplier risk assessment with composite scoring.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logging_config import get_logger

log = get_logger("risk")

ENGINE = create_engine(config.DATABASE_URL, echo=False)


def compute_risk_scores(supplier_id: int = None) -> pd.DataFrame:
    """
    Compute 7-dimension risk for all or a specific supplier.
    Dimensions: Financial, Operational, Geopolitical, Compliance,
                Concentration, ESG, Cyber
    """
    sid_filter = f"AND s.supplier_id = {supplier_id}" if supplier_id else ""

    with ENGINE.connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT
                s.supplier_id,
                s.supplier_name,
                s.tier_level,
                s.annual_revenue_usd,
                c.wgi_governance_score,
                c.cpi_corruption_score AS cpi,
                c.fragile_state_index AS fsi,
                c.sanctions_flag,
                COALESCE(esg.esg_overall_score, 50) AS esg_score,
                COALESCE(qi_agg.defect_rate, 3) AS avg_defect_rate,
                COALESCE(qi_agg.incident_count, 0) AS incident_count,
                COALESCE(sh_agg.avg_delay, 0) AS avg_delay_days,
                COALESCE(sh_agg.on_time_pct, 70) AS on_time_pct,
                COALESCE(comp.non_compliant_count, 0) AS non_compliant_count,
                COALESCE(cert.cert_count, 0) AS cert_count,
                cur.volatility_class

            FROM suppliers s
            LEFT JOIN countries c ON s.country_id = c.country_id
            LEFT JOIN currencies cur ON s.default_currency_id = cur.currency_id
            LEFT JOIN (
                SELECT ea.supplier_id, ea.esg_overall_score,
                    ROW_NUMBER() OVER (PARTITION BY ea.supplier_id
                        ORDER BY ea.assessment_date DESC) rn
                FROM esg_assessments ea
            ) esg ON s.supplier_id = esg.supplier_id AND esg.rn = 1
            LEFT JOIN (
                SELECT po.supplier_id,
                    AVG(qi.defect_rate_pct) AS defect_rate,
                    COUNT(DISTINCT qinc.incident_id) AS incident_count
                FROM purchase_orders po
                LEFT JOIN shipments sh ON po.po_id = sh.po_id
                LEFT JOIN quality_inspections qi ON sh.shipment_id = qi.shipment_id
                LEFT JOIN quality_incidents qinc ON po.po_id = qinc.po_id
                GROUP BY po.supplier_id
            ) qi_agg ON s.supplier_id = qi_agg.supplier_id
            LEFT JOIN (
                SELECT po.supplier_id,
                    AVG(sh.delay_days) AS avg_delay,
                    AVG(CASE WHEN sh.delay_days <= 0 THEN 100 ELSE 0 END) AS on_time_pct
                FROM shipments sh
                JOIN purchase_orders po ON sh.po_id = po.po_id
                GROUP BY po.supplier_id
            ) sh_agg ON s.supplier_id = sh_agg.supplier_id
            LEFT JOIN (
                SELECT supplier_id, COUNT(*) AS non_compliant_count
                FROM compliance_checks WHERE status = 'Non-Compliant'
                GROUP BY supplier_id
            ) comp ON s.supplier_id = comp.supplier_id
            LEFT JOIN (
                SELECT supplier_id, COUNT(*) AS cert_count
                FROM supplier_certifications WHERE is_verified = TRUE AND expiry_date > CURDATE()
                GROUP BY supplier_id
            ) cert ON s.supplier_id = cert.supplier_id
            WHERE s.status = 'Active' {sid_filter}
        """), conn)

    if df.empty:
        return df

    # ─── Dimension scoring (0-100, higher = riskier) ─────────────
    # Financial: based on revenue (lower = riskier) and tier
    df["financial_risk"] = np.clip(
        100 - df["annual_revenue_usd"].clip(0, 500_000_000) / 5_000_000, 0, 100)

    # Operational: defect rate + delays
    df["operational_risk"] = np.clip(
        df["avg_defect_rate"] * 5 +
        (100 - df["on_time_pct"]) * 0.5 +
        df["incident_count"] * 3, 0, 100)

    # Geopolitical: inverse of WGI, factor in FSI and sanctions
    df["geopolitical_risk"] = np.clip(
        (100 - df["wgi_governance_score"].fillna(50)) * 0.6 +
        df["fsi"].fillna(50) * 0.3 +
        df["sanctions_flag"].astype(int) * 30, 0, 100)

    # Compliance: non-compliant checks + missing certs
    df["compliance_risk"] = np.clip(
        df["non_compliant_count"] * 20 +
        (4 - df["cert_count"].clip(0, 4)) * 10, 0, 100)

    # Concentration: simplified — would need full spend data for HHI
    # Using tier as proxy
    tier_risk = {"Strategic": 15, "Preferred": 25, "Approved": 40,
                 "Conditional": 60, "Blocked": 90}
    df["concentration_risk"] = df["tier_level"].map(tier_risk).fillna(50)

    # ESG risk: inverse of ESG score
    df["esg_risk"] = np.clip(100 - df["esg_score"], 0, 100)

    # Cyber risk: proxy from sector and geo
    vol_risk = {"Low": 10, "Medium": 30, "High": 55, "Extreme": 75}
    df["cyber_risk"] = np.clip(
        df["volatility_class"].map(vol_risk).fillna(30) +
        (100 - df["wgi_governance_score"].fillna(50)) * 0.2 +
        (4 - df["cert_count"].clip(0, 4)) * 5, 0, 100)

    # ─── Composite risk (weighted) ───────────────────────────────
    w = config.RISK_WEIGHTS
    risk_dims = ["financial_risk", "operational_risk", "geopolitical_risk",
                 "compliance_risk", "concentration_risk", "esg_risk", "cyber_risk"]
    weight_order = ["financial_health", "quality_failure", "geopolitical",
                    "lead_time_volatility", "concentration", "esg_compliance",
                    "fx_exposure"]
    weights = np.array([w[k] for k in weight_order])
    weights = weights / weights.sum()

    df["composite_risk"] = np.round(
        df[risk_dims].values @ weights, 2)

    # Tier assignment
    df["risk_tier"] = pd.cut(
        df["composite_risk"],
        bins=[-1, 30, 55, 75, 101],
        labels=["Low", "Medium", "High", "Critical"])

    return df[["supplier_id", "supplier_name"] + risk_dims +
              ["composite_risk", "risk_tier"]]


def persist_risk_assessments(df: pd.DataFrame):
    """Save risk assessments to database."""
    if df.empty:
        return

    records = []
    for _, row in df.iterrows():
        records.append({
            "supplier_id": int(row["supplier_id"]),
            "assessment_date": pd.Timestamp.now().date(),
            "financial_risk": float(row["financial_risk"]),
            "operational_risk": float(row["operational_risk"]),
            "geopolitical_risk": float(row["geopolitical_risk"]),
            "compliance_risk": float(row["compliance_risk"]),
            "concentration_risk": float(row["concentration_risk"]),
            "esg_risk": float(row["esg_risk"]),
            "cyber_risk": float(row["cyber_risk"]),
            "composite_risk": float(row["composite_risk"]),
            "risk_tier": str(row["risk_tier"]),
        })

    with ENGINE.begin() as conn:
        conn.execute(text("""
            INSERT INTO risk_assessments
                (supplier_id, assessment_date,
                 financial_risk, operational_risk, geopolitical_risk,
                 compliance_risk, concentration_risk, esg_risk, cyber_risk,
                 composite_risk, risk_tier)
            VALUES
                (:supplier_id, :assessment_date,
                 :financial_risk, :operational_risk, :geopolitical_risk,
                 :compliance_risk, :concentration_risk, :esg_risk, :cyber_risk,
                 :composite_risk, :risk_tier)
        """), records)

    log.info(f"{len(records)} risk assessments persisted")


def run_risk_scoring(supplier_id: int = None):
    df = compute_risk_scores(supplier_id)
    if df.empty:
        log.warning("No suppliers to assess.")
        return df
    persist_risk_assessments(df)
    return df


if __name__ == "__main__":
    result = run_risk_scoring()
    if not result.empty:
        log.info(result[["supplier_name", "composite_risk", "risk_tier"]]
              .sort_values("composite_risk", ascending=False)
              .head(15).to_string(index=False))
