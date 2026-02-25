"""
AEGIS — Scenario Planner
What-if analysis for procurement decisions:
  - Supplier substitution
  - Currency hedging
  - Volume reallocation
  - Nearshoring impact
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logging_config import get_logger

log = get_logger("scenario")

try:
    from utils.db import get_engine
    ENGINE = get_engine()
except Exception:
    ENGINE = create_engine(config.DATABASE_URL, echo=False)


def scenario_supplier_switch(from_supplier_id: int,
                             to_supplier_id: int,
                             year: int = 2024) -> dict:
    """
    What-if: switch spend from one supplier to another.
    Evaluates cost, lead-time, quality, and ESG impact.
    """
    with ENGINE.connect() as conn:
        # Current supplier metrics
        current = pd.read_sql(text("""
            SELECT
                s.supplier_name,
                COUNT(po.po_id) AS po_count,
                SUM(li.line_total) AS total_spend,
                AVG(sh.delay_days) AS avg_delay,
                AVG(qi.defect_rate_pct) AS avg_defect_rate,
                esg.esg_overall_score AS esg_score,
                smc_avg.avg_price
            FROM suppliers s
            LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
                AND YEAR(po.order_date) = :year
            LEFT JOIN po_line_items li ON po.po_id = li.po_id
            LEFT JOIN shipments sh ON po.po_id = sh.po_id
            LEFT JOIN quality_inspections qi ON sh.shipment_id = qi.shipment_id
            LEFT JOIN (
                SELECT supplier_id, esg_overall_score,
                    ROW_NUMBER() OVER (PARTITION BY supplier_id
                        ORDER BY assessment_date DESC) rn
                FROM esg_assessments
            ) esg ON s.supplier_id = esg.supplier_id AND esg.rn = 1
            LEFT JOIN (
                SELECT supplier_id, AVG(quoted_unit_price) AS avg_price
                FROM supplier_material_catalog GROUP BY supplier_id
            ) smc_avg ON s.supplier_id = smc_avg.supplier_id
            WHERE s.supplier_id = :sid
            GROUP BY s.supplier_name, esg.esg_overall_score, smc_avg.avg_price
        """), conn, params={"sid": from_supplier_id, "year": year})

        alternative = pd.read_sql(text("""
            SELECT
                s.supplier_name,
                AVG(sh.delay_days) AS avg_delay,
                AVG(qi.defect_rate_pct) AS avg_defect_rate,
                esg.esg_overall_score AS esg_score,
                smc_avg.avg_price
            FROM suppliers s
            LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
            LEFT JOIN shipments sh ON po.po_id = sh.po_id
            LEFT JOIN quality_inspections qi ON sh.shipment_id = qi.shipment_id
            LEFT JOIN (
                SELECT supplier_id, esg_overall_score,
                    ROW_NUMBER() OVER (PARTITION BY supplier_id
                        ORDER BY assessment_date DESC) rn
                FROM esg_assessments
            ) esg ON s.supplier_id = esg.supplier_id AND esg.rn = 1
            LEFT JOIN (
                SELECT supplier_id, AVG(quoted_unit_price) AS avg_price
                FROM supplier_material_catalog GROUP BY supplier_id
            ) smc_avg ON s.supplier_id = smc_avg.supplier_id
            WHERE s.supplier_id = :sid
            GROUP BY s.supplier_name, esg.esg_overall_score, smc_avg.avg_price
        """), conn, params={"sid": to_supplier_id})

    if current.empty or alternative.empty:
        return {"error": "One or both suppliers not found"}

    c = current.iloc[0]
    a = alternative.iloc[0]
    spend = float(c["total_spend"] or 0)

    price_change_pct = ((float(a["avg_price"] or 0) - float(c["avg_price"] or 1)) /
                        max(float(c["avg_price"] or 1), 1)) * 100

    return {
        "from_supplier": c["supplier_name"],
        "to_supplier": a["supplier_name"],
        "current_spend": spend,
        "estimated_new_spend": spend * (1 + price_change_pct / 100),
        "cost_impact_pct": round(price_change_pct, 2),
        "delay_change": float(a["avg_delay"] or 0) - float(c["avg_delay"] or 0),
        "quality_change": float(c["avg_defect_rate"] or 0) - float(a["avg_defect_rate"] or 0),
        "esg_change": float(a["esg_score"] or 50) - float(c["esg_score"] or 50),
    }


def scenario_currency_hedge(currency: str,
                            hedge_pct: float = 0.80,
                            forward_premium_pct: float = 2.0,
                            year: int = 2024) -> dict:
    """
    What-if: hedge X% of currency exposure at a forward premium.
    """
    from analytics.monte_carlo import simulate_fx

    current_rate = config.FX_ANCHOR_RATES.get(currency, 1.0)
    forward_rate = current_rate * (1 + forward_premium_pct / 100)

    with ENGINE.connect() as conn:
        exposure = float(conn.execute(text("""
            SELECT COALESCE(SUM(li.line_total), 0)
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            JOIN currencies cur ON po.currency_id = cur.currency_id
            WHERE cur.currency_code = :ccy AND YEAR(po.order_date) = :year
        """), {"ccy": currency, "year": year}).scalar())

    # Simulate unhedged
    sim = simulate_fx(currency, n_paths=5000, horizon_days=90)

    unhedged_cost_mean = exposure * sim["mean"] / current_rate
    unhedged_cost_p95 = exposure * sim["p95"] / current_rate

    hedged_portion = exposure * hedge_pct
    unhedged_portion = exposure * (1 - hedge_pct)

    hedged_cost = hedged_portion * forward_rate / current_rate
    unhedged_cost_sim = unhedged_portion * sim["mean"] / current_rate
    total_hedged_mean = hedged_cost + unhedged_cost_sim

    unhedged_p95_portion = unhedged_portion * sim["p95"] / current_rate
    total_hedged_p95 = hedged_cost + unhedged_p95_portion

    return {
        "currency": currency,
        "exposure_usd": exposure,
        "hedge_pct": hedge_pct,
        "forward_premium_pct": forward_premium_pct,
        "unhedged_mean_cost": round(unhedged_cost_mean, 2),
        "unhedged_worst_case_p95": round(unhedged_cost_p95, 2),
        "hedged_mean_cost": round(total_hedged_mean, 2),
        "hedged_worst_case_p95": round(total_hedged_p95, 2),
        "savings_at_p95": round(unhedged_cost_p95 - total_hedged_p95, 2),
        "hedge_premium_cost": round(hedged_portion * forward_premium_pct / 100, 2),
    }


def scenario_nearshoring(target_region: str = "Africa",
                         realloc_pct: float = 0.30,
                         year: int = 2024) -> dict:
    """
    What-if: reallocate X% of spend to suppliers in target region.
    Models cost, lead-time, and carbon impact.
    """
    with ENGINE.connect() as conn:
        # Current spend by region
        by_region = pd.read_sql(text("""
            SELECT
                c.region,
                SUM(li.line_total) AS spend,
                AVG(sh.delay_days) AS avg_delay,
                AVG(po.freight_cost_usd) AS avg_freight
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            JOIN suppliers s ON po.supplier_id = s.supplier_id
            JOIN countries c ON s.country_id = c.country_id
            LEFT JOIN shipments sh ON po.po_id = sh.po_id
            WHERE YEAR(po.order_date) = :year
            GROUP BY c.region
        """), conn, params={"year": year})

    if by_region.empty:
        return {"error": "No data"}

    total_spend = by_region["spend"].sum()
    current_target = by_region[by_region["region"] == target_region]
    current_target_pct = (float(current_target["spend"].sum()) / total_spend * 100
                         ) if not current_target.empty else 0

    realloc_amount = total_spend * realloc_pct

    # Assume nearshoring has: lower freight, slightly higher unit cost, faster delivery
    cost_premium = 0.05  # 5% higher unit cost
    freight_savings = 0.40  # 40% lower freight
    lead_time_reduction = 0.30  # 30% faster

    new_cost = realloc_amount * (1 + cost_premium)
    freight_saved = realloc_amount * 0.08 * freight_savings  # 8% of spend is freight
    net_impact = new_cost - realloc_amount - freight_saved

    return {
        "target_region": target_region,
        "current_target_share_pct": round(current_target_pct, 1),
        "reallocation_pct": realloc_pct * 100,
        "reallocation_amount": round(realloc_amount, 0),
        "cost_premium_impact": round(realloc_amount * cost_premium, 0),
        "freight_savings": round(freight_saved, 0),
        "net_cost_impact": round(net_impact, 0),
        "lead_time_improvement_pct": lead_time_reduction * 100,
        "carbon_reduction_pct": round(freight_savings * 60, 1),  # Proxy
        "by_region": by_region,
    }


if __name__ == "__main__":
    log.info("=== Supplier Switch Scenario ===")
    switch = scenario_supplier_switch(1, 5)
    for k, v in switch.items():
        log.info(f"  {k}: {v}")

    log.info("=== Nearshoring Scenario ===")
    near = scenario_nearshoring("Africa", 0.30)
    for k, v in near.items():
        if not isinstance(v, pd.DataFrame):
            log.info(f"  {k}: {v}")
