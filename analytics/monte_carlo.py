"""
AEGIS — Monte Carlo Simulation Engine
FX risk, lead-time variability, disruption impact, cost scenarios.
Uses Geometric Brownian Motion for FX, log-normal for lead times.
"""

import math
import datetime as dt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logging_config import get_logger

log = get_logger("montecarlo")

ENGINE = create_engine(config.DATABASE_URL, echo=False)


# ═════════════════════════════════════════════════════════════════════
#  1. FX Monte Carlo — GBM simulation
# ═════════════════════════════════════════════════════════════════════
def simulate_fx(currency: str,
                n_paths: int = None,
                horizon_days: int = None,
                current_rate: float = None,
                annual_vol: float = None) -> dict:
    """
    Simulates future FX paths using Geometric Brownian Motion.
    Returns distribution statistics and VaR/CVaR.
    """
    n_paths = n_paths or config.MC_DEFAULT_PATHS
    horizon_days = horizon_days or config.MC_DEFAULT_HORIZON_DAYS
    current_rate = current_rate or config.FX_ANCHOR_RATES.get(currency, 1.0)
    annual_vol = annual_vol or config.FX_VOLATILITIES.get(currency, 0.10)

    n_paths = min(n_paths, config.MC_MAX_PATHS)
    horizon_days = min(horizon_days, config.MC_MAX_HORIZON_DAYS)

    daily_vol = annual_vol / math.sqrt(252)
    dt_step = 1 / 252  # Trading day fraction

    # GBM: S(t+1) = S(t) * exp((mu - 0.5σ²)dt + σ√dt * Z)
    # Assume drift = 0 (risk-neutral)
    terminal_rates = np.zeros(n_paths)
    for i in range(n_paths):
        rate = current_rate
        for _ in range(horizon_days):
            z = np.random.normal()
            rate *= math.exp(-0.5 * daily_vol**2 * dt_step + daily_vol * math.sqrt(dt_step) * z)
        terminal_rates[i] = rate

    # Stats
    stats = {
        "currency": currency,
        "current_rate": current_rate,
        "horizon_days": horizon_days,
        "n_paths": n_paths,
        "mean": float(np.mean(terminal_rates)),
        "median": float(np.median(terminal_rates)),
        "std_dev": float(np.std(terminal_rates)),
        "p5": float(np.percentile(terminal_rates, 5)),
        "p25": float(np.percentile(terminal_rates, 25)),
        "p75": float(np.percentile(terminal_rates, 75)),
        "p95": float(np.percentile(terminal_rates, 95)),
        "var_95": float(np.percentile(terminal_rates, 95) - current_rate),
        "cvar_95": float(np.mean(terminal_rates[terminal_rates >= np.percentile(terminal_rates, 95)]) - current_rate),
        "terminal_rates": terminal_rates,
    }
    return stats


# ═════════════════════════════════════════════════════════════════════
#  2. Lead-Time Monte Carlo — Log-normal
# ═════════════════════════════════════════════════════════════════════
def simulate_lead_time(supplier_id: int = None,
                       n_sims: int = None) -> dict:
    """
    Simulates lead-time distribution from historical data.
    Uses log-normal fit on actual delivery times.
    """
    n_sims = n_sims or config.MC_DEFAULT_PATHS

    with ENGINE.connect() as conn:
        if supplier_id:
            rows = conn.execute(text("""
                SELECT DATEDIFF(COALESCE(sh.actual_arrival, sh.eta_date), po.order_date) AS lt
                FROM shipments sh
                JOIN purchase_orders po ON sh.po_id = po.po_id
                WHERE po.supplier_id = :sid AND sh.actual_arrival IS NOT NULL
            """), {"sid": supplier_id}).fetchall()
        else:
            rows = conn.execute(text("""
                SELECT DATEDIFF(COALESCE(sh.actual_arrival, sh.eta_date), po.order_date) AS lt
                FROM shipments sh
                JOIN purchase_orders po ON sh.po_id = po.po_id
                WHERE sh.actual_arrival IS NOT NULL
            """)).fetchall()

    lead_times = np.array([max(1, r[0]) for r in rows if r[0] and r[0] > 0])

    if len(lead_times) < 5:
        # Fallback: use generic distribution
        lead_times = np.array([30, 45, 60, 35, 50, 40, 55, 70, 25, 65])

    # Fit log-normal
    log_lt = np.log(lead_times)
    mu = np.mean(log_lt)
    sigma = np.std(log_lt)

    simulated = np.random.lognormal(mean=mu, sigma=sigma, size=n_sims)

    return {
        "supplier_id": supplier_id,
        "n_historical": len(lead_times),
        "hist_mean": float(np.mean(lead_times)),
        "hist_std": float(np.std(lead_times)),
        "n_simulations": n_sims,
        "mean": float(np.mean(simulated)),
        "median": float(np.median(simulated)),
        "std_dev": float(np.std(simulated)),
        "p5": float(np.percentile(simulated, 5)),
        "p25": float(np.percentile(simulated, 25)),
        "p75": float(np.percentile(simulated, 75)),
        "p95": float(np.percentile(simulated, 95)),
        "simulated": simulated,
    }


# ═════════════════════════════════════════════════════════════════════
#  3. Disruption Impact — scenario-based
# ═════════════════════════════════════════════════════════════════════
def simulate_disruption(scenario: str = "port_closure",
                        affected_entity: str = "Lagos",
                        duration_days: int = 30,
                        n_sims: int = None) -> dict:
    """
    Models supply chain disruption impact through Monte Carlo.
    Scenarios: port_closure, supplier_failure, sanctions, natural_disaster
    """
    n_sims = n_sims or config.MC_DEFAULT_PATHS

    # Impact multipliers (on cost and lead time)
    impact_params = {
        "port_closure": {"cost_mult_mean": 1.25, "cost_mult_std": 0.15,
                         "lt_add_mean": 21, "lt_add_std": 10},
        "supplier_failure": {"cost_mult_mean": 1.40, "cost_mult_std": 0.20,
                             "lt_add_mean": 45, "lt_add_std": 20},
        "sanctions": {"cost_mult_mean": 1.60, "cost_mult_std": 0.30,
                      "lt_add_mean": 60, "lt_add_std": 25},
        "natural_disaster": {"cost_mult_mean": 1.35, "cost_mult_std": 0.25,
                             "lt_add_mean": 35, "lt_add_std": 15},
    }

    params = impact_params.get(scenario, impact_params["port_closure"])

    # Get baseline spend
    with ENGINE.connect() as conn:
        baseline = conn.execute(text("""
            SELECT COALESCE(SUM(li.line_total), 1000000)
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            WHERE YEAR(po.order_date) = 2024
        """)).scalar()

    baseline = float(baseline)

    cost_impacts = np.random.normal(
        params["cost_mult_mean"], params["cost_mult_std"], n_sims)
    cost_impacts = np.maximum(cost_impacts, 1.0)  # At least 1x

    lt_additions = np.random.normal(
        params["lt_add_mean"], params["lt_add_std"], n_sims)
    lt_additions = np.maximum(lt_additions, 0)

    total_cost_impact = baseline * (cost_impacts - 1)

    return {
        "scenario": scenario,
        "affected_entity": affected_entity,
        "duration_days": duration_days,
        "baseline_spend": baseline,
        "cost_impact_mean": float(np.mean(total_cost_impact)),
        "cost_impact_p95": float(np.percentile(total_cost_impact, 95)),
        "lt_addition_mean": float(np.mean(lt_additions)),
        "lt_addition_p95": float(np.percentile(lt_additions, 95)),
        "var_95": float(np.percentile(total_cost_impact, 95)),
        "cvar_95": float(np.mean(total_cost_impact[
            total_cost_impact >= np.percentile(total_cost_impact, 95)])),
    }


# ═════════════════════════════════════════════════════════════════════
#  4. Cost Scenario — total procurement cost under uncertainty
# ═════════════════════════════════════════════════════════════════════
def simulate_cost_scenario(n_sims: int = None,
                           fx_currencies: list = None) -> dict:
    """
    Combined Monte Carlo: FX + commodity price + lead time variability
    on total procurement cost.
    """
    n_sims = n_sims or config.MC_DEFAULT_PATHS
    fx_currencies = fx_currencies or ["NGN", "EUR", "GBP", "CNY"]

    with ENGINE.connect() as conn:
        baseline = float(conn.execute(text("""
            SELECT COALESCE(SUM(li.line_total), 1000000)
            FROM po_line_items li
            JOIN purchase_orders po ON li.po_id = po.po_id
            WHERE YEAR(po.order_date) = 2024
        """)).scalar())

    # Simulate combined FX impact
    fx_impact = np.ones(n_sims)
    for ccy in fx_currencies:
        vol = config.FX_VOLATILITIES.get(ccy, 0.10)
        daily_vol = vol / math.sqrt(252)
        horizon = 90
        for i in range(n_sims):
            rate_change = math.exp(
                (-0.5 * daily_vol**2 * horizon/252) +
                daily_vol * math.sqrt(horizon/252) * np.random.normal()
            )
            fx_impact[i] *= rate_change

    # Commodity price shock (±20%)
    commodity_shock = np.random.normal(1.0, 0.10, n_sims)
    commodity_shock = np.maximum(commodity_shock, 0.7)

    # Combine
    total_cost = baseline * fx_impact * commodity_shock
    savings_at_risk = total_cost - baseline

    return {
        "baseline_spend": baseline,
        "n_simulations": n_sims,
        "mean_cost": float(np.mean(total_cost)),
        "median_cost": float(np.median(total_cost)),
        "p5_cost": float(np.percentile(total_cost, 5)),
        "p95_cost": float(np.percentile(total_cost, 95)),
        "var_95": float(np.percentile(savings_at_risk, 95)),
        "cvar_95": float(np.mean(savings_at_risk[
            savings_at_risk >= np.percentile(savings_at_risk, 95)])),
        "cost_distribution": total_cost,
    }


# ═════════════════════════════════════════════════════════════════════
#  5. Persist simulation results
# ═════════════════════════════════════════════════════════════════════
def save_simulation(scenario_type: str, scenario_label: str,
                    stats: dict, n_sims: int = None):
    """Save simulation results to simulation_runs table."""
    import json

    with ENGINE.begin() as conn:
        conn.execute(text("""
            INSERT INTO simulation_runs
                (scenario_type, scenario_label, n_simulations,
                 mean_value, median_value, std_dev,
                 p5_value, p25_value, p75_value, p95_value,
                 var_95, cvar_95, input_parameters)
            VALUES
                (:scenario_type, :scenario_label, :n_simulations,
                 :mean_value, :median_value, :std_dev,
                 :p5_value, :p25_value, :p75_value, :p95_value,
                 :var_95, :cvar_95, :input_parameters)
        """), {
            "scenario_type": scenario_type,
            "scenario_label": scenario_label,
            "n_simulations": n_sims or config.MC_DEFAULT_PATHS,
            "mean_value": stats.get("mean") or stats.get("mean_cost"),
            "median_value": stats.get("median") or stats.get("median_cost"),
            "std_dev": stats.get("std_dev", 0),
            "p5_value": stats.get("p5") or stats.get("p5_cost"),
            "p25_value": stats.get("p25"),
            "p75_value": stats.get("p75"),
            "p95_value": stats.get("p95") or stats.get("p95_cost"),
            "var_95": stats.get("var_95", 0),
            "cvar_95": stats.get("cvar_95", 0),
            "input_parameters": json.dumps({
                k: v for k, v in stats.items()
                if k not in ("terminal_rates", "simulated", "cost_distribution")
            }),
        })

    log.info(f"Simulation saved: {scenario_type} -- {scenario_label}")


if __name__ == "__main__":
    log.info("=== FX Simulation: NGN ===")
    fx = simulate_fx("NGN", n_paths=5000, horizon_days=90)
    log.info(f"  Current: {fx['current_rate']}")
    log.info(f"  Mean: {fx['mean']:.2f}, P5: {fx['p5']:.2f}, P95: {fx['p95']:.2f}")
    log.info(f"  VaR(95): {fx['var_95']:.2f}, CVaR(95): {fx['cvar_95']:.2f}")
    save_simulation("FX", "NGN 90-day", fx, 5000)

    log.info("=== Lead Time Simulation ===")
    lt = simulate_lead_time()
    log.info(f"  Mean: {lt['mean']:.1f} days, P95: {lt['p95']:.1f} days")
    save_simulation("LeadTime", "All Suppliers 90-day", lt)

    log.info("=== Disruption: Port Closure ===")
    dis = simulate_disruption("port_closure", "Lagos", 30)
    log.info(f"  Cost Impact Mean: ${dis['cost_impact_mean']:,.0f}")
    log.info(f"  Cost Impact P95: ${dis['cost_impact_p95']:,.0f}")
    save_simulation("Disruption", "Lagos Port Closure 30d", dis)
