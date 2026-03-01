"""
Unit tests for MCDA engine pure-computation functions.
No database required — uses hardcoded decision matrices with known-correct results.
"""

import numpy as np
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCDA_PATH = ROOT / "analytics" / "mcda_engine.py"

spec = importlib.util.spec_from_file_location("mcda_engine", MCDA_PATH)
mcda = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mcda)


# ═══ Known decision matrix: 4 suppliers × 3 criteria ═══
# All benefit-type criteria (higher = better).
DM = np.array([
    [80, 90, 70],   # Supplier A
    [90, 60, 85],   # Supplier B
    [70, 70, 90],   # Supplier C
    [85, 80, 75],   # Supplier D
])
WEIGHTS = np.array([0.4, 0.35, 0.25])


# ─── TOPSIS ──────────────────────────────────────────────────────────

def test_topsis_returns_correct_shape():
    scores = mcda.topsis(DM, WEIGHTS)
    assert scores.shape == (4,)


def test_topsis_scores_are_bounded_0_to_1():
    scores = mcda.topsis(DM, WEIGHTS)
    assert np.all(scores >= 0.0)
    assert np.all(scores <= 1.0)


def test_topsis_best_supplier_is_first_or_fourth():
    """Supplier A (80,90,70) or D (85,80,75) should lead given balanced weights."""
    scores = mcda.topsis(DM, WEIGHTS)
    best_idx = int(np.argmax(scores))
    assert best_idx in (0, 3), f"Expected supplier A(0) or D(3) to rank first, got {best_idx}"


def test_topsis_dominant_alternative_wins():
    """If one alternative dominates all others on every criterion, it must score highest."""
    dm = np.array([
        [100, 100, 100],
        [50, 50, 50],
        [70, 70, 70],
    ])
    w = np.array([0.33, 0.34, 0.33])
    scores = mcda.topsis(dm, w)
    assert np.argmax(scores) == 0


def test_topsis_equal_alternatives_get_equal_scores():
    """Identical rows should produce identical closeness scores."""
    dm = np.array([
        [80, 80, 80],
        [80, 80, 80],
        [60, 60, 60],
    ])
    w = np.array([0.33, 0.34, 0.33])
    scores = mcda.topsis(dm, w)
    assert abs(scores[0] - scores[1]) < 1e-9


def test_topsis_with_cost_criteria():
    """First criterion as cost (lower is better)."""
    dm = np.array([
        [20, 90],
        [90, 90],
        [50, 60],
    ])
    w = np.array([0.5, 0.5])
    scores = mcda.topsis(dm, w, benefit_criteria=[False, True])
    # Supplier A has low cost + high benefit → should win
    assert np.argmax(scores) == 0


# ─── PROMETHEE II ────────────────────────────────────────────────────

def test_promethee_returns_correct_shape():
    flows = mcda.promethee_ii(DM, WEIGHTS)
    assert flows.shape == (4,)


def test_promethee_net_flows_sum_to_zero():
    """Net flows of all alternatives should sum to approximately zero."""
    flows = mcda.promethee_ii(DM, WEIGHTS)
    assert abs(flows.sum()) < 1e-6, f"Net flows sum to {flows.sum()}, expected ~0"


def test_promethee_dominant_alternative_has_highest_flow():
    dm = np.array([
        [100, 100, 100],
        [50, 50, 50],
        [70, 70, 70],
    ])
    w = np.array([0.33, 0.34, 0.33])
    flows = mcda.promethee_ii(dm, w)
    assert np.argmax(flows) == 0


# ─── WSM ─────────────────────────────────────────────────────────────

def test_wsm_returns_correct_shape():
    scores = mcda.wsm(DM, WEIGHTS)
    assert scores.shape == (4,)


def test_wsm_scores_are_bounded_0_to_1():
    scores = mcda.wsm(DM, WEIGHTS)
    assert np.all(scores >= 0.0 - 1e-9)
    assert np.all(scores <= 1.0 + 1e-9)


def test_wsm_dominant_alternative_scores_highest():
    dm = np.array([
        [100, 100, 100],
        [50, 50, 50],
        [70, 70, 70],
    ])
    w = np.array([0.33, 0.34, 0.33])
    scores = mcda.wsm(dm, w)
    assert np.argmax(scores) == 0


def test_wsm_manual_computation():
    """Verify WSM against hand-computed result."""
    dm = np.array([
        [100, 50],
        [50, 100],
    ])
    w = np.array([0.6, 0.4])
    scores = mcda.wsm(dm, w)
    # After min-max normalization: row 0 = [1, 0], row 1 = [0, 1]
    # WSM: row 0 = 1*0.6 + 0*0.4 = 0.6; row 1 = 0*0.6 + 1*0.4 = 0.4
    assert abs(scores[0] - 0.6) < 1e-9
    assert abs(scores[1] - 0.4) < 1e-9


# ─── Tier assignment ─────────────────────────────────────────────────

def test_tier_from_score_boundaries():
    assert mcda.tier_from_score(95) == "Strategic"
    assert mcda.tier_from_score(80) == "Strategic"
    assert mcda.tier_from_score(79) == "Preferred"
    assert mcda.tier_from_score(65) == "Preferred"
    assert mcda.tier_from_score(64) == "Approved"
    assert mcda.tier_from_score(50) == "Approved"
    assert mcda.tier_from_score(49) == "Conditional"
    assert mcda.tier_from_score(35) == "Conditional"
    assert mcda.tier_from_score(34) == "Blocked"
    assert mcda.tier_from_score(0) == "Blocked"
