"""
Unit tests for Should-Cost model arithmetic and cost-leakage thresholds.
No database required — tests the cost-component formulas and config thresholds
using hardcoded inputs.
"""

import numpy as np
import pandas as pd
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel_path):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


cfg = _load("config", "config.py")


# ═══════════════════════════════════════════════════════════════════
#  Should-Cost component arithmetic (mirrors build_should_cost logic)
# ═══════════════════════════════════════════════════════════════════

FREIGHT_PCT = {
    "Africa": 0.12, "Europe": 0.05, "Asia": 0.08,
    "Americas": 0.06, "Oceania": 0.10,
}
OVERHEAD_PCT = 0.05
MARGIN_PCT = 0.12


def _compute_should_cost(material_cost: float, region: str) -> float:
    """Replicate the should-cost formula from analytics/should_cost.py."""
    freight = material_cost * FREIGHT_PCT.get(region, 0.08)
    customs_duty_pct = 0.10 if region == "Africa" else (0.07 if region == "Asia" else 0.03)
    customs = material_cost * customs_duty_pct
    overhead = material_cost * OVERHEAD_PCT
    margin = material_cost * MARGIN_PCT
    return material_cost + freight + customs + overhead + margin


def _classify_leakage(variance_pct: float) -> str:
    if variance_pct <= cfg.COST_LEAKAGE_INVESTIGATE_PCT:
        return "Within Range"
    elif variance_pct <= cfg.COST_LEAKAGE_ESCALATE_PCT:
        return "Investigate"
    elif variance_pct <= cfg.COST_LEAKAGE_RED_FLAG_PCT:
        return "Escalate"
    return "Red Flag"


# ─── Africa region ──────────────────────────────────────────────

def test_should_cost_africa():
    """Material $100, Africa: 100 + 12 + 10 + 5 + 12 = $139."""
    result = _compute_should_cost(100.0, "Africa")
    assert abs(result - 139.0) < 1e-9


# ─── Europe region ──────────────────────────────────────────────

def test_should_cost_europe():
    """Material $100, Europe: 100 + 5 + 3 + 5 + 12 = $125."""
    result = _compute_should_cost(100.0, "Europe")
    assert abs(result - 125.0) < 1e-9


# ─── Asia region ────────────────────────────────────────────────

def test_should_cost_asia():
    """Material $100, Asia: 100 + 8 + 7 + 5 + 12 = $132."""
    result = _compute_should_cost(100.0, "Asia")
    assert abs(result - 132.0) < 1e-9


# ─── Americas region ───────────────────────────────────────────

def test_should_cost_americas():
    """Material $100, Americas: 100 + 6 + 3 + 5 + 12 = $126."""
    result = _compute_should_cost(100.0, "Americas")
    assert abs(result - 126.0) < 1e-9


# ─── Unknown region fallback ───────────────────────────────────

def test_should_cost_unknown_region_uses_default_freight():
    """Unknown region uses 0.08 freight + 0.03 customs."""
    result = _compute_should_cost(100.0, "Unknown")
    expected = 100 + 8 + 3 + 5 + 12  # 128
    assert abs(result - expected) < 1e-9


# ─── Leakage classification ───────────────────────────────────

def test_leakage_within_range():
    assert _classify_leakage(0.0) == "Within Range"
    assert _classify_leakage(4.9) == "Within Range"
    assert _classify_leakage(5.0) == "Within Range"


def test_leakage_investigate():
    assert _classify_leakage(5.1) == "Investigate"
    assert _classify_leakage(10.0) == "Investigate"
    assert _classify_leakage(15.0) == "Investigate"


def test_leakage_escalate():
    assert _classify_leakage(15.1) == "Escalate"
    assert _classify_leakage(20.0) == "Escalate"
    assert _classify_leakage(25.0) == "Escalate"


def test_leakage_red_flag():
    assert _classify_leakage(25.1) == "Red Flag"
    assert _classify_leakage(50.0) == "Red Flag"
    assert _classify_leakage(100.0) == "Red Flag"


# ─── Config thresholds sanity ──────────────────────────────────

def test_leakage_thresholds_are_ordered():
    assert cfg.COST_LEAKAGE_INVESTIGATE_PCT < cfg.COST_LEAKAGE_ESCALATE_PCT
    assert cfg.COST_LEAKAGE_ESCALATE_PCT < cfg.COST_LEAKAGE_RED_FLAG_PCT


def test_leakage_thresholds_are_positive():
    assert cfg.COST_LEAKAGE_INVESTIGATE_PCT > 0
    assert cfg.COST_LEAKAGE_ESCALATE_PCT > 0
    assert cfg.COST_LEAKAGE_RED_FLAG_PCT > 0


# ─── End-to-end scenario ──────────────────────────────────────

def test_should_cost_scenario_quoted_vs_modeled():
    """
    Supplier quotes $150 for a $100 material from Asia.
    Should-cost = $132. Variance = (150-132)/132 = 13.6%. → Investigate.
    """
    should = _compute_should_cost(100.0, "Asia")
    quoted = 150.0
    variance_pct = (quoted - should) / should * 100
    flag = _classify_leakage(variance_pct)
    assert abs(should - 132.0) < 1e-9
    assert abs(variance_pct - 13.636363636) < 0.01
    assert flag == "Investigate"


def test_should_cost_scenario_underpriced():
    """
    Supplier quotes $120 for $100 material from Europe.
    Should-cost = $125. Variance = (120-125)/125 = -4%. → Within Range.
    """
    should = _compute_should_cost(100.0, "Europe")
    quoted = 120.0
    variance_pct = (quoted - should) / should * 100
    flag = _classify_leakage(variance_pct)
    assert variance_pct < 0
    assert flag == "Within Range"
