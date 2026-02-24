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


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


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
        print(f"  Executing {sql_file}...")
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
                print(f"    Warning: {e}")
        print(f"    [OK] {sql_file}")

    cursor.close()
    conn.close()
    print("  Schema deployment complete.")


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
            print(f"    Warning: {e}")

    cursor.close()
    conn.close()
    print("  Reference data seeded.")


def step_generate_data():
    """Generate realistic sample data."""
    banner("Step 3/6 — Generate Sample Data")
    from data_ingestion.generate_seed_data import main as generate_main
    generate_main()
    print("  Sample data generated.")


def step_populate_warehouse():
    """Run warehouse ETL."""
    banner("Step 4/6 — Populate Data Warehouse")
    from data_ingestion.populate_warehouse import run_etl as warehouse_main
    warehouse_main()
    print("  Warehouse populated.")


def step_run_analytics():
    """Run all analytics engines."""
    banner("Step 5/6 — Run Analytics Engines")

    print("  Running MCDA scoring...")
    from analytics.mcda_engine import run_mcda
    run_mcda()

    print("  Running risk scoring...")
    from analytics.risk_scoring import compute_risk_scores, persist_risk_assessments
    scores = compute_risk_scores()
    persist_risk_assessments(scores)

    print("  Running concentration analysis...")
    from analytics.concentration import run_full_concentration_analysis, persist_concentration
    conc_results = run_full_concentration_analysis()
    if conc_results:
        persist_concentration(conc_results)

    print("  Running carbon calculations...")
    from analytics.carbon_engine import calculate_emissions
    calculate_emissions()

    print("  Analytics engines complete.")


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
        print(f"  {'Table':<30} {'Count':>10}")
        print(f"  {'-'*40}")
        for tbl in tables:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM `{tbl}`")).scalar()
                status = "OK" if count > 0 else "!! EMPTY"
                print(f"  {tbl:<30} {count:>10,}  {status}")
            except Exception:
                print(f"  {tbl:<30} {'N/A':>10}  MISSING")

    print("\n  Pipeline verification complete!")


def step_load_external_data(input_dir: str):
    """Import external company data from CSV files."""
    banner("Step 3/6 — Load External Data")
    from data_ingestion.external_data_loader import ExternalDataLoader

    loader = ExternalDataLoader(input_dir)

    if not loader.load_all_files():
        print("  [FAIL] External data validation failed. Aborting.")
        sys.exit(1)

    if not loader.import_data():
        print("  [FAIL] External data import failed. Aborting.")
        sys.exit(1)

    print("  External data loaded successfully.")


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
    print(f"  Database: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else config.DATABASE_URL}")
    print(f"  Demo Mode: {config.DEMO_MODE}")
    if args.external:
        print(f"  External Data: {os.path.abspath(args.external)}")

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
    print(f"\n  Launch dashboard:  streamlit run streamlit_app.py\n")


if __name__ == "__main__":
    main()
