"""
Unit tests for Monte Carlo simulation engine pure-computation functions.
No database required — uses hardcoded inputs and seeded RNG for determinism.
"""

import math
import numpy as np
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MC_PATH = ROOT / "analytics" / "monte_carlo.py"

spec = importlib.util.spec_from_file_location("monte_carlo", MC_PATH)
mc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mc)


# ═══ simulate_fx — GBM-based FX simulation ═══════════════════════════

def test_simulate_fx_returns_expected_keys():
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=100, horizon_days=30,
                            current_rate=1.10, annual_vol=0.08)
    expected_keys = {
        "currency", "current_rate", "horizon_days", "n_paths",
        "mean", "median", "std_dev", "p5", "p25", "p75", "p95",
        "var_95", "cvar_95", "terminal_rates",
    }
    assert expected_keys.issubset(set(result.keys()))


def test_simulate_fx_n_paths_matches():
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=200, horizon_days=10,
                            current_rate=1.10, annual_vol=0.08)
    assert result["n_paths"] == 200
    assert len(result["terminal_rates"]) == 200


def test_simulate_fx_mean_near_current_rate():
    """With zero drift (risk-neutral), mean terminal rate ≈ current rate."""
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=5000, horizon_days=30,
                            current_rate=1.10, annual_vol=0.08)
    # Allow ±3% of current rate for sampling variance
    assert abs(result["mean"] - 1.10) < 0.033, (
        f"Mean {result['mean']:.4f} too far from current rate 1.10"
    )


def test_simulate_fx_std_dev_positive():
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=500, horizon_days=30,
                            current_rate=1.10, annual_vol=0.08)
    assert result["std_dev"] > 0


def test_simulate_fx_var95_direction():
    """VaR-95 = p95 - current_rate; for symmetric-ish distribution, p95 > current_rate."""
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=5000, horizon_days=60,
                            current_rate=1.10, annual_vol=0.12)
    # p95 should be above current rate (upside percentile) for risk-neutral GBM
    assert result["p95"] > result["current_rate"]


def test_simulate_fx_percentile_ordering():
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=2000, horizon_days=30,
                            current_rate=1.10, annual_vol=0.10)
    assert result["p5"] <= result["p25"]
    assert result["p25"] <= result["median"]
    assert result["median"] <= result["p75"]
    assert result["p75"] <= result["p95"]


def test_simulate_fx_deterministic_with_seed():
    """Same seed → same results."""
    np.random.seed(123)
    r1 = mc.simulate_fx("GBP", n_paths=100, horizon_days=20,
                         current_rate=0.79, annual_vol=0.09)
    np.random.seed(123)
    r2 = mc.simulate_fx("GBP", n_paths=100, horizon_days=20,
                         current_rate=0.79, annual_vol=0.09)
    assert abs(r1["mean"] - r2["mean"]) < 1e-12


def test_simulate_fx_higher_vol_wider_spread():
    """Higher volatility should produce wider terminal distribution."""
    np.random.seed(42)
    low_vol = mc.simulate_fx("EUR", n_paths=3000, horizon_days=60,
                              current_rate=1.10, annual_vol=0.05)
    np.random.seed(42)
    high_vol = mc.simulate_fx("EUR", n_paths=3000, horizon_days=60,
                               current_rate=1.10, annual_vol=0.30)
    assert high_vol["std_dev"] > low_vol["std_dev"]


def test_simulate_fx_zero_vol_converges():
    """With zero volatility, terminal rates should tightly cluster around current rate."""
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=100, horizon_days=30,
                            current_rate=1.10, annual_vol=0.0)
    # Allow tiny floating-point drift from 30 multiplicative steps
    assert abs(result["mean"] - 1.10) < 0.01
    assert result["std_dev"] < 0.01


def test_simulate_fx_single_path():
    np.random.seed(42)
    result = mc.simulate_fx("EUR", n_paths=1, horizon_days=10,
                            current_rate=1.10, annual_vol=0.10)
    assert result["n_paths"] == 1
    assert len(result["terminal_rates"]) == 1
    assert result["terminal_rates"][0] > 0  # FX rate must be positive
