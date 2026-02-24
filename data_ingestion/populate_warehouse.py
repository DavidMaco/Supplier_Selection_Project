"""
AEGIS — Warehouse ETL
Populates the star schema (dim_date, dim_supplier, dim_material,
dim_geography, fact_procurement, fact_esg) from OLTP tables.
"""

import datetime as dt
from sqlalchemy import create_engine, text

import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ENGINE = create_engine(config.DATABASE_URL, echo=False)


# ═════════════════════════════════════════════════════════════════════
#  DIM_DATE — calendar 2022-01-01 → 2028-12-31
# ═════════════════════════════════════════════════════════════════════
def populate_dim_date(conn):
    conn.execute(text("DELETE FROM dim_date"))
    start = dt.date(2022, 1, 1)
    end = dt.date(2028, 12, 31)
    rows = []
    d = start
    while d <= end:
        fiscal_month = (d.month - 3) % 12 + 1  # April fiscal year start
        fiscal_year = d.year if d.month >= 4 else d.year - 1
        fiscal_quarter = (fiscal_month - 1) // 3 + 1

        rows.append({
            "date_key": int(d.strftime("%Y%m%d")),
            "full_date": d,
            "year": d.year,
            "quarter": (d.month - 1) // 3 + 1,
            "month": d.month,
            "month_name": d.strftime("%B"),
            "week_of_year": d.isocalendar()[1],
            "day_of_week": d.isoweekday(),
            "day_name": d.strftime("%A"),
            "is_weekend": d.isoweekday() >= 6,
            "is_month_end": (d + dt.timedelta(days=1)).month != d.month,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
        })
        d += dt.timedelta(days=1)

    chunk = 500
    for i in range(0, len(rows), chunk):
        conn.execute(text("""
            INSERT INTO dim_date (date_key, full_date, `year`, `quarter`, `month`,
                month_name, week_of_year, day_of_week, day_name,
                is_weekend, is_month_end, fiscal_year, fiscal_quarter)
            VALUES (:date_key, :full_date, :year, :quarter, :month,
                :month_name, :week_of_year, :day_of_week, :day_name,
                :is_weekend, :is_month_end, :fiscal_year, :fiscal_quarter)
        """), rows[i:i + chunk])

    print(f"  ✓ dim_date: {len(rows)} rows")


# ═════════════════════════════════════════════════════════════════════
#  DIM_SUPPLIER (SCD Type 2 — initial load = current snapshot)
# ═════════════════════════════════════════════════════════════════════
def populate_dim_supplier(conn):
    conn.execute(text("DELETE FROM dim_supplier"))
    conn.execute(text("""
        INSERT INTO dim_supplier
            (supplier_id, supplier_name, country_name, region,
             sector_name, tier_level, currency_code,
             is_iso9001, esg_rating, risk_tier,
             scd_valid_from, scd_valid_to, scd_is_current)
        SELECT
            s.supplier_id,
            s.supplier_name,
            c.country_name,
            c.region,
            sec.sector_name,
            s.tier_level,
            cur.currency_code,
            s.is_iso9001_certified,
            esg.esg_rating,
            ra.risk_tier,
            CURDATE(),
            NULL,
            TRUE
        FROM suppliers s
        LEFT JOIN countries c ON s.country_id = c.country_id
        LEFT JOIN industry_sectors sec ON s.sector_id = sec.sector_id
        LEFT JOIN currencies cur ON s.default_currency_id = cur.currency_id
        LEFT JOIN (
            SELECT supplier_id, esg_rating,
                   ROW_NUMBER() OVER (PARTITION BY supplier_id ORDER BY assessment_date DESC) rn
            FROM esg_assessments
        ) esg ON s.supplier_id = esg.supplier_id AND esg.rn = 1
        LEFT JOIN (
            SELECT supplier_id, risk_tier,
                   ROW_NUMBER() OVER (PARTITION BY supplier_id ORDER BY assessment_date DESC) rn
            FROM risk_assessments
        ) ra ON s.supplier_id = ra.supplier_id AND ra.rn = 1
    """))
    count = conn.execute(text("SELECT COUNT(*) FROM dim_supplier")).scalar()
    print(f"  ✓ dim_supplier: {count} rows")


# ═════════════════════════════════════════════════════════════════════
#  DIM_MATERIAL
# ═════════════════════════════════════════════════════════════════════
def populate_dim_material(conn):
    conn.execute(text("DELETE FROM dim_material"))
    conn.execute(text("""
        INSERT INTO dim_material
            (material_id, material_name, category, sub_category,
             commodity_group, standard_cost_usd, is_critical)
        SELECT material_id, material_name, category, sub_category,
               commodity_group, standard_cost_usd, is_critical
        FROM materials
    """))
    count = conn.execute(text("SELECT COUNT(*) FROM dim_material")).scalar()
    print(f"  ✓ dim_material: {count} rows")


# ═════════════════════════════════════════════════════════════════════
#  DIM_GEOGRAPHY
# ═════════════════════════════════════════════════════════════════════
def populate_dim_geography(conn):
    conn.execute(text("DELETE FROM dim_geography"))
    conn.execute(text("""
        INSERT INTO dim_geography
            (country_id, country_name, region, sub_region,
             income_group, sanctions_flag)
        SELECT country_id, country_name, region, sub_region,
               income_group, sanctions_flag
        FROM countries
    """))
    count = conn.execute(text("SELECT COUNT(*) FROM dim_geography")).scalar()
    print(f"  ✓ dim_geography: {count} rows")


# ═════════════════════════════════════════════════════════════════════
#  FACT_PROCUREMENT — grain: one PO line item
# ═════════════════════════════════════════════════════════════════════
def populate_fact_procurement(conn):
    conn.execute(text("DELETE FROM fact_procurement"))
    conn.execute(text("""
        INSERT INTO fact_procurement
            (date_key, supplier_key, material_key, geo_key,
             po_id, contract_id, quantity, unit_price_usd,
             line_total_usd, landed_cost_usd, fx_rate_applied,
             standard_cost_usd, cost_variance_usd, cost_variance_pct,
             lead_time_days, delay_days, on_time_flag,
             defect_flag, is_maverick, co2e_kg)
        SELECT
            (YEAR(po.order_date) * 10000 + MONTH(po.order_date) * 100 + DAY(po.order_date)) AS date_key,
            ds.supplier_key,
            dm.material_key,
            dg.geo_key,
            po.po_id,
            po.contract_id,
            li.quantity,
            li.unit_price          AS unit_price_usd,
            li.line_total          AS line_total_usd,
            po.landed_cost_usd,
            fx.rate_to_usd         AS fx_rate_applied,
            m.standard_cost_usd,
            ROUND(li.unit_price - m.standard_cost_usd, 2)
                AS cost_variance_usd,
            ROUND(((li.unit_price - m.standard_cost_usd)
                   / NULLIF(m.standard_cost_usd, 0)) * 100, 2)
                AS cost_variance_pct,
            DATEDIFF(COALESCE(sh.actual_arrival, sh.eta_date), po.order_date)
                AS lead_time_days,
            sh.delay_days,
            (COALESCE(sh.delay_days, 0) <= 0) AS on_time_flag,
            COALESCE(qi.result = 'Fail', FALSE) AS defect_flag,
            po.is_maverick,
            ce.co2e_kg
        FROM po_line_items li
        JOIN purchase_orders po ON li.po_id = po.po_id
        JOIN suppliers sup ON po.supplier_id = sup.supplier_id
        JOIN dim_supplier ds ON sup.supplier_id = ds.supplier_id AND ds.scd_is_current = TRUE
        JOIN materials m ON li.material_id = m.material_id
        JOIN dim_material dm ON m.material_id = dm.material_id
        LEFT JOIN countries ct ON sup.country_id = ct.country_id
        LEFT JOIN dim_geography dg ON ct.country_id = dg.country_id
        LEFT JOIN shipments sh ON po.po_id = sh.po_id
        LEFT JOIN (
            SELECT shipment_id, result,
                   ROW_NUMBER() OVER (PARTITION BY shipment_id ORDER BY inspection_date DESC) rn
            FROM quality_inspections
        ) qi ON sh.shipment_id = qi.shipment_id AND qi.rn = 1
        LEFT JOIN carbon_estimates ce ON sh.shipment_id = ce.shipment_id
        LEFT JOIN fx_rates fx ON po.currency_id = fx.currency_id
            AND fx.rate_date = po.order_date
    """))
    count = conn.execute(text("SELECT COUNT(*) FROM fact_procurement")).scalar()
    print(f"  ✓ fact_procurement: {count} rows")


# ═════════════════════════════════════════════════════════════════════
#  FACT_ESG
# ═════════════════════════════════════════════════════════════════════
def populate_fact_esg(conn):
    conn.execute(text("DELETE FROM fact_esg"))
    conn.execute(text("""
        INSERT INTO fact_esg
            (date_key, supplier_key, env_score, social_score,
             governance_score, overall_score, esg_rating, compliance_gap_count)
        SELECT
            (YEAR(ea.assessment_date) * 10000 + MONTH(ea.assessment_date) * 100 + DAY(ea.assessment_date)),
            ds.supplier_key,
            ea.env_composite         AS env_score,
            ea.social_composite      AS social_score,
            ea.governance_composite  AS governance_score,
            ea.esg_overall_score     AS overall_score,
            ea.esg_rating,
            COALESCE(cc.gap_count, 0)
        FROM esg_assessments ea
        JOIN dim_supplier ds ON ea.supplier_id = ds.supplier_id
            AND ds.scd_is_current = TRUE
        LEFT JOIN (
            SELECT supplier_id, COUNT(*) AS gap_count
            FROM compliance_checks
            WHERE status = 'Non-Compliant'
            GROUP BY supplier_id
        ) cc ON ea.supplier_id = cc.supplier_id
    """))
    count = conn.execute(text("SELECT COUNT(*) FROM fact_esg")).scalar()
    print(f"  ✓ fact_esg: {count} rows")


# ═════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════
def run_etl():
    print("=" * 60)
    print("AEGIS — Warehouse ETL")
    print("=" * 60)

    with ENGINE.begin() as conn:
        print("\n[1/6] dim_date...")
        populate_dim_date(conn)

        print("[2/6] dim_supplier (SCD-2 initial)...")
        populate_dim_supplier(conn)

        print("[3/6] dim_material...")
        populate_dim_material(conn)

        print("[4/6] dim_geography...")
        populate_dim_geography(conn)

        print("[5/6] fact_procurement...")
        populate_fact_procurement(conn)

        print("[6/6] fact_esg...")
        populate_fact_esg(conn)

    print("\n✓ Warehouse ETL complete!")


if __name__ == "__main__":
    run_etl()
