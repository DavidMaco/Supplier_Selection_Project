"""
AEGIS — Master Pipeline Runner
Orchestrates: schema deploy → seed data → warehouse ETL → analytics.
"""

import sys, os, time, argparse, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import config
from utils.logging_config import get_logger, DataQualityLogger

log = get_logger("pipeline")
dq = DataQualityLogger()


def banner(msg: str):
    log.info("=" * 60)
    log.info("  %s", msg)
    log.info("=" * 60)


def step_deploy_schema(engine):
    """Execute SQL schema files in order using raw MySQL connection."""
    banner("Step 1/6 — Deploy Database Schema")
    import pymysql

    # Parse connection info from config
    db_url = config.DATABASE_URL
    # mysql+pymysql://root:Maconoelle86@localhost:3306/aegis_procurement
    parts = db_url.replace("mysql+pymysql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    conn_kwargs = {
        "host": host_port[0],
        "port": int(host_port[1]) if len(host_port) > 1 else 3306,
        "user": user_pass[0],
        "password": user_pass[1] if len(user_pass) > 1 else "",
        "charset": "utf8mb4",
        "client_flag": pymysql.constants.CLIENT.MULTI_STATEMENTS,
    }

    conn = pymysql.connect(**conn_kwargs)
    cursor = conn.cursor()

    # Create database
    cursor.execute("CREATE DATABASE IF NOT EXISTS aegis_procurement CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("USE aegis_procurement")
    conn.commit()

    sql_dir = os.path.join(os.path.dirname(__file__), "database")
    files = sorted(f for f in os.listdir(sql_dir)
                   if f.endswith(".sql") and f != "00_MASTER_DEPLOY.sql")

    for sql_file in files:
        path = os.path.join(sql_dir, sql_file)
        log.info("  Executing %s...", sql_file)
        with open(path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Remove CREATE DATABASE and USE statements (already done above)
        cleaned = re.sub(
            r'CREATE\s+DATABASE\s+.*?;', '', sql_content,
            flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(
            r'^\s*USE\s+\w+\s*;', '', cleaned,
            flags=re.IGNORECASE | re.MULTILINE)

        try:
            cursor.execute(cleaned)
            conn.commit()
            # Consume any remaining results from multi-statement execution
            while cursor.nextset():
                pass
        except Exception as e:
            conn.commit()
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                pass
            else:
                log.warning("    %s: %s", sql_file, e)
        log.info("    [OK] %s", sql_file)

    cursor.close()
    conn.close()
    log.info("  Schema deployment complete.")


def step_seed_reference(engine):
    """Insert reference data from SQL using raw connection."""
    banner("Step 2/6 — Seed Reference Data")
    import pymysql

    db_url = config.DATABASE_URL
    parts = db_url.replace("mysql+pymysql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    conn = pymysql.connect(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 3306,
        user=user_pass[0],
        password=user_pass[1] if len(user_pass) > 1 else "",
        database="aegis_procurement",
        charset="utf8mb4",
        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
    )
    cursor = conn.cursor()

    sql_path = os.path.join(os.path.dirname(__file__),
                            "database", "09_seed_reference_data.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Remove USE statement
    cleaned = re.sub(
        r'^\s*USE\s+\w+\s*;', '', sql_content,
        flags=re.IGNORECASE | re.MULTILINE)

    try:
        cursor.execute(cleaned)
        conn.commit()
        while cursor.nextset():
            pass
    except Exception as e:
        conn.commit()
        if "duplicate" in str(e).lower():
            pass
        else:
            log.warning("    Reference seed: %s", e)

    cursor.close()
    conn.close()
    log.info("  Reference data seeded.")


def step_generate_data():
    """Generate realistic sample data."""
    banner("Step 3/6 — Generate Sample Data")
    from data_ingestion.generate_seed_data import main as generate_main
    generate_main()
    log.info("  Sample data generated.")


def step_populate_warehouse():
    """Run warehouse ETL."""
    banner("Step 4/6 — Populate Data Warehouse")
    from data_ingestion.populate_warehouse import run_etl as warehouse_main
    warehouse_main()
    log.info("  Warehouse populated.")


def step_run_analytics():
    """Run all analytics engines."""
    banner("Step 5/6 — Run Analytics Engines")

    log.info("  Running MCDA scoring...")
    from analytics.mcda_engine import run_mcda
    run_mcda()

    log.info("  Running risk scoring...")
    from analytics.risk_scoring import compute_risk_scores, persist_risk_assessments
    scores = compute_risk_scores()
    persist_risk_assessments(scores)

    log.info("  Running concentration analysis...")
    from analytics.concentration import run_full_concentration_analysis, persist_concentration
    conc_results = run_full_concentration_analysis()
    if conc_results:
        persist_concentration(conc_results)

    log.info("  Running carbon calculations...")
    from analytics.carbon_engine import calculate_emissions
    calculate_emissions()

    log.info("  Running should-cost analysis...")
    from analytics.should_cost import get_leakage_summary
    summary = get_leakage_summary()
    if summary:
        log.info("    Leakage: $%s (%s%%)",
                 f"{summary.get('total_leakage_usd', 0):,.0f}",
                 f"{summary.get('leakage_pct', 0):.1f}")

    log.info("  Running working capital analysis...")
    from analytics.working_capital import analyze_working_capital
    wc = analyze_working_capital()
    if wc:
        log.info("    Avg DPO: %.1f days, Total Spend: $%s",
                 wc.get('avg_dpo', 0), f"{wc.get('total_spend', 0):,.0f}")

    log.info("  Running scenario planner (baseline)...")
    from analytics.scenario_planner import scenario_nearshoring
    try:
        near = scenario_nearshoring()
        if near and "error" not in near:
            log.info("    Nearshoring net impact: $%s",
                     f"{near.get('net_cost_impact', 0):,.0f}")
    except Exception:
        log.info("    Skipped (insufficient data)")

    log.info("  Analytics engines complete.")


def step_verify(engine):
    """Verify data counts across key tables."""
    banner("Step 6/6 — Verification")

    tables = [
        "countries", "currencies", "suppliers", "materials",
        "purchase_orders", "po_line_items", "shipments",
        "invoices", "fx_rates", "commodity_prices",
        "esg_assessments", "carbon_estimates",
        "dim_date", "dim_supplier", "fact_procurement",
        "supplier_scorecards", "risk_assessments",
        "concentration_analysis"
    ]

    with engine.connect() as conn:
        conn.execute(text("USE aegis_procurement"))
        log.info("  %-30s %10s", "Table", "Count")
        log.info("  %s", "-" * 40)
        for tbl in tables:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM `{tbl}`")).scalar()
                status = "OK" if count > 0 else "!! EMPTY"
                log.info("  %-30s %10s  %s", tbl, f"{count:,}", status)
                # Record DQ check
                dq.log(
                    check_name=f"row_count_{tbl}",
                    check_type="Completeness",
                    table_name=tbl,
                    column_name=None,
                    records_checked=count,
                    records_failed=0 if count > 0 else 1,
                    severity="Info" if count > 0 else "Warning",
                    details=f"Row count: {count}",
                )
            except Exception:
                log.warning("  %-30s %10s  MISSING", tbl, "N/A")
                dq.log(
                    check_name=f"table_exists_{tbl}",
                    check_type="Completeness",
                    table_name=tbl,
                    column_name=None,
                    records_checked=0,
                    records_failed=1,
                    severity="Error",
                    details="Table missing from database",
                )

    log.info("  Pipeline verification complete!")


def step_load_external_data(input_dir: str):
    """Import external company data from CSV files."""
    banner("Step 3/6 — Load External Data")
    from data_ingestion.external_data_loader import ExternalDataLoader

    loader = ExternalDataLoader(input_dir)

    if not loader.load_all_files():
        log.error("  External data validation failed. Aborting.")
        sys.exit(1)

    if not loader.import_data():
        log.error("  External data import failed. Aborting.")
        sys.exit(1)

    log.info("  External data loaded successfully.")


def main():
    parser = argparse.ArgumentParser(description="AEGIS Pipeline Runner")
    parser.add_argument("--skip-schema", action="store_true",
                       help="Skip schema deployment")
    parser.add_argument("--skip-seed", action="store_true",
                       help="Skip sample data generation")
    parser.add_argument("--skip-warehouse", action="store_true",
                       help="Skip warehouse ETL")
    parser.add_argument("--skip-analytics", action="store_true",
                       help="Skip analytics engines")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only run verification")
    parser.add_argument("--external", type=str, default=None,
                       metavar="DIR",
                       help="Import external CSV data from DIR instead of generating sample data")
    args = parser.parse_args()

    banner("AEGIS Procurement Intelligence — Pipeline Runner")
    log.info("  Database: %s",
             config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else '***')
    log.info("  Demo Mode: %s", config.DEMO_MODE)
    if args.external:
        log.info("  External Data: %s", os.path.abspath(args.external))

    start = time.time()

    # Use a connection URL without database for schema creation
    base_url = config.DATABASE_URL.rsplit("/", 1)[0]
    engine_base = create_engine(base_url)
    engine = create_engine(config.DATABASE_URL)

    if args.verify_only:
        step_verify(engine)
        return

    if not args.skip_schema:
        step_deploy_schema(engine_base)

    step_seed_reference(engine_base)

    if args.external:
        # External data mode: load from CSV instead of generating
        step_load_external_data(args.external)
    elif not args.skip_seed:
        step_generate_data()

    if not args.skip_warehouse:
        step_populate_warehouse()

    if not args.skip_analytics:
        step_run_analytics()

    step_verify(engine)

    elapsed = time.time() - start
    banner(f"Pipeline Complete — {elapsed:.1f}s")
    log.info("  Launch dashboard:  streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()
