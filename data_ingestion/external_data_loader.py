"""
AEGIS -- External Data Loader
Allows importing company procurement data from CSV files with schema validation.

USAGE:
    python data_ingestion/external_data_loader.py --input-dir ./company_data

EXPECTED STRUCTURE:
    company_data/
      |- suppliers.csv           (required)
      |- materials.csv           (required)
      |- purchase_orders.csv     (required)
      |- po_line_items.csv       (required)
      |- shipments.csv           (optional)
      |- invoices.csv            (optional)
      |- esg_assessments.csv     (optional)

See EXTERNAL_DATA_GUIDE.md for detailed specifications.
"""

import sys
import os
import argparse
import math
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import DATABASE_URL
    from utils.logging_config import get_logger
except Exception:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root@localhost:3306/aegis_procurement",
    )
    import logging
    def get_logger(name):
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.addHandler(logging.StreamHandler(sys.stdout))
            logger.setLevel(logging.INFO)
        return logger

log = get_logger("external_loader")

ENGINE = create_engine(DATABASE_URL, echo=False)

# ---------------------------------------------------------------------------
#  Schema validation rules
# ---------------------------------------------------------------------------
SCHEMA = {
    "suppliers": {
        "required": ["supplier_name", "country", "currency_code", "lead_time_days"],
        "optional": [
            "supplier_code", "sector", "tier_level", "company_size",
            "annual_revenue_usd", "lead_time_stddev", "defect_rate_pct",
            "payment_terms_days", "is_iso9001_certified", "contact_email",
        ],
        "numeric": ["lead_time_days", "lead_time_stddev", "defect_rate_pct",
                     "annual_revenue_usd", "payment_terms_days"],
    },
    "materials": {
        "required": ["material_name", "category", "standard_cost_usd"],
        "optional": [
            "material_code", "sub_category", "commodity_group",
            "unit_of_measure", "is_critical",
        ],
        "numeric": ["standard_cost_usd"],
    },
    "purchase_orders": {
        "required": ["order_date", "supplier_name", "currency_code", "total_amount"],
        "optional": [
            "po_number", "required_date", "status", "freight_cost_usd",
            "landed_cost_usd", "is_maverick",
        ],
        "numeric": ["total_amount", "freight_cost_usd", "landed_cost_usd"],
    },
    "po_line_items": {
        "required": ["po_number", "material_name", "quantity", "unit_price"],
        "optional": [],
        "numeric": ["quantity", "unit_price"],
    },
    "shipments": {
        "required": ["po_number", "transport_mode", "dispatch_date"],
        "optional": [
            "carrier_name", "origin_port", "destination_port",
            "weight_tonnes", "eta_date", "actual_arrival",
            "final_delivery_date", "status",
        ],
        "numeric": ["weight_tonnes"],
    },
    "invoices": {
        "required": ["po_number", "supplier_name", "invoice_date", "due_date",
                      "amount", "currency_code"],
        "optional": [
            "invoice_number", "amount_usd", "status", "payment_date",
        ],
        "numeric": ["amount", "amount_usd"],
    },
    "esg_assessments": {
        "required": ["supplier_name", "assessment_date", "esg_rating"],
        "optional": [
            "carbon_intensity_score", "waste_management_score",
            "water_usage_score", "labor_practices_score",
            "health_safety_score", "community_impact_score",
            "ethics_compliance_score", "transparency_score",
            "board_diversity_score",
        ],
        "numeric": [
            "carbon_intensity_score", "waste_management_score",
            "water_usage_score", "labor_practices_score",
            "health_safety_score", "community_impact_score",
            "ethics_compliance_score", "transparency_score",
            "board_diversity_score",
        ],
    },
}

VALID_TRANSPORT_MODES = {"Sea", "Air", "Rail", "Road", "Multimodal"}
VALID_PO_STATUSES = {
    "Draft", "Approved", "Shipped", "In Transit",
    "Customs", "Delivered", "Closed", "Cancelled",
}
VALID_SHIP_STATUSES = {
    "Pending", "In Transit", "At Port", "Customs", "Delivered", "Exception",
}
VALID_INVOICE_STATUSES = {
    "Pending", "Approved", "Paid", "Disputed", "Cancelled",
}
VALID_ESG_RATINGS = {"A", "B", "C", "D", "F"}
VALID_TIER_LEVELS = {
    "Strategic", "Preferred", "Approved", "Conditional", "Blocked",
}


# ====================================================================
#  DataValidator
# ====================================================================
class DataValidator:
    """Validates external CSV files against the AEGIS schema."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    # ---- public ------------------------------------------------------
    def validate_file(self, file_path: str, file_type: str) -> bool:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            self.errors.append(f"Failed to read {file_type}: {e}")
            return False

        spec = SCHEMA.get(file_type)
        if not spec:
            self.errors.append(f"Unknown file type: {file_type}")
            return False

        # Required columns
        missing = set(spec["required"]) - set(df.columns)
        if missing:
            self.errors.append(f"{file_type}: Missing required columns: {missing}")
            return False

        if df.empty:
            self.warnings.append(f"{file_type}: File is empty")
            return True

        # Numeric checks
        for col in spec.get("numeric", []):
            if col in df.columns:
                non_numeric = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
                if non_numeric.any():
                    self.warnings.append(
                        f"{file_type}.{col}: {non_numeric.sum()} non-numeric values")

        # File-specific rules
        method = getattr(self, f"_validate_{file_type}", None)
        if method:
            method(df)

        return len(self.errors) == 0

    # ---- private per-file rules --------------------------------------
    def _validate_suppliers(self, df):
        if "lead_time_days" in df.columns:
            bad = df[pd.to_numeric(df["lead_time_days"], errors="coerce") <= 0]
            if not bad.empty:
                self.errors.append("suppliers: lead_time_days must be > 0")

    def _validate_materials(self, df):
        if "standard_cost_usd" in df.columns:
            bad = df[pd.to_numeric(df["standard_cost_usd"], errors="coerce") < 0]
            if not bad.empty:
                self.errors.append("materials: standard_cost_usd cannot be negative")

    def _validate_purchase_orders(self, df):
        if "order_date" in df.columns:
            try:
                pd.to_datetime(df["order_date"])
            except Exception as e:
                self.errors.append(f"purchase_orders: invalid order_date format: {e}")
        if "total_amount" in df.columns:
            bad = df[pd.to_numeric(df["total_amount"], errors="coerce") < 0]
            if not bad.empty:
                self.errors.append("purchase_orders: total_amount cannot be negative")

    def _validate_po_line_items(self, df):
        if "quantity" in df.columns:
            bad = df[pd.to_numeric(df["quantity"], errors="coerce") <= 0]
            if not bad.empty:
                self.warnings.append("po_line_items: quantity should be > 0")
        if "unit_price" in df.columns:
            bad = df[pd.to_numeric(df["unit_price"], errors="coerce") < 0]
            if not bad.empty:
                self.errors.append("po_line_items: unit_price cannot be negative")

    def _validate_shipments(self, df):
        if "transport_mode" in df.columns:
            invalid = set(df["transport_mode"].dropna().unique()) - VALID_TRANSPORT_MODES
            if invalid:
                self.errors.append(
                    f"shipments: invalid transport_mode values: {invalid}. "
                    f"Valid: {VALID_TRANSPORT_MODES}")

    def _validate_invoices(self, df):
        if "amount" in df.columns:
            bad = df[pd.to_numeric(df["amount"], errors="coerce") < 0]
            if not bad.empty:
                self.errors.append("invoices: amount cannot be negative")

    def _validate_esg_assessments(self, df):
        if "esg_rating" in df.columns:
            invalid = set(df["esg_rating"].dropna().unique()) - VALID_ESG_RATINGS
            if invalid:
                self.errors.append(
                    f"esg_assessments: invalid esg_rating values: {invalid}. "
                    f"Valid: {VALID_ESG_RATINGS}")


# ====================================================================
#  ExternalDataLoader
# ====================================================================
class ExternalDataLoader:
    """Load and import external company data into AEGIS."""

    REQUIRED_FILES = ["suppliers", "materials", "purchase_orders", "po_line_items"]
    OPTIONAL_FILES = ["shipments", "invoices", "esg_assessments"]

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.validator = DataValidator()
        self.data: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    #  Phase 1 — Load & validate
    # ------------------------------------------------------------------
    def load_all_files(self) -> bool:
        log.info(f"Loading external data from: {self.input_dir}")


        all_types = self.REQUIRED_FILES + self.OPTIONAL_FILES
        for file_type in all_types:
            file_path = self.input_dir / f"{file_type}.csv"
            required = file_type in self.REQUIRED_FILES

            if not file_path.exists():
                if required:
                    log.error(f"[MISSING] {file_type}.csv  (REQUIRED)")
                    self.validator.errors.append(f"Required file missing: {file_type}.csv")
                else:
                    log.info(f"[SKIP] {file_type}.csv  (optional, not provided)")
                continue

            log.info(f"Validating {file_type}.csv ...")
            if self.validator.validate_file(str(file_path), file_type):
                df = pd.read_csv(file_path)
                self.data[file_type] = df
                log.info(f"  {file_type}.csv [OK] ({len(df)} rows)")
            else:
                log.error(f"  {file_type}.csv [FAIL]")
                for err in self.validator.errors:
                    log.error(f"    Error: {err}")
                self.validator.errors.clear()
                return False

        if self.validator.warnings:
            log.warning("Warnings:")
            for w in self.validator.warnings:
                log.warning(f"  - {w}")
            self.validator.warnings.clear()

        missing_required = [
            f for f in self.REQUIRED_FILES if f not in self.data
        ]
        if missing_required:
            log.error(f"Cannot import: missing required files {missing_required}")
            return False

        return True

    # ------------------------------------------------------------------
    #  Phase 2 — Import into database
    # ------------------------------------------------------------------
    def import_data(self) -> bool:
        if not self.data:
            log.warning("No data to import.")
            return False

        try:
            log.info("Importing data into AEGIS database ...")

            with ENGINE.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            self._clear_tables()

            self._import_suppliers()
            self._import_materials()
            self._import_purchase_orders()
            self._import_po_line_items()

            if "shipments" in self.data:
                self._import_shipments()
            if "invoices" in self.data:
                self._import_invoices()
            if "esg_assessments" in self.data:
                self._import_esg_assessments()

            # Seed FX rates and commodity prices (needed by analytics)
            self._seed_market_data()

            with ENGINE.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            log.info("External data imported successfully!")
            return True

        except Exception as e:
            log.error(f"Import failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    #  Seed FX + commodity data for analytics
    # ------------------------------------------------------------------
    def _seed_market_data(self):
        """Generate FX rates + commodity prices so analytics work."""
        try:
            from data_ingestion.generate_seed_data import seed_fx_rates, seed_commodity_prices
            with ENGINE.begin() as conn:
                # Clear existing market data
                conn.execute(text("DELETE FROM fx_rates"))
                conn.execute(text("DELETE FROM commodity_prices"))
                seed_fx_rates(conn)
                seed_commodity_prices(conn)
            log.info("FX rates & commodity prices seeded")
        except Exception as e:
            log.warning(f"Market data seeding failed: {e}")

    # ------------------------------------------------------------------
    #  Table clearing
    # ------------------------------------------------------------------
    def _clear_tables(self):
        """Clear transactional + analytics tables before import."""
        tables = [
            # analytics
            "concentration_analysis", "risk_assessments", "supplier_scorecards",
            "simulation_runs",
            # warehouse
            "fact_esg", "fact_procurement",
            "dim_geography", "dim_material", "dim_supplier", "dim_date",
            # esg
            "due_diligence_records", "compliance_checks", "carbon_estimates",
            "esg_assessments",
            # transactions
            "quality_incidents", "quality_inspections",
            "invoices", "shipments",
            "po_line_items", "purchase_orders",
            # master
            "supplier_certifications", "supplier_material_catalog",
            "contracts", "materials", "suppliers",
        ]
        with ENGINE.begin() as conn:
            for t in tables:
                try:
                    conn.execute(text(f"DELETE FROM `{t}`"))
                except Exception:
                    pass  # table may not exist yet

    # ------------------------------------------------------------------
    #  Lookup helpers
    # ------------------------------------------------------------------
    def _get_map(self, sql: str) -> dict:
        with ENGINE.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return {r[0]: r[1] for r in rows} if rows else {}

    def _country_map(self) -> dict:
        """country_name (lowercase) -> country_id"""
        return {k.lower(): v for k, v in self._get_map(
            "SELECT country_name, country_id FROM countries").items()}

    def _currency_map(self) -> dict:
        """currency_code -> currency_id"""
        return self._get_map(
            "SELECT currency_code, currency_id FROM currencies")

    def _sector_map(self) -> dict:
        """sector_name (lowercase) -> sector_id"""
        return {k.lower(): v for k, v in self._get_map(
            "SELECT sector_name, sector_id FROM industry_sectors").items()}

    def _supplier_map(self) -> dict:
        """supplier_name -> supplier_id"""
        return self._get_map(
            "SELECT supplier_name, supplier_id FROM suppliers")

    def _material_map(self) -> dict:
        """material_name -> material_id"""
        return self._get_map(
            "SELECT material_name, material_id FROM materials")

    def _po_map(self) -> dict:
        """po_number -> po_id"""
        return self._get_map(
            "SELECT po_number, po_id FROM purchase_orders")

    def _port_map(self) -> dict:
        """port_name (lowercase) -> port_id"""
        return {k.lower(): v for k, v in self._get_map(
            "SELECT port_name, port_id FROM ports").items()}

    # ------------------------------------------------------------------
    #  Import: Suppliers
    # ------------------------------------------------------------------
    def _import_suppliers(self):
        df = self.data["suppliers"].copy()
        country_map = self._country_map()
        currency_map = self._currency_map()
        sector_map = self._sector_map()

        # Resolve FKs
        df["country_id"] = df["country"].str.lower().map(country_map)
        df["default_currency_id"] = df["currency_code"].map(currency_map)

        # Default sector
        default_sector = next(iter(sector_map.values()), 1)
        if "sector" in df.columns:
            df["sector_id"] = df["sector"].str.lower().map(sector_map).fillna(default_sector)
        else:
            df["sector_id"] = default_sector

        # Warn on unmatched countries
        unmatched_c = df[df["country_id"].isna()]["country"].unique()
        if len(unmatched_c):
            log.warning(f"Unmatched countries (skipped): {list(unmatched_c)}")
        unmatched_cur = df[df["default_currency_id"].isna()]["currency_code"].unique()
        if len(unmatched_cur):
            log.warning(f"Unmatched currencies (skipped): {list(unmatched_cur)}")

        df = df.dropna(subset=["country_id", "default_currency_id"])

        # Auto-generate supplier_code if missing
        if "supplier_code" not in df.columns or df["supplier_code"].isna().all():
            df["supplier_code"] = [f"SUP-{str(i+1).zfill(4)}" for i in range(len(df))]

        # Defaults
        df["published_lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce").fillna(30).astype(int)
        df["lead_time_stddev_days"] = pd.to_numeric(
            df.get("lead_time_stddev", df["published_lead_time_days"] * 0.2),
            errors="coerce"
        ).fillna(0)
        df["defect_rate_pct"] = pd.to_numeric(
            df.get("defect_rate_pct", pd.Series([2.0] * len(df))),
            errors="coerce"
        ).fillna(2.0)
        df["payment_terms_days"] = pd.to_numeric(
            df.get("payment_terms_days", pd.Series([30] * len(df))),
            errors="coerce"
        ).fillna(30).astype(int)
        df["annual_revenue_usd"] = pd.to_numeric(
            df.get("annual_revenue_usd", pd.Series([0] * len(df))),
            errors="coerce"
        ).fillna(0)
        df["tier_level"] = df.get("tier_level", pd.Series(["Approved"] * len(df)))
        df["tier_level"] = df["tier_level"].where(df["tier_level"].isin(VALID_TIER_LEVELS), "Approved")
        df["is_iso9001_certified"] = df.get("is_iso9001_certified", False)
        df["onboarding_date"] = date.today().isoformat()
        df["status"] = "Active"

        insert_df = df[[
            "supplier_code", "supplier_name", "country_id", "sector_id",
            "default_currency_id", "tier_level",
            "annual_revenue_usd", "published_lead_time_days",
            "lead_time_stddev_days", "defect_rate_pct",
            "payment_terms_days", "is_iso9001_certified",
            "onboarding_date", "status",
        ]].copy()

        insert_df.to_sql("suppliers", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} suppliers")

    # ------------------------------------------------------------------
    #  Import: Materials
    # ------------------------------------------------------------------
    def _import_materials(self):
        df = self.data["materials"].copy()

        if "material_code" not in df.columns or df["material_code"].isna().all():
            df["material_code"] = [f"MAT-{str(i+1).zfill(4)}" for i in range(len(df))]

        df["standard_cost_usd"] = pd.to_numeric(df["standard_cost_usd"], errors="coerce").fillna(1.0)
        df["commodity_group"] = df.get("commodity_group", df["category"])
        df["unit_of_measure"] = df.get("unit_of_measure", "KG")
        df["is_critical"] = df.get("is_critical", False)

        insert_df = df[[
            "material_code", "material_name", "category",
            "commodity_group", "standard_cost_usd",
            "unit_of_measure", "is_critical",
        ]].copy()
        if "sub_category" in df.columns:
            insert_df["sub_category"] = df["sub_category"]

        insert_df.to_sql("materials", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} materials")

    # ------------------------------------------------------------------
    #  Import: Purchase Orders
    # ------------------------------------------------------------------
    def _import_purchase_orders(self):
        df = self.data["purchase_orders"].copy()
        supplier_map = self._supplier_map()
        currency_map = self._currency_map()

        df["supplier_id"] = df["supplier_name"].map(supplier_map)
        df["currency_id"] = df["currency_code"].map(currency_map)
        df["order_date"] = pd.to_datetime(df["order_date"]).dt.date

        if "required_date" in df.columns:
            df["required_date"] = pd.to_datetime(df["required_date"]).dt.date
        else:
            df["required_date"] = pd.to_datetime(df["order_date"]) + pd.Timedelta(days=45)
            df["required_date"] = df["required_date"].dt.date

        if "po_number" not in df.columns or df["po_number"].isna().all():
            df["po_number"] = [f"PO-EXT-{str(i+1).zfill(6)}" for i in range(len(df))]

        df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)
        df["status"] = df.get("status", "Delivered")
        df["status"] = df["status"].where(df["status"].isin(VALID_PO_STATUSES), "Delivered")
        df["is_maverick"] = df.get("is_maverick", False)
        df["freight_cost_usd"] = pd.to_numeric(df.get("freight_cost_usd", 0), errors="coerce").fillna(0)
        df["landed_cost_usd"] = pd.to_numeric(
            df.get("landed_cost_usd", df["total_amount"]),
            errors="coerce"
        ).fillna(df["total_amount"])

        # Drop unresolved FKs
        unmatched_s = df[df["supplier_id"].isna()]["supplier_name"].unique()
        if len(unmatched_s):
            log.warning(f"Unmatched suppliers (skipped): {list(unmatched_s)}")
        df = df.dropna(subset=["supplier_id", "currency_id"])

        insert_df = df[[
            "po_number", "supplier_id", "order_date", "required_date",
            "currency_id", "total_amount", "freight_cost_usd",
            "landed_cost_usd", "status", "is_maverick",
        ]].copy()

        insert_df.to_sql("purchase_orders", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} purchase orders")

    # ------------------------------------------------------------------
    #  Import: PO Line Items
    # ------------------------------------------------------------------
    def _import_po_line_items(self):
        df = self.data["po_line_items"].copy()
        po_map = self._po_map()
        mat_map = self._material_map()

        df["po_id"] = df["po_number"].map(po_map)
        df["material_id"] = df["material_name"].map(mat_map)
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1)
        df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0)

        unmatched = df[df["po_id"].isna()]["po_number"].unique()
        if len(unmatched):
            log.warning(f"Unmatched PO numbers (skipped): {list(unmatched[:5])}")
        unmatched_m = df[df["material_id"].isna()]["material_name"].unique()
        if len(unmatched_m):
            log.warning(f"Unmatched materials (skipped): {list(unmatched_m[:5])}")

        df = df.dropna(subset=["po_id", "material_id"])

        insert_df = df[["po_id", "material_id", "quantity", "unit_price"]].copy()
        insert_df.to_sql("po_line_items", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} PO line items")

    # ------------------------------------------------------------------
    #  Import: Shipments (optional)
    # ------------------------------------------------------------------
    def _import_shipments(self):
        df = self.data["shipments"].copy()
        po_map = self._po_map()
        port_map = self._port_map()

        df["po_id"] = df["po_number"].map(po_map)
        df["dispatch_date"] = pd.to_datetime(df["dispatch_date"]).dt.date

        if "shipment_ref" not in df.columns or df["shipment_ref"].isna().all():
            df["shipment_ref"] = [f"SH-EXT-{str(i+1).zfill(6)}" for i in range(len(df))]

        # Resolve ports
        if "origin_port" in df.columns:
            df["origin_port_id"] = df["origin_port"].str.lower().map(port_map)
        if "destination_port" in df.columns:
            df["destination_port_id"] = df["destination_port"].str.lower().map(port_map)

        for col in ["eta_date", "actual_arrival", "final_delivery_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            else:
                df[col] = None

        df["weight_tonnes"] = pd.to_numeric(df.get("weight_tonnes", 0), errors="coerce").fillna(0)
        df["status"] = df.get("status", "Delivered")
        df["status"] = df["status"].where(df["status"].isin(VALID_SHIP_STATUSES), "Delivered")

        df = df.dropna(subset=["po_id"])

        cols = [
            "shipment_ref", "po_id", "transport_mode", "dispatch_date",
            "weight_tonnes", "status",
        ]
        for opt in ["carrier_name", "origin_port_id", "destination_port_id",
                     "eta_date", "actual_arrival", "final_delivery_date"]:
            if opt in df.columns:
                cols.append(opt)

        insert_df = df[[c for c in cols if c in df.columns]].copy()
        insert_df.to_sql("shipments", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} shipments")

    # ------------------------------------------------------------------
    #  Import: Invoices (optional)
    # ------------------------------------------------------------------
    def _import_invoices(self):
        df = self.data["invoices"].copy()
        po_map = self._po_map()
        supplier_map = self._supplier_map()
        currency_map = self._currency_map()

        df["po_id"] = df["po_number"].map(po_map)
        df["supplier_id"] = df["supplier_name"].map(supplier_map)
        df["currency_id"] = df["currency_code"].map(currency_map)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"]).dt.date
        df["due_date"] = pd.to_datetime(df["due_date"]).dt.date

        if "invoice_number" not in df.columns or df["invoice_number"].isna().all():
            df["invoice_number"] = [f"INV-EXT-{str(i+1).zfill(6)}" for i in range(len(df))]

        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        df["amount_usd"] = pd.to_numeric(df.get("amount_usd", df["amount"]), errors="coerce").fillna(df["amount"])
        df["status"] = df.get("status", "Paid")
        df["status"] = df["status"].where(df["status"].isin(VALID_INVOICE_STATUSES), "Paid")

        if "payment_date" in df.columns:
            df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce").dt.date

        df = df.dropna(subset=["po_id", "supplier_id", "currency_id"])

        cols = [
            "invoice_number", "po_id", "supplier_id", "invoice_date",
            "due_date", "amount", "currency_id", "amount_usd", "status",
        ]
        if "payment_date" in df.columns:
            cols.append("payment_date")

        insert_df = df[[c for c in cols if c in df.columns]].copy()
        insert_df.to_sql("invoices", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} invoices")

    # ------------------------------------------------------------------
    #  Import: ESG Assessments (optional)
    # ------------------------------------------------------------------
    def _import_esg_assessments(self):
        df = self.data["esg_assessments"].copy()
        supplier_map = self._supplier_map()

        df["supplier_id"] = df["supplier_name"].map(supplier_map)
        df["assessment_date"] = pd.to_datetime(df["assessment_date"]).dt.date

        # Score columns (0-100)
        score_cols = [
            "carbon_intensity_score", "waste_management_score", "water_usage_score",
            "labor_practices_score", "health_safety_score", "community_impact_score",
            "ethics_compliance_score", "transparency_score", "board_diversity_score",
        ]
        for col in score_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").clip(0, 100)
            else:
                df[col] = 50  # default mid-score

        # Compute composites
        df["env_composite"] = df[["carbon_intensity_score", "waste_management_score",
                                   "water_usage_score"]].mean(axis=1).round(2)
        df["social_composite"] = df[["labor_practices_score", "health_safety_score",
                                      "community_impact_score"]].mean(axis=1).round(2)
        df["governance_composite"] = df[["ethics_compliance_score", "transparency_score",
                                          "board_diversity_score"]].mean(axis=1).round(2)
        df["esg_overall_score"] = (
            df["env_composite"] * 0.4 +
            df["social_composite"] * 0.3 +
            df["governance_composite"] * 0.3
        ).round(2)

        df["esg_rating"] = df["esg_rating"].where(
            df["esg_rating"].isin(VALID_ESG_RATINGS), "C")

        df = df.dropna(subset=["supplier_id"])

        insert_cols = [
            "supplier_id", "assessment_date",
        ] + score_cols + [
            "env_composite", "social_composite", "governance_composite",
            "esg_overall_score", "esg_rating",
        ]

        insert_df = df[[c for c in insert_cols if c in df.columns]].copy()
        insert_df.to_sql("esg_assessments", ENGINE, if_exists="append", index=False)
        log.info(f"Imported {len(insert_df)} ESG assessments")


# ====================================================================
#  CLI entry point
# ====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load external company procurement data into AEGIS"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./external_data",
        help="Directory containing CSV input files",
    )

    args = parser.parse_args()

    loader = ExternalDataLoader(args.input_dir)

    if loader.load_all_files():
        if loader.import_data():
            log.info("")
            log.info("Next steps:")
            log.info("  1. Run warehouse ETL:  python data_ingestion/populate_warehouse.py")
            log.info("  2. Run analytics:      python run_aegis_pipeline.py   (steps 4-6 only)")
            log.info("  3. Launch dashboard:   streamlit run streamlit_app.py")
            sys.exit(0)

    sys.exit(1)
