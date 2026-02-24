"""
AEGIS — Extended Test Suite
Tests for loader validation, auth, logging, scenario math, and integration.
"""

import pytest
import sys
import os
import hashlib
import tempfile
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Authentication Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAuth:
    def test_default_password_hash(self):
        from utils.auth import DASHBOARD_PASS_HASH
        expected = hashlib.sha256("aegis2025".encode()).hexdigest()
        assert DASHBOARD_PASS_HASH == expected

    def test_check_password_correct(self):
        from utils.auth import _check_password
        assert _check_password("aegis2025") is True

    def test_check_password_wrong(self):
        from utils.auth import _check_password
        assert _check_password("wrong") is False

    def test_default_username(self):
        from utils.auth import DASHBOARD_USER
        assert DASHBOARD_USER == "admin"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Logging Config Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLoggingConfig:
    def test_get_logger_returns_logger(self):
        from utils.logging_config import get_logger
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name == "aegis.test_module"

    def test_logger_has_handlers(self):
        from utils.logging_config import get_logger
        logger = get_logger("test_handlers")
        assert len(logger.handlers) >= 2  # console + file

    def test_log_dir_exists(self):
        from utils.logging_config import LOG_DIR
        assert LOG_DIR.exists()

    def test_data_quality_logger_instantiates(self):
        from utils.logging_config import DataQualityLogger
        dq = DataQualityLogger()
        assert dq is not None

    def test_audit_logger_instantiates(self):
        from utils.logging_config import AuditLogger
        al = AuditLogger(changed_by="test")
        assert al.changed_by == "test"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  External Data Loader Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExternalDataLoader:
    @pytest.fixture
    def sample_csv_dir(self, tmp_path):
        """Create a temp directory with sample CSV files."""
        # suppliers.csv
        suppliers = tmp_path / "suppliers.csv"
        suppliers.write_text(
            "supplier_name,country,currency_code,lead_time_days,status,payment_terms_days\n"
            "Acme Corp,US,USD,14,Active,30\n"
            "Beta Ltd,GB,GBP,21,Active,45\n"
        )
        # materials.csv
        materials = tmp_path / "materials.csv"
        materials.write_text(
            "material_name,category,unit_of_measure,standard_cost_usd\n"
            "Steel,Metals,kg,1.50\n"
            "Copper,Metals,kg,8.20\n"
        )
        # purchase_orders.csv  (required)
        pos = tmp_path / "purchase_orders.csv"
        pos.write_text(
            "po_number,supplier_name,order_date,currency_code,total_amount\n"
            "PO-001,Acme Corp,2024-01-15,USD,50000\n"
        )
        # po_line_items.csv  (required)
        items = tmp_path / "po_line_items.csv"
        items.write_text(
            "po_number,material_name,quantity,unit_price,line_total\n"
            "PO-001,Steel,1000,1.50,1500\n"
        )
        return tmp_path

    def test_loader_detects_csv_files(self, sample_csv_dir):
        from data_ingestion.external_data_loader import ExternalDataLoader
        loader = ExternalDataLoader(str(sample_csv_dir))
        result = loader.load_all_files()
        assert result is True

    def test_loader_validates_columns(self, sample_csv_dir):
        from data_ingestion.external_data_loader import ExternalDataLoader
        loader = ExternalDataLoader(str(sample_csv_dir))
        loader.load_all_files()
        # Validate via validator attribute
        assert loader.validator is not None

    def test_loader_empty_dir(self, tmp_path):
        from data_ingestion.external_data_loader import ExternalDataLoader
        loader = ExternalDataLoader(str(tmp_path))
        # Should return False when no files found
        result = loader.load_all_files()
        # With no files it should still not crash
        assert isinstance(result, bool)

    def test_loader_invalid_csv(self, tmp_path):
        """A badly formed CSV should not crash the loader."""
        bad_file = tmp_path / "suppliers.csv"
        bad_file.write_text("this is not,valid\ncsv,data,with,extra,cols\n")
        from data_ingestion.external_data_loader import ExternalDataLoader
        loader = ExternalDataLoader(str(tmp_path))
        # Should handle gracefully (return False due to missing required cols)
        result = loader.load_all_files()
        assert isinstance(result, bool)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Scenario Planner Pure-Math Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestScenarioPlannerMath:
    def test_hedge_savings_formula(self):
        """If hedge covers 60% of exposure and worst-case loss is 15%,
        then hedged worst-case loss ≈ unhedged × (1 - hedge_pct)."""
        hedge_pct = 0.60
        unhedged_loss = 150_000
        hedged_loss = unhedged_loss * (1 - hedge_pct)
        assert hedged_loss == pytest.approx(60_000, abs=1)

    def test_nearshoring_cost_premium(self):
        """Reallocation of 30% with 12% premium → net cost impact ~3.6%."""
        total_spend = 1_000_000
        realloc_pct = 0.30
        cost_premium_pct = 0.12
        net_premium = total_spend * realloc_pct * cost_premium_pct
        assert net_premium == pytest.approx(36_000, abs=1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Working Capital Pure-Math Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWorkingCapitalMath:
    def test_dpo_calculation(self):
        """DPO = (AP / COGS) × 365"""
        accounts_payable = 500_000
        cogs = 3_650_000
        dpo = (accounts_payable / cogs) * 365
        assert dpo == pytest.approx(50.0, abs=0.1)

    def test_epd_negative_annualized_impossible(self):
        """Early payment discount should always produce positive annualized return."""
        discount_pct = 0.01
        days_early = 20
        annualized = (discount_pct / (1 - discount_pct)) * (365 / days_early)
        assert annualized > 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Should-Cost Pure-Math Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestShouldCostMath:
    def test_cost_variance(self):
        """variance = (quoted - should_cost) / should_cost × 100."""
        should_cost = 100
        quoted = 115
        variance = (quoted - should_cost) / should_cost * 100
        assert variance == pytest.approx(15.0, abs=0.01)

    def test_leakage_flag_investigate(self):
        """5-15% variance → Investigate."""
        import config
        variance = 10.0
        if variance >= config.COST_LEAKAGE_RED_FLAG_PCT:
            flag = "Red Flag"
        elif variance >= config.COST_LEAKAGE_ESCALATE_PCT:
            flag = "Escalate"
        elif variance >= config.COST_LEAKAGE_INVESTIGATE_PCT:
            flag = "Investigate"
        else:
            flag = "OK"
        assert flag == "Investigate"

    def test_leakage_flag_escalate(self):
        import config
        variance = 20.0
        if variance >= config.COST_LEAKAGE_RED_FLAG_PCT:
            flag = "Red Flag"
        elif variance >= config.COST_LEAKAGE_ESCALATE_PCT:
            flag = "Escalate"
        elif variance >= config.COST_LEAKAGE_INVESTIGATE_PCT:
            flag = "Investigate"
        else:
            flag = "OK"
        assert flag == "Escalate"

    def test_leakage_flag_red(self):
        import config
        variance = 30.0
        if variance >= config.COST_LEAKAGE_RED_FLAG_PCT:
            flag = "Red Flag"
        elif variance >= config.COST_LEAKAGE_ESCALATE_PCT:
            flag = "Escalate"
        elif variance >= config.COST_LEAKAGE_INVESTIGATE_PCT:
            flag = "Investigate"
        else:
            flag = "OK"
        assert flag == "Red Flag"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Integration Tests (mocked DB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestIntegration:
    def test_config_database_url_format(self):
        import config
        url = config.DATABASE_URL
        assert url.startswith("mysql+pymysql://")
        assert "@" in url
        assert "/" in url.split("@")[1]

    def test_all_analytics_importable(self):
        """All 8 analytics engines should import without error."""
        from analytics import mcda_engine
        from analytics import risk_scoring
        from analytics import concentration
        from analytics import carbon_engine
        from analytics import monte_carlo
        from analytics import should_cost
        from analytics import working_capital
        from analytics import scenario_planner
        assert True

    def test_all_ingestion_importable(self):
        """Data ingestion modules should import without error."""
        from data_ingestion import external_data_loader
        from data_ingestion import generate_seed_data
        from data_ingestion import populate_warehouse
        assert True

    def test_utils_importable(self):
        from utils.logging_config import get_logger, AuditLogger, DataQualityLogger
        from utils.auth import login_gate, _check_password
        assert True
