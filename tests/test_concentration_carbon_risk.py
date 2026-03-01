"""
Unit tests for Concentration (HHI), Carbon (haversine), and Risk scoring engines.
No database required — uses hardcoded inputs with known-correct expected outputs.
"""

import math
import numpy as np
import pandas as pd
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ─── Load modules via importlib (avoids DB connection on import) ─────

def _load(name, rel_path):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


concentration = _load("concentration", "analytics/concentration.py")
carbon = _load("carbon_engine", "analytics/carbon_engine.py")
cfg = _load("config", "config.py")


# ═══════════════════════════════════════════════════════════════════
#  HHI — Herfindahl–Hirschman Index
# ═══════════════════════════════════════════════════════════════════

def test_hhi_monopoly():
    """Single supplier with 100% share → HHI = 10 000."""
    assert concentration.compute_hhi([100]) == 10_000.0


def test_hhi_duopoly_equal():
    """Two equal suppliers → 50² + 50² = 5000."""
    result = concentration.compute_hhi([50, 50])
    assert abs(result - 5000.0) < 1e-9


def test_hhi_perfectly_competitive():
    """10 equal suppliers → 10 × 10² = 1000."""
    shares = [10] * 10
    result = concentration.compute_hhi(shares)
    assert abs(result - 1000.0) < 1e-9


def test_hhi_three_suppliers():
    """50² + 30² + 20² = 2500 + 900 + 400 = 3800."""
    result = concentration.compute_hhi([50, 30, 20])
    assert abs(result - 3800.0) < 1e-9


def test_hhi_fractional_shares():
    """Shares that don't sum to 100 (market share percentages)."""
    hhi = concentration.compute_hhi([33.3, 33.3, 33.4])
    assert abs(hhi - (33.3**2 + 33.3**2 + 33.4**2)) < 1e-6


# ═══════════════════════════════════════════════════════════════════
#  HHI Categorization (uses config thresholds)
# ═══════════════════════════════════════════════════════════════════

def test_categorize_hhi_below_competitive():
    assert concentration.categorize_hhi(1000) == "Low"
    assert concentration.categorize_hhi(0) == "Low"


def test_categorize_hhi_at_competitive_boundary():
    """At exactly HHI_COMPETITIVE (1500), should be Moderate."""
    assert concentration.categorize_hhi(cfg.HHI_COMPETITIVE) == "Moderate"


def test_categorize_hhi_moderate_range():
    assert concentration.categorize_hhi(2000) == "Moderate"


def test_categorize_hhi_at_moderate_boundary():
    """At exactly HHI_MODERATE (2500), should be High."""
    assert concentration.categorize_hhi(cfg.HHI_MODERATE) == "High"


def test_categorize_hhi_high_range():
    assert concentration.categorize_hhi(4000) == "High"


def test_categorize_hhi_above_concentrated():
    """At and above HHI_CONCENTRATED (5000), still High."""
    assert concentration.categorize_hhi(cfg.HHI_CONCENTRATED) == "High"
    assert concentration.categorize_hhi(10000) == "High"


# ═══════════════════════════════════════════════════════════════════
#  Haversine distance (Carbon engine)
# ═══════════════════════════════════════════════════════════════════

def test_haversine_same_point():
    """Distance from a point to itself is zero."""
    assert carbon.haversine(6.45, 3.38, 6.45, 3.38) == 0.0


def test_haversine_lagos_to_london():
    """Lagos (6.45°N, 3.38°E) → London (51.51°N, -0.13°W) ≈ 5100 km."""
    d = carbon.haversine(6.45, 3.38, 51.51, -0.13)
    assert 5000 < d < 5200, f"Lagos→London distance {d:.0f} km out of range"


def test_haversine_new_york_to_tokyo():
    """NYC (40.71°N, -74.01°W) → Tokyo (35.68°N, 139.69°E) ≈ 10 800 km."""
    d = carbon.haversine(40.71, -74.01, 35.68, 139.69)
    assert 10_700 < d < 10_900, f"NYC→Tokyo distance {d:.0f} km out of range"


def test_haversine_symmetry():
    """Distance A→B == B→A."""
    d1 = carbon.haversine(6.45, 3.38, 51.51, -0.13)
    d2 = carbon.haversine(51.51, -0.13, 6.45, 3.38)
    assert abs(d1 - d2) < 1e-6


def test_haversine_equator_segment():
    """Along the equator, 1° ≈ 111.32 km. Test 10° span."""
    d = carbon.haversine(0.0, 0.0, 0.0, 10.0)
    assert 1100 < d < 1120, f"10° equator distance {d:.0f} km"


def test_haversine_poles():
    """North Pole → South Pole ≈ half circumference ≈ 20 015 km."""
    d = carbon.haversine(90, 0, -90, 0)
    assert 20_000 < d < 20_050


def test_haversine_antipodal():
    """Opposite points on earth ≈ 20 015 km."""
    d = carbon.haversine(0, 0, 0, 180)
    assert 20_000 < d < 20_050


def test_haversine_works_with_numpy_arrays():
    """Function should accept numpy arrays (used by Pandas apply)."""
    lats = np.array([6.45, 40.71])
    lons = np.array([3.38, -74.01])
    d = carbon.haversine(lats, lons, np.array([51.51, 35.68]),
                         np.array([-0.13, 139.69]))
    assert len(d) == 2
    assert all(x > 0 for x in d)


# ═══════════════════════════════════════════════════════════════════
#  Emission factor constants sanity checks
# ═══════════════════════════════════════════════════════════════════

def test_emission_factors_sea_lowest():
    """Sea freight has the lowest emission factor."""
    ef = cfg.EMISSION_FACTORS
    assert ef["Sea"] < ef["Rail"] < ef["Road"] < ef["Air"]


def test_emission_factors_all_positive():
    for mode, factor in cfg.EMISSION_FACTORS.items():
        assert factor > 0, f"{mode} emission factor must be positive"


def test_emission_factor_air_vs_sea_ratio():
    """Air/Sea ratio should be roughly 30-40× (DEFRA 2025)."""
    ratio = cfg.EMISSION_FACTORS["Air"] / cfg.EMISSION_FACTORS["Sea"]
    assert 30 < ratio < 50, f"Air/Sea ratio = {ratio:.1f}×"


# ═══════════════════════════════════════════════════════════════════
#  Risk weights sanity checks
# ═══════════════════════════════════════════════════════════════════

def test_risk_weights_sum_to_one():
    total = sum(cfg.RISK_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Risk weights sum to {total}"


def test_risk_weights_all_positive():
    for dim, w in cfg.RISK_WEIGHTS.items():
        assert w > 0, f"Risk weight {dim} must be positive"


def test_risk_weights_have_seven_dimensions():
    assert len(cfg.RISK_WEIGHTS) == 7
