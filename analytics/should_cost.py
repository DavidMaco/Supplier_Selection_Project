"""
AEGIS — Should-Cost Model
Bottom-up cost estimation using material, labour, logistics,
and overhead factors. Identifies cost leakage vs. quoted prices.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logging_config import get_logger

log = get_logger("should_cost")

try:
    from utils.db import get_engine
    ENGINE = get_engine()
except Exception:
    ENGINE = create_engine(config.DATABASE_URL, echo=False)


def build_should_cost(material_id: int = None, year: int = 2024) -> pd.DataFrame:
    """
    Build should-cost estimate per material-supplier combination.
    Components: material, freight, customs, overhead, margin.
    """
    mat_filter = f"AND m.material_id = {material_id}" if material_id else ""

    with ENGINE.connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT
                m.material_id,
                m.material_name,
                m.category,
                m.standard_cost_usd,
                m.commodity_group,
                s.supplier_id,
                s.supplier_name,
                c.country_name,
                c.region,
                smc.quoted_unit_price,
                smc.lead_time_days,
                cur.currency_code,
                COALESCE(fx.rate_to_usd, 1.0) AS fx_rate,
                p_dest.avg_customs_days
            FROM supplier_material_catalog smc
            JOIN materials m ON smc.material_id = m.material_id
            JOIN suppliers s ON smc.supplier_id = s.supplier_id
            LEFT JOIN countries c ON s.country_id = c.country_id
            LEFT JOIN currencies cur ON smc.currency_id = cur.currency_id
            LEFT JOIN (
                SELECT currency_id, rate_to_usd,
                    ROW_NUMBER() OVER (PARTITION BY currency_id
                        ORDER BY rate_date DESC) rn
                FROM fx_rates
            ) fx ON cur.currency_id = fx.currency_id AND fx.rn = 1
            LEFT JOIN ports p_dest ON p_dest.port_id = (
                SELECT port_id FROM ports LIMIT 1
            )
            WHERE 1=1 {mat_filter}
            ORDER BY m.material_id, smc.quoted_unit_price
        """), conn)

    if df.empty:
        return df

    # ─── Should-cost components ─────────────────────────────────
    # Material cost (base = standard cost adjusted for commodity index)
    df["material_cost"] = df["standard_cost_usd"]

    # Freight estimate (% of material cost based on region)
    freight_pct = {
        "Africa": 0.12, "Europe": 0.05, "Asia": 0.08,
        "Americas": 0.06, "Oceania": 0.10
    }
    df["freight_pct"] = df["region"].map(freight_pct).fillna(0.08)
    df["freight_cost"] = df["material_cost"] * df["freight_pct"]

    # Customs & duties (based on HS code / country combination)
    df["customs_duty_pct"] = np.where(
        df["region"] == "Africa", 0.10,
        np.where(df["region"] == "Asia", 0.07, 0.03))
    df["customs_cost"] = df["material_cost"] * df["customs_duty_pct"]

    # Overhead (handling, insurance, admin)
    df["overhead_cost"] = df["material_cost"] * 0.05

    # Supplier margin assumption
    df["margin_pct"] = 0.12  # 12% assumed margin
    df["margin_cost"] = df["material_cost"] * df["margin_pct"]

    # Total should-cost
    df["should_cost_usd"] = (df["material_cost"] + df["freight_cost"] +
                             df["customs_cost"] + df["overhead_cost"] +
                             df["margin_cost"])

    # Quoted unit price in USD
    df["quoted_usd"] = df["quoted_unit_price"] / df["fx_rate"].replace(0, 1)

    # Variance analysis
    df["cost_variance_usd"] = df["quoted_usd"] - df["should_cost_usd"]
    df["cost_variance_pct"] = (df["cost_variance_usd"] /
                                df["should_cost_usd"].replace(0, 1) * 100)

    # Classification
    df["leakage_flag"] = pd.cut(
        df["cost_variance_pct"],
        bins=[-np.inf,
              config.COST_LEAKAGE_INVESTIGATE_PCT,
              config.COST_LEAKAGE_ESCALATE_PCT,
              config.COST_LEAKAGE_RED_FLAG_PCT,
              np.inf],
        labels=["Within Range", "Investigate", "Escalate", "Red Flag"])

    return df


def get_leakage_summary(year: int = 2024) -> dict:
    """Aggregate cost leakage analysis."""
    df = build_should_cost(year=year)
    if df.empty:
        return {}

    total_quoted = df["quoted_usd"].sum()
    total_should = df["should_cost_usd"].sum()
    leakage = total_quoted - total_should

    summary = {
        "total_quoted_usd": total_quoted,
        "total_should_cost_usd": total_should,
        "total_leakage_usd": leakage,
        "leakage_pct": (leakage / total_should * 100) if total_should else 0,
        "items_in_range": int((df["leakage_flag"] == "Within Range").sum()),
        "items_investigate": int((df["leakage_flag"] == "Investigate").sum()),
        "items_escalate": int((df["leakage_flag"] == "Escalate").sum()),
        "items_red_flag": int((df["leakage_flag"] == "Red Flag").sum()),
        "top_overpriced": df.nlargest(10, "cost_variance_pct")[
            ["supplier_name", "material_name", "quoted_usd",
             "should_cost_usd", "cost_variance_pct", "leakage_flag"]
        ],
        "detail": df,
    }
    return summary


if __name__ == "__main__":
    summary = get_leakage_summary()
    if summary:
        log.info(f"Total Quoted: ${summary['total_quoted_usd']:,.0f}")
        log.info(f"Total Should-Cost: ${summary['total_should_cost_usd']:,.0f}")
        log.info(f"Leakage: ${summary['total_leakage_usd']:,.0f} ({summary['leakage_pct']:.1f}%)")
        log.info(f"Flags: {summary['items_in_range']} OK, "
              f"{summary['items_investigate']} Investigate, "
              f"{summary['items_escalate']} Escalate, "
              f"{summary['items_red_flag']} Red Flag")
