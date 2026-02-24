# AEGIS API Reference

## Pipeline CLI

```bash
python run_aegis_pipeline.py [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--skip-schema` | Skip schema deployment (step 1) |
| `--skip-seed` | Skip sample data generation (step 3) |
| `--skip-warehouse` | Skip warehouse ETL (step 4) |
| `--skip-analytics` | Skip analytics engines (step 5) |
| `--verify-only` | Only run verification (step 6) |
| `--external DIR` | Import CSVs from DIR instead of generating sample data |

## Analytics Engine APIs

### MCDA Engine (`analytics/mcda_engine.py`)

```python
topsis(matrix: np.ndarray, weights: np.ndarray, is_benefit: list[bool]) -> np.ndarray
promethee_ii(matrix: np.ndarray, weights: np.ndarray, is_benefit: list[bool]) -> np.ndarray
wsm(matrix: np.ndarray, weights: np.ndarray) -> np.ndarray
run_mcda() -> None  # Persists supplier_scorecards to DB
tier_from_score(score: float) -> str  # Strategic/Preferred/Approved/Conditional/Blocked
```

### Risk Scoring (`analytics/risk_scoring.py`)

```python
compute_risk_scores() -> pd.DataFrame  # Returns DataFrame with composite risk scores
persist_risk_assessments(scores: pd.DataFrame) -> None
```

### Monte Carlo (`analytics/monte_carlo.py`)

```python
simulate_fx(currency: str, n_paths: int = 10000, horizon_days: int = 90) -> dict
# Returns: {terminal_rates, mean, std, var_95, cvar_95, p5, p50, p95, paths}

simulate_lead_time(supplier_id: int, n_sims: int = 5000) -> dict
simulate_disruption(supplier_id: int, n_sims: int = 5000) -> dict
simulate_cost(material_id: int, n_sims: int = 5000) -> dict
```

### Concentration (`analytics/concentration.py`)

```python
compute_hhi(shares: list[float]) -> float  # Herfindahl-Hirschman Index
categorize_hhi(hhi: float) -> str  # Low/Moderate/High
run_full_concentration_analysis() -> list[dict]
persist_concentration(results: list[dict]) -> None
```

### Carbon Engine (`analytics/carbon_engine.py`)

```python
haversine(lat1, lon1, lat2, lon2) -> float  # km
calculate_emissions() -> None  # Computes & persists carbon_estimates
```

### Should-Cost (`analytics/should_cost.py`)

```python
build_should_cost(material_id: int = None, year: int = 2024) -> pd.DataFrame
# Returns: material_name, should_cost_usd, quoted_usd, cost_variance_pct, leakage_flag

get_leakage_summary(year: int = 2024) -> dict
# Returns: {total_leakage_usd, leakage_pct, items_flagged, total_items}
```

### Working Capital (`analytics/working_capital.py`)

```python
analyze_working_capital() -> dict
# Returns: {total_spend, total_overdue, overdue_pct, avg_dpo, dpo_trend, aging_by_supplier, epd_analysis}

optimize_payment_timing() -> pd.DataFrame
# Returns: supplier_name, amount_usd, savings_usd, annualized_return
```

### Scenario Planner (`analytics/scenario_planner.py`)

```python
scenario_supplier_switch(from_id: int = None, to_id: int = None) -> dict
# Returns: from_supplier, to_supplier, current_spend, estimated_new_spend, cost_impact_pct, ...

scenario_currency_hedge(currency: str = "NGN", hedge_pct: float = 0.6) -> dict
# Returns: exposure_usd, hedge_pct, unhedged_worst_case_p95, hedged_worst_case_p95, savings_at_p95

scenario_nearshoring(target_region: str = "LATAM", realloc_pct: float = 0.3) -> dict
# Returns: reallocation_amount, cost_premium_impact, freight_savings, net_cost_impact, ...
```

## Utility APIs

### Logging (`utils/logging_config.py`)
```python
get_logger(name: str) -> logging.Logger
AuditLogger(changed_by: str).log(table, record_id, action, old_values, new_values)
DataQualityLogger().log(check_name, check_type, table, column, checked, failed, severity, details)
```

### Authentication (`utils/auth.py`)
```python
login_gate() -> bool  # Shows login form, returns True when authenticated
```

### Data Freshness (`utils/freshness.py`)
```python
record_start() -> int  # Returns run_id
record_finish(run_id, status, duration, steps)
get_last_run() -> dict | None
freshness_badge() -> str  # "🟢 Fresh (5m ago)" etc.
```

### Export (`utils/export.py`)
```python
to_excel_bytes(dataframes: dict[str, pd.DataFrame]) -> bytes
to_csv_bytes(df: pd.DataFrame) -> bytes
generate_executive_summary(engine) -> dict[str, pd.DataFrame]
```

## External Data Loader

```python
from data_ingestion.external_data_loader import ExternalDataLoader

loader = ExternalDataLoader("/path/to/csv/dir")
loader.load_all_files()  # Validates & loads CSVs
loader.import_data()     # Inserts into database
```

### Required CSV files
| File | Required Columns |
|------|-----------------|
| `suppliers.csv` | supplier_name, country, currency_code, lead_time_days |
| `purchase_orders.csv` | po_number, supplier_name, order_date, currency_code, total_amount |
| `po_line_items.csv` | po_number, material_name, quantity, unit_price, line_total |
| `materials.csv` | material_name, category, unit_of_measure, standard_cost_usd |

### Optional CSV files
- `shipments.csv`, `invoices.csv`, `esg_assessments.csv`

## Live FX Fetcher

```python
from data_ingestion.live_data_fetcher import refresh_live_data

result = refresh_live_data()
# Returns: {fx_updated: int, fx_rates: dict, timestamp: str}
```

API Priority: open.er-api.com → exchangerate-api.com → frankfurter.dev

## Configuration (`config.py`)

| Constant | Type | Description |
|----------|------|-------------|
| `DATABASE_URL` | str | MySQL connection string |
| `FX_VOLATILITIES` | dict | Annual σ per currency (9 currencies) |
| `FX_ANCHOR_RATES` | dict | Base rates per 1 USD |
| `RISK_WEIGHTS` | dict | 7-dimension weights (sum=1.0) |
| `MCDA_DEFAULT_WEIGHTS` | dict | 7-dimension supplier weights (sum=1.0) |
| `EMISSION_FACTORS` | dict | kg CO₂/tonne-km by transport mode |
| `COST_LEAKAGE_*_PCT` | float | Thresholds: 5%, 15%, 25% |
| `HHI_*` | int | Competitive (1500), Moderate (2500), Concentrated (5000) |
| `MC_DEFAULT_PATHS` | int | Default Monte Carlo paths (10000) |
| `ENABLE_LIVE_FX` | bool | Toggle live FX API fetch |
| `DEMO_MODE` | bool | Use synthetic data |
