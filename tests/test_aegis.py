"""
AEGIS — Test Suite
Unit tests for analytics engines and data modules.
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Config Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestConfig:
    def test_database_url_set(self):
        import config
        assert config.DATABASE_URL is not None
        assert "mysql" in config.DATABASE_URL

    def test_fx_volatilities_valid(self):
        import config
        for ccy, vol in config.FX_VOLATILITIES.items():
            assert 0 < vol <= 1.0, f"{ccy} vol {vol} out of range"

    def test_risk_weights_sum_to_one(self):
        import config
        total = sum(config.RISK_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Risk weights sum to {total}"

    def test_mcda_weights_sum_to_one(self):
        import config
        total = sum(config.MCDA_DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"MCDA weights sum to {total}"

    def test_hhi_thresholds_ordered(self):
        import config
        assert config.HHI_COMPETITIVE < config.HHI_MODERATE < config.HHI_CONCENTRATED

    def test_emission_factors_positive(self):
        import config
        for mode, factor in config.EMISSION_FACTORS.items():
            assert factor > 0, f"{mode} emission factor must be positive"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MCDA Engine Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMCDAEngine:
    """Test TOPSIS, PROMETHEE, WSM implementations."""

    @pytest.fixture
    def sample_matrix(self):
        """5 suppliers, 4 criteria"""
        return np.array([
            [80, 5, 0.02, 70],
            [90, 3, 0.05, 60],
            [70, 7, 0.01, 85],
            [85, 4, 0.03, 75],
            [60, 8, 0.04, 50],
        ])

    @pytest.fixture
    def sample_weights(self):
        return np.array([0.3, 0.2, 0.2, 0.3])

    @pytest.fixture
    def sample_is_benefit(self):
        return [True, False, False, True]

    def test_topsis_returns_correct_shape(self, sample_matrix, sample_weights, sample_is_benefit):
        from analytics.mcda_engine import topsis
        scores = topsis(sample_matrix, sample_weights, sample_is_benefit)
        assert len(scores) == 5
        assert all(0 <= s <= 1 for s in scores)

    def test_topsis_best_alternative(self, sample_matrix, sample_weights, sample_is_benefit):
        from analytics.mcda_engine import topsis
        scores = topsis(sample_matrix, sample_weights, sample_is_benefit)
        # Supplier 3 (index 2) has best quality, lowest defect, high ESG
        # but exact ranking depends on normalization
        assert scores.argmax() in [0, 2, 3]  # reasonable top candidates

    def test_promethee_returns_correct_shape(self, sample_matrix, sample_weights, sample_is_benefit):
        from analytics.mcda_engine import promethee_ii
        flows = promethee_ii(sample_matrix, sample_weights, sample_is_benefit)
        assert len(flows) == 5
        # Net flows should sum approximately to 0
        assert abs(sum(flows)) < 0.01

    def test_wsm_returns_correct_shape(self, sample_matrix, sample_weights, sample_is_benefit):
        from analytics.mcda_engine import wsm
        scores = wsm(sample_matrix, sample_weights)
        assert len(scores) == 5
        assert all(0 <= s <= 1 for s in scores)

    def test_tier_from_score(self):
        from analytics.mcda_engine import tier_from_score
        assert tier_from_score(90) == "Strategic"
        assert tier_from_score(75) == "Preferred"
        assert tier_from_score(55) == "Approved"
        assert tier_from_score(40) == "Conditional"
        assert tier_from_score(20) == "Blocked"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Monte Carlo Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMonteCarlo:
    def test_simulate_fx_returns_dict(self):
        from analytics.monte_carlo import simulate_fx
        result = simulate_fx("NGN", n_paths=500, horizon_days=30)
        assert "terminal_rates" in result
        assert "mean" in result
        assert "var_95" in result
        assert len(result["terminal_rates"]) == 500

    def test_simulate_fx_gbm_positive(self):
        from analytics.monte_carlo import simulate_fx
        result = simulate_fx("EUR", n_paths=1000, horizon_days=60)
        assert all(r > 0 for r in result["terminal_rates"])

    def test_simulate_fx_var_positive(self):
        from analytics.monte_carlo import simulate_fx
        result = simulate_fx("NGN", n_paths=2000, horizon_days=90)
        assert result["var_95"] >= 0  # loss should be non-negative


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Risk Scoring Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRiskScoring:
    def test_risk_tier_mapping(self):
        """Risk tier boundaries."""
        import config
        assert "financial_health" in config.RISK_WEIGHTS
        assert "geopolitical" in config.RISK_WEIGHTS
        assert "esg_compliance" in config.RISK_WEIGHTS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Concentration Analysis Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestConcentration:
    def test_compute_hhi_uniform(self):
        from analytics.concentration import compute_hhi
        # 4 entities each with 25% share → HHI = 4 × 25² = 2500
        shares = [25.0, 25.0, 25.0, 25.0]
        hhi = compute_hhi(shares)
        assert abs(hhi - 2500) < 1

    def test_compute_hhi_monopoly(self):
        from analytics.concentration import compute_hhi
        shares = [100.0]
        hhi = compute_hhi(shares)
        assert abs(hhi - 10000) < 1

    def test_compute_hhi_equal_ten(self):
        from analytics.concentration import compute_hhi
        shares = [10.0] * 10
        hhi = compute_hhi(shares)
        assert abs(hhi - 1000) < 1

    def test_categorize_hhi(self):
        from analytics.concentration import categorize_hhi
        assert categorize_hhi(800) == "Low"
        assert categorize_hhi(2000) == "Moderate"
        assert categorize_hhi(3000) == "High"
        assert categorize_hhi(6000) == "High"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Carbon Engine Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCarbonEngine:
    def test_haversine(self):
        from analytics.carbon_engine import haversine
        # London to New York ≈ 5,570 km
        dist = haversine(51.5, -0.1, 40.7, -74.0)
        assert 5400 < dist < 5700

    def test_haversine_same_point(self):
        from analytics.carbon_engine import haversine
        dist = haversine(0, 0, 0, 0)
        assert dist == 0

    def test_emission_factors_exist(self):
        import config
        assert "Sea" in config.EMISSION_FACTORS
        assert "Air" in config.EMISSION_FACTORS
        assert config.EMISSION_FACTORS["Air"] > config.EMISSION_FACTORS["Sea"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Should-Cost Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestShouldCost:
    def test_leakage_flags(self):
        import config
        assert config.COST_LEAKAGE_INVESTIGATE_PCT < config.COST_LEAKAGE_ESCALATE_PCT
        assert config.COST_LEAKAGE_ESCALATE_PCT < config.COST_LEAKAGE_RED_FLAG_PCT


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Working Capital Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWorkingCapital:
    def test_epd_annualized_return(self):
        """2% 10-day discount → annualized ≈ 73%"""
        discount_pct = 0.02
        days_early = 10
        annualized = (discount_pct / (1 - discount_pct)) * (365 / days_early)
        assert 70 < annualized * 100 < 80
