# AEGIS Project Walkthrough

A step-by-step tour of the AEGIS (Adaptive Engine for Global Intelligent Sourcing) codebase, covering the database schema, data pipeline, analytics engines, dashboard pages, testing, and deployment.

---

## Table of Contents

1. [Repository Layout](#1-repository-layout)
2. [Configuration](#2-configuration)
3. [Database Schema](#3-database-schema)
4. [Data Ingestion](#4-data-ingestion)
5. [Warehouse ETL](#5-warehouse-etl)
6. [Analytics Engines](#6-analytics-engines)
7. [Streamlit Dashboard](#7-streamlit-dashboard)
8. [Utilities](#8-utilities)
9. [Testing](#9-testing)
10. [CI/CD Pipeline](#10-cicd-pipeline)
11. [Docker Deployment](#11-docker-deployment)
12. [Power BI Layer](#12-power-bi-layer)
13. [Pipeline Execution Walkthrough](#13-pipeline-execution-walkthrough)
14. [Data Flow Diagram](#14-data-flow-diagram)
15. [Adding Your Own Data](#15-adding-your-own-data)

---

## 1. Repository Layout

```
aegis-procurement/
├── config.py                          # Central configuration (DB, FX, weights, thresholds)
├── run_aegis_pipeline.py              # 6-step master orchestrator
├── streamlit_app.py                   # Dashboard entry point
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Black, Ruff, pytest configuration
├── Dockerfile                         # Python 3.11-slim container image
├── docker-compose.yml                 # MySQL 8.0 + Streamlit app stack
├── .env.example                       # Environment variable template
│
├── database/                          # 10 SQL files (40 tables across 8 layers)
│   ├── 00_MASTER_DEPLOY.sql           # Bootstrap script (drops and recreates everything)
│   ├── 01_create_reference_tables.sql # 9 lookup tables
│   ├── 02_create_master_tables.sql    # 5 master data tables
│   ├── 03_create_transaction_tables.sql # 7 transaction tables
│   ├── 04_create_market_tables.sql    # 3 market data tables
│   ├── 05_create_esg_tables.sql       # 4 ESG and compliance tables
│   ├── 06_create_warehouse.sql        # 4 dimensions + 2 fact tables
│   ├── 07_create_analytics_tables.sql # 4 analytics output tables
│   ├── 08_create_audit_tables.sql     # 2 audit/DQ tables
│   └── 09_seed_reference_data.sql     # Reference data inserts
│
├── data_ingestion/
│   ├── generate_seed_data.py          # 14-step realistic data generator
│   ├── populate_warehouse.py          # Star-schema ETL with SCD Type 2
│   ├── external_data_loader.py        # Import company CSV data
│   └── live_data_fetcher.py           # Live FX rates (3-tier API failover)
│
├── analytics/                         # 8 engines
│   ├── mcda_engine.py                 # TOPSIS, PROMETHEE-II, WSM
│   ├── risk_scoring.py                # 7-dimension composite risk
│   ├── monte_carlo.py                 # FX (GBM), lead-time, disruption, cost
│   ├── concentration.py               # HHI across 5 dimensions
│   ├── carbon_engine.py               # GHG Protocol Scope 3, GLEC Framework
│   ├── should_cost.py                 # Bottom-up cost model, leakage detection
│   ├── working_capital.py             # DPO analysis, EPD optimization
│   └── scenario_planner.py            # Supplier switch, hedge, nearshoring
│
├── pages/                             # 12 Streamlit dashboard pages
│   ├── 01_Executive_Dashboard.py
│   ├── 02_Supplier_Scorecards.py
│   ├── 03_Risk_Radar.py
│   ├── 04_Monte_Carlo_Lab.py
│   ├── 05_Concentration_Analysis.py
│   ├── 06_Carbon_Dashboard.py
│   ├── 07_Should_Cost.py
│   ├── 08_Working_Capital.py
│   ├── 09_ESG_Compliance.py
│   ├── 10_Scenario_Planner.py
│   ├── 11_Data_Explorer.py
│   └── 12_Settings.py
│
├── utils/
│   ├── auth.py                        # SHA-256 login gate
│   ├── export.py                      # Excel/CSV export helpers
│   ├── freshness.py                   # Pipeline run tracking
│   └── logging_config.py              # File + console logging, audit, DQ
│
├── powerbi/                           # Power BI assets
│   ├── AEGIS_Dashboard_BUILD.md       # 10-page build guide
│   ├── AEGIS_Theme.json               # Custom color theme
│   ├── DAX_Measures.md                # 25+ DAX measure definitions
│   └── PowerQuery_Connections.pq      # 14 Power Query M scripts
│
├── external_data_samples/             # 7 CSV templates for company data
├── tests/                             # 49 pytest tests (2 files, 16 classes)
├── docs/                              # DATA_MODEL.md, SETUP_GUIDE.md, ARCHITECTURE.md
├── logs/                              # Runtime log output
└── .github/workflows/ci.yml          # 3-job CI (test, lint, docker)
```

---

## 2. Configuration

All tuneable parameters live in `config.py`. Nothing is hardcoded in the analytics or ingestion modules; they all import from this single file.

### Database Connection

```python
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "...")
DB_NAME     = os.getenv("DB_NAME", "aegis_procurement")
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

Every value can be overridden with an environment variable, so the same code runs locally and inside Docker without changes.

### FX Parameters

Nine currencies are tracked, each with a calibrated annual volatility and an anchor rate (the starting point for Monte Carlo simulations):

| Currency | Anchor Rate (to USD) | Annual Volatility |
|----------|---------------------|-------------------|
| EUR | 0.92 | 8% |
| GBP | 0.79 | 10% |
| CNY | 7.25 | 6% |
| NGN | 1,580 | 40% |
| JPY | 149.5 | 12% |
| KRW | 1,435 | 10% |
| BRL | 5.85 | 18% |
| ZAR | 18.4 | 15% |
| TRY | 36.2 | 35% |

### MCDA Weights

Default AHP weights for the 7 supplier scoring criteria (sum to 1.0):

| Criterion | Weight |
|-----------|--------|
| Cost | 0.20 |
| Quality | 0.18 |
| Delivery | 0.15 |
| Risk | 0.15 |
| ESG | 0.12 |
| Innovation | 0.10 |
| Compliance | 0.10 |

Users can adjust these interactively on the Supplier Scorecards page.

### Risk Weights

Seven risk dimensions, also summing to 1.0:

| Dimension | Weight |
|-----------|--------|
| Lead-Time Volatility | 0.15 |
| Quality Failure | 0.20 |
| FX Exposure | 0.15 |
| Geopolitical | 0.10 |
| Concentration | 0.15 |
| Financial Health | 0.10 |
| ESG Compliance | 0.15 |

### Other Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `MC_DEFAULT_PATHS` | 10,000 | Monte Carlo default simulation count |
| `MC_MAX_PATHS` | 100,000 | Upper bound for simulations |
| `MC_DEFAULT_HORIZON_DAYS` | 90 | Default forecast window |
| `EMISSION_FACTORS` | Sea 0.016, Air 0.602, Rail 0.028, Road 0.062 | kgCO2e per tonne-km (GLEC v3) |
| `COST_LEAKAGE_INVESTIGATE_PCT` | 5% | Should-cost leakage threshold (yellow) |
| `COST_LEAKAGE_ESCALATE_PCT` | 15% | Leakage threshold (orange) |
| `COST_LEAKAGE_RED_FLAG_PCT` | 25% | Leakage threshold (red) |
| `HHI_COMPETITIVE` | 1,500 | HHI threshold for "Low" concentration |
| `HHI_MODERATE` | 2,500 | HHI threshold for "Moderate" |
| `HHI_CONCENTRATED` | 5,000 | HHI threshold for "High" |
| `RANDOM_SEED` | 42 | Reproducible data generation |
| `ENABLE_LIVE_FX` | false | Toggle live FX fetching |
| `DEMO_MODE` | true | Demo/production mode flag |

---

## 3. Database Schema

The schema is split into 10 SQL files executed in numeric order. Together they create 40 tables across 8 logical layers.

### 3.1 Reference Tables (01)

Nine lookup tables that rarely change after initial setup.

| Table | Rows | Description |
|-------|------|-------------|
| `countries` | 15 | ISO codes, region, income group, WGI governance, CPI corruption, sanctions flag, grid emission factor |
| `currencies` | 10 | Currency code/name, major flag, volatility class (Low/Medium/High/Very High) |
| `industry_sectors` | 6 | ISIC-aligned sectors with risk profiles |
| `ports` | 12 | Global ports with lat/long coordinates and congestion risk scores |
| `incoterms` | 7 | ICC 2020 trade terms with buyer-bears-freight/insurance flags |
| `compliance_frameworks` | 6 | UK Modern Slavery Act, EU CSRD, OECD DD, Nigerian NCDMB, US Dodd-Frank s.1502, ISO 20400 |
| `certifications_catalog` | 10 | ISO 9001/14001/45001/27001, SA8000, OHSAS, API Q1, ASME, CE, LEED |
| `risk_categories` | 7 | The 7 risk dimensions with default weights |
| `emission_factors` | 4 | Transport mode emission factors per GHG Protocol |

### 3.2 Master Data Tables (02)

Five tables representing the core business entities.

| Table | Description |
|-------|-------------|
| `suppliers` | 50 suppliers across 15 countries. Fields: tier level (Strategic through Blocked), revenue, lead times, defect rate, ISO cert flags, payment terms, status |
| `supplier_certifications` | Many-to-many link between suppliers and the certifications catalog with issue/expiry dates |
| `materials` | 80 industrial materials with HS codes, commodity groups, standard costs, and criticality flags |
| `supplier_material_catalog` | Which suppliers can provide which materials at what price and lead time |
| `contracts` | 40 contracts (Fixed Price, Cost Plus, Framework, Spot, Blanket) with FX clauses and EPD terms |

### 3.3 Transaction Tables (03)

Seven tables capturing operational activity.

| Table | Volume | Description |
|-------|--------|-------------|
| `purchase_orders` | ~2,000 | PO header with supplier, contract, dates, amounts, maverick flag, status |
| `po_line_items` | ~6,000 | One row per material ordered (quantity, unit price, line total, USD value) |
| `shipments` | ~1,800 | Transport mode, carrier, origin/destination port, ETA vs. actual arrival, delay days |
| `shipment_milestones` | varies | 9 milestone types from "Order Placed" through "Exception" |
| `quality_inspections` | ~1,500 | Sample size, defects found, computed defect rate, pass/fail/conditional result |
| `quality_incidents` | ~120 | Severity (Minor/Major/Critical), category, CAPA status, financial impact |
| `invoices` | ~2,000 | Amount, due date, paid date, days-to-pay, EPD taken flag, status |

### 3.4 Market Data Tables (04)

| Table | Volume | Description |
|-------|--------|-------------|
| `fx_rates` | ~7,000 | Daily exchange rates per currency (2022-2025), generated via GBM |
| `commodity_prices` | ~2,000 | Weekly prices for 8 commodity groups (HRC Steel, Copper, Brent, Nickel, Aluminium, etc.) |
| `country_risk_indices` | 60 | Annual political stability, regulatory quality, rule of law, logistics performance per country |

### 3.5 ESG and Compliance Tables (05)

| Table | Volume | Description |
|-------|--------|-------------|
| `esg_assessments` | 100 | Environmental (carbon/waste/water), Social (labor/H&S), Governance (ethics/transparency/board diversity), overall score, A-F rating |
| `compliance_checks` | varies | Status per supplier per framework (Compliant, Partially Compliant, Non-Compliant) with remediation plans |
| `carbon_estimates` | ~1,800 | Per-shipment CO2e estimates: transport mode, distance, weight, emission factor, resulting kgCO2e |
| `due_diligence_records` | varies | OECD 6-step due diligence status (Policy, Identify, Mitigate, Verify, Communicate, Remediate) |

### 3.6 Warehouse (Star Schema) (06)

Four dimension tables and two fact tables, designed for analytical queries and Power BI consumption.

**Dimensions:**

| Table | Type | Key fields |
|-------|------|------------|
| `dim_date` | Calendar | Year, quarter, month, week, day-of-week, is_weekend, fiscal year/quarter (April start) |
| `dim_supplier` | SCD Type 2 | Supplier attributes plus `scd_valid_from`, `scd_valid_to`, `scd_is_current` for historical tracking |
| `dim_material` | Standard | Category, commodity group, standard cost, criticality |
| `dim_geography` | Standard | Country, region, income group, sanctions flag |

**Facts:**

| Table | Grain | Key measures |
|-------|-------|--------------|
| `fact_procurement` | One PO line item | quantity, unit_price_usd, line_total_usd, landed_cost_usd, fx_rate_applied, cost_variance_pct, lead_time_days, delay_days, on_time_flag, defect_flag, is_maverick, co2e_kg |
| `fact_esg` | One ESG assessment | env/social/governance sub-scores, overall score, rating, compliance gap count |

### 3.7 Analytics Output Tables (07)

| Table | Description |
|-------|-------------|
| `supplier_scorecards` | MCDA output: 7 dimension scores, 7 weights, composite score, rank, tier, methodology used |
| `risk_assessments` | 7 risk dimension scores, composite risk, risk tier per supplier |
| `simulation_runs` | Monte Carlo results: scenario type, paths, distribution stats (mean/median/std/P5-P95), VaR, CVaR, input params (JSON) |
| `concentration_analysis` | HHI per dimension: spend shares, index value, category, recommendations |

### 3.8 Audit Tables (08)

| Table | Description |
|-------|-------------|
| `audit_log` | Row-level change tracking: table, record ID, action (INSERT/UPDATE/DELETE), old/new values as JSON, changed_by, timestamp |
| `data_quality_log` | DQ check results: check name/type, table/column, records checked/failed, computed failure %, severity |

---

## 4. Data Ingestion

### 4.1 Seed Data Generator (`generate_seed_data.py`)

A 14-step data generator that populates all master and transactional tables with realistic, internally consistent data. It runs inside a single database transaction so that either everything succeeds or nothing changes.

**Steps and what they produce:**

| Step | Function | Output |
|------|----------|--------|
| 1 | `seed_suppliers` | 50 suppliers across 15 countries with weighted tier distribution (10% Strategic, 25% Preferred, 40% Approved, 20% Conditional, 5% Blocked) |
| 2 | `seed_materials` | 80 industrial materials spanning 20+ commodity groups (Ferrous Metals, Flow Control, Instrumentation, Rotating Equipment, Wellhead, Subsea, Drilling, etc.) |
| 3 | `seed_catalog` | ~200 supplier-material catalog entries, priced at 75%-135% of standard cost |
| 4 | `seed_contracts` | 40 contracts (Fixed Price, Cost Plus, Framework, Spot, Blanket) with randomized FX clauses and EPD percentages |
| 5 | `seed_purchase_orders` | 2,000 POs with weighted statuses (60% Delivered, 12% Closed, 5% Cancelled) and ~6,000 line items |
| 6 | `seed_shipments` | 1,800 shipments with mode weights (55% Sea, 20% Air, 15% Road, 10% Rail). Delay drawn from Normal(2, 5) |
| 7 | `seed_quality` | 1,500 quality inspections (defect rate from Normal(3, 4)) and 120 incidents (50% Minor, 35% Major, 15% Critical) |
| 8 | `seed_invoices` | ~2,000 invoices (85% paid, 25% with EPD taken). Days-to-pay varies -10 to +30 days relative to due date |
| 9 | `seed_fx_rates` | Daily FX rates for 9 currencies (2022-2025) generated via GBM, re-scaled so the final value matches the anchor rate in config |
| 10 | `seed_commodity_prices` | Weekly prices for 8 commodities via GBM with 20% annual volatility |
| 11 | `seed_country_risk` | 15 countries x 4 years = 60 annual risk index records |
| 12 | `seed_esg` | 100 ESG assessments (50 suppliers x 2 years). Overall = 35% Environmental + 35% Social + 30% Governance |
| 13 | `seed_carbon` | 1,800 carbon estimates using GLEC Framework emission factors |
| 14 | `seed_certifications` / `seed_compliance` | ~150 certification links and compliance/due diligence records |

All randomness uses `config.RANDOM_SEED = 42` so that results are reproducible across runs.

### 4.2 External Data Loader (`external_data_loader.py`)

An alternative to the seed generator for importing real company data from CSV files.

**Two-phase process:**

**Phase 1 - Validation** (`load_all_files`):
- Scans an input directory for 4 required files (`suppliers.csv`, `materials.csv`, `purchase_orders.csv`, `po_line_items.csv`) and 3 optional files (`shipments.csv`, `invoices.csv`, `esg_assessments.csv`)
- Validates each file against a schema definition (required columns, numeric fields, value ranges)
- Per-file rules: lead_time > 0, standard_cost >= 0, valid transport modes, valid ESG ratings
- Logs detailed error and warning messages before aborting on failure

**Phase 2 - Import** (`import_data`):
- Clears 30 tables in reverse-FK order
- Inserts data in FK order, resolving foreign keys via lookup helpers (country name to country_id, currency code to currency_id, etc.)
- Auto-generates `supplier_material_catalog` from PO line item data
- Seeds FX and commodity market data by calling the seed generator's FX/commodity functions

**Usage:**
```bash
python data_ingestion/external_data_loader.py --input-dir ./company_data
# Or through the pipeline:
python run_aegis_pipeline.py --external ./company_data
```

Sample CSV templates are provided in `external_data_samples/`.

### 4.3 Live FX Fetcher (`live_data_fetcher.py`)

Fetches real-time exchange rates from free APIs, gated by `config.ENABLE_LIVE_FX`.

**3-tier API failover:**
1. `open.er-api.com` (primary)
2. `exchangerate-api.com` (secondary)
3. `frankfurter.app` (tertiary)

Each attempt has a 10-second timeout. Only currencies present in `config.FX_VOLATILITIES` are kept.

When successful, today's rates are upserted into `fx_rates` using `ON DUPLICATE KEY UPDATE`. The fetcher is called from the pipeline and is also available as a manual refresh button in the dashboard sidebar.

---

## 5. Warehouse ETL

`populate_warehouse.py` transforms the OLTP tables into a star schema suitable for analytical queries and Power BI.

### ETL Steps

| Step | Function | What it does |
|------|----------|--------------|
| 1 | `populate_dim_date` | Generates a calendar dimension from 2022-01-01 to 2028-12-31. Includes year, quarter, month, week, day-of-week, is_weekend, and fiscal year/quarter (April start). Date key is an integer in YYYYMMDD format |
| 2 | `populate_dim_supplier` | SCD Type 2 initial load. Joins `suppliers` with `countries`, `industry_sectors`, `currencies`, latest ESG rating, and latest risk tier. Sets `scd_is_current = TRUE` |
| 3 | `populate_dim_material` | Copies from `materials` into `dim_material` |
| 4 | `populate_dim_geography` | Copies from `countries` into `dim_geography` |
| 5 | `populate_fact_procurement` | Grain = one PO line item. Joins through purchase_orders, suppliers, materials, shipments, quality inspections, carbon estimates, and FX rates. Populates 20 measures including landed cost, cost variance, lead time, delay, on-time flag, defect flag, and CO2e |
| 6 | `populate_fact_esg` | Grain = one ESG assessment. Joins to dim_supplier and adds compliance gap count |

The ETL uses a full-refresh pattern (DELETE then INSERT) within a single transaction. This keeps the logic simple and makes every run idempotent.

---

## 6. Analytics Engines

Eight independent engines, each reading from the database and writing results back. They can run standalone or as part of the pipeline.

### 6.1 MCDA Engine (`mcda_engine.py`)

Multi-criteria decision analysis for supplier ranking.

**Three scoring methods:**

**TOPSIS** (Technique for Order of Preference by Similarity to Ideal Solution):
1. Build a decision matrix from 7 criteria per supplier (cost, quality, delivery, risk, ESG, innovation, financial health)
2. Vector-normalise each column
3. Multiply by weights
4. Identify the ideal best and ideal worst vectors
5. Compute Euclidean distance from each supplier to both
6. Closeness coefficient: $C_i = D_i^- / (D_i^+ + D_i^-)$

**PROMETHEE-II** (Preference Ranking Organization Method for Enrichment Evaluation):
- Uses a linear preference function with indifference threshold $q$ and strict preference threshold $p$
- Computes pairwise preference indices $\pi(a_i, a_j)$
- Positive flow $\phi^+$, negative flow $\phi^-$, net flow $\phi = \phi^+ - \phi^-$

**WSM** (Weighted Sum Model):
- Min-max normalise each column to [0, 1]
- Dot product with weight vector

After scoring, results are scaled to 0-100 and suppliers are assigned to tiers:

| Score | Tier |
|-------|------|
| >= 80 | Strategic |
| >= 65 | Preferred |
| >= 50 | Approved |
| >= 35 | Conditional |
| < 35 | Blocked |

Results are written to `supplier_scorecards`.

### 6.2 Risk Scoring (`risk_scoring.py`)

Computes a 7-dimension composite risk score for each supplier.

**Risk dimensions (all normalized to 0-100, higher = riskier):**

| Dimension | Calculation |
|-----------|-------------|
| Financial | Based on supplier revenue. Lower revenue = higher risk |
| Operational | Weighted sum of defect rate, on-time delivery shortfall, and incident count |
| Geopolitical | Weighted sum of WGI governance gap, Fragile States Index, and sanctions flag |
| Compliance | Based on non-compliant check count and certification gap |
| Concentration | Mapped from supplier tier level (Strategic = 15, Blocked = 90) |
| ESG | Inverse of ESG overall score |
| Cyber | Based on currency volatility, governance gap, and certification count |

**Composite risk** is the weighted sum using `config.RISK_WEIGHTS`. The result is classified into tiers:

| Score | Tier |
|-------|------|
| < 30 | Low |
| < 55 | Medium |
| < 75 | High |
| >= 75 | Critical |

Results are written to `risk_assessments`.

### 6.3 Monte Carlo Simulations (`monte_carlo.py`)

Four types of stochastic simulation.

**FX Risk (Geometric Brownian Motion):**

$$S_{t+1} = S_t \cdot \exp\!\left(\left(-\tfrac{1}{2}\sigma^2\right)\Delta t + \sigma\sqrt{\Delta t} \cdot Z\right)$$

where $Z \sim N(0,1)$. Runs 10,000 paths (configurable up to 100,000) over 90 trading days. Reports P5, P25, P50, P75, P95, VaR(95%), and CVaR(95%).

**Lead-Time Risk:**
- Fits a log-normal distribution to historical shipment lead times from the `shipments` table
- Computes $\mu$ and $\sigma$ of $\ln(\text{lead\_time})$
- Generates random samples from that distribution
- Falls back to a preset array if fewer than 5 historical data points exist

**Disruption Risk:**
- Four preset scenarios: port closure, supplier failure, sanctions, natural disaster
- Each has a cost multiplier (drawn from Normal distribution) and a lead-time addition
- Multiplies baseline annual spend by the sampled cost multiplier

**Combined Cost Scenario:**
- Simulates FX movements per currency (GBM, 90 days) and commodity price shocks (Normal, mean=1, std=0.10, floor at 0.7)
- Multiplies baseline spend by combined FX and commodity factors
- Returns full cost distribution with savings-at-risk

All simulation results are persisted to `simulation_runs` with JSON-serialised parameters.

### 6.4 Concentration Analysis (`concentration.py`)

Herfindahl-Hirschman Index across 5 dimensions.

$$HHI = \sum_{i=1}^{N} s_i^2$$

where $s_i$ is spend share as a percentage. Computed separately for Supplier, Country, Currency, Material, and Port.

| HHI | Category |
|-----|----------|
| < 1,500 | Low (competitive) |
| < 2,500 | Moderate |
| >= 2,500 | High (concentrated) |

For each dimension, the engine also computes top-3 concentration share and generates text recommendations for any entity holding more than 25% or 40% of spend.

Results are written to `concentration_analysis` in batches of 100.

### 6.5 Carbon Engine (`carbon_engine.py`)

GHG Protocol Scope 3 Category 4 (upstream transport) emissions.

$$\text{CO}_2\text{e (kg)} = \text{weight (tonnes)} \times \text{distance (km)} \times \text{emission factor}$$

- **Emission factors** come from the GLEC Framework v3: Sea (0.016), Air (0.602), Rail (0.028), Road (0.062) kgCO2e/tonne-km
- **Distance** is computed using the Haversine formula between origin and destination port coordinates:

$$d = 2R \cdot \arcsin\!\sqrt{\sin^2\!\left(\tfrac{\Delta\phi}{2}\right) + \cos\phi_1 \cos\phi_2 \sin^2\!\left(\tfrac{\Delta\lambda}{2}\right)}$$

- **Mode-shift analysis** filters air shipments and calculates CO2e savings from switching to sea or rail
- Also computes carbon intensity (kgCO2e per $1,000 freight value)

### 6.6 Should-Cost Model (`should_cost.py`)

Bottom-up cost estimation and leakage detection per material-supplier combination.

**Five cost components:**

| Component | Calculation |
|-----------|-------------|
| Material cost | `standard_cost_usd` from materials table |
| Freight | Region-based percentage (Africa 12%, Europe 5%, Asia 8%, Americas 7%, Middle East 6%) |
| Customs/duties | Region-based (Africa 10%, Asia 7%, else 3%) |
| Overhead | Fixed 5% of material cost |
| Supplier margin | Assumed 12% |

**Should-cost total** = sum of all five. **Variance** = quoted price minus should-cost (both absolute and percentage).

**Leakage classification:**

| Variance | Flag |
|----------|------|
| < 5% | Within Range |
| 5-15% | Investigate |
| 15-25% | Escalate |
| >= 25% | Red Flag |

The leakage summary reports total quoted vs. should-cost, total leakage in dollars and percent, and the top 10 overpriced items.

### 6.7 Working Capital (`working_capital.py`)

DPO analysis, invoice aging, and early payment discount optimization.

**`analyze_working_capital`** runs three SQL queries:
1. Aging by supplier: invoice count, total amount, average days-to-pay, overdue amount, EPD captured/missed
2. Monthly DPO trend: average DPO, total spend, overdue count
3. EPD analysis by payment terms bucket: volume, discount captured value, average early payment timing

**`optimize_payment_timing`** implements a greedy knapsack algorithm for EPD:
1. Query pending invoices that have an EPD percentage
2. Compute annualised return for each: `(discount_pct / 100) * 365 / days_early`
3. Filter invoices where the annualised return exceeds the cost of capital (default 8%)
4. Sort by annualised return descending
5. Greedily select highest-return invoices until the budget constraint (default $500K) is exhausted

### 6.8 Scenario Planner (`scenario_planner.py`)

Three what-if scenarios.

**Supplier Switch** (`scenario_supplier_switch`):
- Compares two suppliers on cost, lead-time, quality, and ESG
- Queries each supplier's PO history, catalog pricing, delay stats, defect rate, and latest ESG score
- Returns estimated spend change (%), delay change (days), quality delta, and ESG delta

**Currency Hedge** (`scenario_currency_hedge`):
- Models hedging a percentage (default 80%) of currency exposure at a forward rate (default 2% premium)
- Calls `monte_carlo.simulate_fx` internally (5,000 paths, 90 days)
- Compares unhedged mean/P95 cost vs. hedged cost (fixed-rate portion plus simulated remainder)
- Returns savings at P95 and hedge premium cost

**Nearshoring** (`scenario_nearshoring`):
- Models reallocating a percentage (default 30%) of spend to a target region
- Assumptions: 5% higher unit cost, 40% lower freight, 30% faster delivery
- Returns net cost impact, freight savings, lead-time improvement, and a carbon reduction estimate

---

## 7. Streamlit Dashboard

The dashboard is a 12-page Streamlit multipage app. Every page is protected by a login gate (`utils/auth.py`) and shows a data freshness badge in the sidebar.

### 7.1 Entry Point (`streamlit_app.py`)

- Sets page config (wide layout, AEGIS branding)
- Runs `login_gate()` before rendering anything
- Applies custom CSS for metrics, sidebar gradient, and headings
- Shows a landing page with 6 live KPIs from the database (active suppliers, PO count, total spend, countries, shipments, materials)
- Displays navigation cards linking to all 12 analytics modules

### 7.2 Page-by-Page Overview

**Page 1: Executive Dashboard**
- 6 KPIs: Total Spend, Active Suppliers, On-Time %, Defect Rate %, Maverick Spend %, Overdue Invoices
- Monthly spend trend line chart
- Spend by region donut chart
- Supplier tier distribution bar chart
- Active quality incident alerts table

**Page 2: Supplier Scorecards**
- Sidebar controls: methodology selector (TOPSIS/PROMETHEE/WSM), year filter, 7 weight sliders with auto-normalization
- "Run MCDA" button triggers real-time re-computation
- Ranked supplier table with gradient-colored scores
- Tier distribution pie chart
- Radar chart for the top-ranked supplier across all 7 dimensions
- Composite score histogram colored by tier

**Page 3: Risk Radar**
- Risk heatmap showing top 20 suppliers across 7 risk dimensions
- KPIs: suppliers assessed, average risk score, Critical/High counts
- Risk tier distribution pie chart
- Average risk by region bar chart
- Single-supplier radar drill-down (select a supplier and see its 7 dimension scores)

**Page 4: Monte Carlo Lab**
- 4 simulation tabs:
  - **FX Risk:** Select currency, paths (1K-100K), horizon (30-365 days), optional volatility override. Shows current rate, mean, P95, VaR, CVaR, and histogram
  - **Lead Time:** Select simulation count and optional supplier. Shows historical mean, simulated mean, P95, standard deviation, and histogram
  - **Disruption:** Select scenario type (port closure/supplier failure/sanctions/natural disaster), affected entity, duration. Shows baseline spend, cost impact (mean/P95), lead-time addition, CVaR
  - **Total Cost:** Combined FX + commodity simulation. Shows baseline/mean/P95 cost, VaR, and histogram

**Page 5: Concentration Analysis**
- KPI row with HHI score and top entity per dimension (color-coded green/yellow/red)
- HHI bar chart with threshold lines at 1,500 and 2,500
- 4 spend distribution tabs: By Supplier (treemap), By Country (pie), By Currency (pie), By Material (treemap by commodity group)

**Page 6: Carbon Dashboard**
- KPIs: total estimates, total CO2e in tonnes, average carbon intensity per $1K
- Emissions by transport mode (bar and pie charts)
- Top 15 emitting suppliers (bar chart colored by intensity)
- Top 15 emitting routes (bar chart colored by mode)
- Mode-shift reduction opportunities table with total potential savings in tonnes

**Page 7: Should-Cost**
- KPIs: items analysed, total quoted vs. should-cost, total leakage (USD and %)
- Leakage classification bar and pie (Within Range / Investigate / Escalate / Red Flag)
- Waterfall chart decomposing the highest-leakage item into its 5 cost components vs. quoted price
- Detailed leakage table filterable by flag severity

**Page 8: Working Capital**
- DPO trend over time (line chart)
- Invoice aging by supplier (grouped bar chart)
- EPD optimization: interactive budget slider and cost-of-capital input, shows which invoices to pay early for the highest annualised return
- Summary metrics: total spend, overdue amount, discount captured vs. missed

**Page 9: ESG Compliance**
- EcoVadis-style overall and sub-score gauges
- ESG rating distribution across suppliers
- OECD 6-step due diligence status tracker
- Compliance framework pass/fail summary

**Page 10: Scenario Planner**
- Three tabs: Supplier Switch (pick two suppliers, compare), Currency Hedge (pick currency, hedge %, forward premium), Nearshoring (pick target region, reallocation %)
- Each tab shows before/after metrics and net impact

**Page 11: Data Explorer**
- Dropdown to select any of the 40+ tables
- Shows table row count and first N rows
- Ad-hoc SQL editor with results displayed in a table

**Page 12: Settings**
- View and modify MCDA weights, risk weights, FX parameters
- Toggle live FX fetching
- View pipeline run history and data freshness

### 7.3 Authentication

`utils/auth.py` provides a SHA-256 based login gate. Default credentials:
- Username: `admin`
- Password: `aegis2025`

Override via environment variables `AEGIS_DASHBOARD_USER` and `AEGIS_DASHBOARD_PASS_HASH`.

---

## 8. Utilities

### 8.1 Logging (`utils/logging_config.py`)

- `get_logger(name)` returns a logger under the `aegis.*` namespace with two handlers:
  - **File handler:** writes to `logs/aegis_pipeline.log` at DEBUG level
  - **Console handler:** writes to stdout at INFO level
- `AuditLogger` writes row-level change events to the `audit_log` table (table name, record ID, action, old/new JSON values, changed_by)
- `DataQualityLogger` writes DQ check results to `data_quality_log` (check name/type, records checked/failed, severity)

### 8.2 Export (`utils/export.py`)

- `to_excel_bytes(dataframes)` takes a dict of `{sheet_name: DataFrame}` and returns openpyxl bytes for download buttons
- `to_csv_bytes(df)` returns UTF-8 CSV bytes
- `generate_executive_summary(engine)` queries 5 sheets of data (scorecards, risk, concentration, spend summary, carbon) for a one-click executive export

### 8.3 Freshness Tracking (`utils/freshness.py`)

- `record_start()` creates a `pipeline_runs` row (auto-creates table if missing) with status "running". Returns a `run_id`
- `record_finish(run_id, status, duration)` updates the row with completion time and status
- `freshness_badge()` computes the age of the last successful run and returns an emoji string: green (< 1 hour), yellow (< 24 hours), red (> 24 hours), or warning (no runs)

The badge is shown in the Streamlit sidebar on every page load.

---

## 9. Testing

49 tests across 2 files and 16 test classes. Tests are designed to run without a database connection by testing pure logic (math, configs, imports, module structure).

### `tests/test_aegis.py` (24 tests)

| Class | Tests | What it covers |
|-------|-------|----------------|
| `TestConfig` (6) | `test_database_url_set`, `test_fx_volatilities_valid`, `test_risk_weights_sum_to_one`, `test_mcda_weights_sum_to_one`, `test_hhi_thresholds_ordered`, `test_emission_factors_positive` | Validates all config parameters are well-formed and consistent |
| `TestMCDAEngine` (5) | `test_topsis_returns_correct_shape`, `test_topsis_best_alternative`, `test_promethee_returns_correct_shape`, `test_wsm_returns_correct_shape`, `test_tier_from_score` | Pure-math MCDA scoring on synthetic matrices |
| `TestMonteCarlo` (3) | `test_simulate_fx_returns_dict`, `test_simulate_fx_gbm_positive`, `test_simulate_fx_var_positive` | GBM output shape, positivity, VaR sanity |
| `TestRiskScoring` (1) | `test_risk_tier_mapping` | Tier boundary classification |
| `TestConcentration` (4) | `test_compute_hhi_uniform`, `test_compute_hhi_monopoly`, `test_compute_hhi_equal_ten`, `test_categorize_hhi` | HHI math and classification |
| `TestCarbonEngine` (3) | `test_haversine`, `test_haversine_same_point`, `test_emission_factors_exist` | Haversine formula accuracy and factor presence |
| `TestShouldCost` (1) | `test_leakage_flags` | Leakage threshold classification |
| `TestWorkingCapital` (1) | `test_epd_annualized_return` | EPD return formula |

### `tests/test_extended.py` (25 tests)

| Class | Tests | What it covers |
|-------|-------|----------------|
| `TestAuth` (4) | `test_default_password_hash`, `test_check_password_correct`, `test_check_password_wrong`, `test_default_username` | SHA-256 login mechanism |
| `TestLoggingConfig` (5) | `test_get_logger_returns_logger`, `test_logger_has_handlers`, `test_log_dir_exists`, `test_data_quality_logger_instantiates`, `test_audit_logger_instantiates` | Logger setup and handler attachment |
| `TestExternalDataLoader` (4) | `test_loader_detects_csv_files`, `test_loader_validates_columns`, `test_loader_empty_dir`, `test_loader_invalid_csv` | CSV validation and error handling |
| `TestScenarioPlannerMath` (2) | `test_hedge_savings_formula`, `test_nearshoring_cost_premium` | Hedge and nearshoring math |
| `TestWorkingCapitalMath` (2) | `test_dpo_calculation`, `test_epd_negative_annualized_impossible` | DPO and EPD edge cases |
| `TestShouldCostMath` (3) | `test_cost_variance`, `test_leakage_flag_investigate`, `test_leakage_flag_escalate`, `test_leakage_flag_red` | Should-cost variance and flag boundaries |
| `TestIntegration` (4) | `test_config_database_url_format`, `test_all_analytics_importable`, `test_all_ingestion_importable`, `test_utils_importable` | Import smoke tests for all modules |

### Running Tests

```bash
pytest tests/ -v                          # Run all 49 tests
pytest tests/test_aegis.py -v             # Run core tests only
pytest tests/test_extended.py -v          # Run extended tests only
pytest tests/ -v -k "TestMonteCarlo"      # Run one test class
```

---

## 10. CI/CD Pipeline

`.github/workflows/ci.yml` defines three jobs that run on every push to `main`/`develop` and on pull requests to `main`.

### Job 1: `test`

1. Starts a MySQL 8.0 service container
2. Installs Python 3.11 and project dependencies
3. Waits for MySQL to accept connections (retries every 3 seconds)
4. Deploys the full database schema (SQL files 01-09)
5. Runs `pytest tests/ -v`

### Job 2: `lint`

1. Runs `black --check --diff .` (non-blocking, prints a warning if formatting differs)
2. Runs `flake8 . --max-line-length=120` with an extended ignore list for cosmetic codes

### Job 3: `docker`

1. Only runs on `main` branch pushes, after `test` passes
2. Builds the Docker image from `Dockerfile`
3. Smoke-tests the image by running `python -c "import config"`

---

## 11. Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y default-mysql-client curl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
WORKDIR /app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

### docker-compose.yml

Two services:

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `mysql` | mysql:8.0 | 3307 (host) -> 3306 (container) | SQL files auto-execute from mounted `database/` directory. Persistent volume `aegis-mysql-data` |
| `app` | Built from Dockerfile | 8501 | Waits for MySQL health check before starting. `DATABASE_URL` set to point at the `mysql` container |

### Running

```bash
# Start both services
docker-compose up -d

# Dashboard available at http://localhost:8501
# MySQL available at localhost:3307

# Tear down
docker-compose down
# Remove data volume too:
docker-compose down -v
```

Environment variables `DB_PASSWORD` and `DB_NAME` can be set in a `.env` file (see `.env.example`).

---

## 12. Power BI Layer

The `powerbi/` directory contains everything needed to build a Power BI executive dashboard on top of the same MySQL database.

| File | Description |
|------|-------------|
| `AEGIS_Dashboard_BUILD.md` | 10-page step-by-step build guide with visual layout instructions |
| `AEGIS_Theme.json` | Custom color theme (Tableau-10 palette adapted for AEGIS) |
| `DAX_Measures.md` | 25+ DAX measure definitions: Total Spend, YoY Growth, OTD %, Defect Rate, Risk Score avg, HHI, CO2 Intensity, Working Capital metrics |
| `PowerQuery_Connections.pq` | 14 ready-to-paste Power Query M scripts for connecting to the warehouse tables |

Additional documentation in `docs/`:

| File | Description |
|------|-------------|
| `DATA_MODEL.md` | Full star-schema reference with relationship diagram |
| `SETUP_GUIDE.md` | End-to-end Power BI Desktop connection and import instructions |
| `ARCHITECTURE.md` | System architecture overview with component map |

---

## 13. Pipeline Execution Walkthrough

When you run `python run_aegis_pipeline.py`, here is exactly what happens:

### Step 1/6: Deploy Database Schema

```
[pipeline] ============================================================
[pipeline]   Step 1/6 — Deploy Database Schema
[pipeline] ============================================================
```

- Opens a raw PyMySQL connection (not SQLAlchemy) with `CLIENT.MULTI_STATEMENTS` enabled
- Runs `CREATE DATABASE IF NOT EXISTS aegis_procurement`
- Iterates through SQL files 01-09 in sorted order
- Each file is read, stripped of any `CREATE DATABASE` / `USE` statements (already handled), and executed
- Errors for "already exists" or "duplicate" are silently ignored (idempotent)

### Step 2/6: Seed Reference Data

```
[pipeline] ============================================================
[pipeline]   Step 2/6 — Seed Reference Data
[pipeline] ============================================================
```

- Re-executes `09_seed_reference_data.sql` to ensure all 9 lookup tables have their baseline rows
- Uses `INSERT IGNORE` so existing rows are not duplicated

### Step 3/6: Generate Sample Data (or Load External Data)

```
[pipeline] ============================================================
[pipeline]   Step 3/6 — Generate Sample Data
[pipeline] ============================================================
```

- If `--external DIR` was passed: runs `ExternalDataLoader` against the CSV directory
- Otherwise: runs `generate_seed_data.main()` to create all transactional data

### Step 4/6: Populate Data Warehouse

```
[pipeline] ============================================================
[pipeline]   Step 4/6 — Populate Data Warehouse
[pipeline] ============================================================
```

- Runs the 6-step ETL: dim_date, dim_supplier (SCD2), dim_material, dim_geography, fact_procurement, fact_esg
- Full refresh (delete + insert) inside a single transaction

### Step 5/6: Run Analytics Engines

```
[pipeline] ============================================================
[pipeline]   Step 5/6 — Run Analytics Engines
[pipeline] ============================================================
```

- MCDA scoring (TOPSIS by default)
- Risk scoring (7 dimensions, composite, tier assignment)
- Concentration analysis (HHI across 5 dimensions)
- Carbon emission calculations
- Should-cost leakage summary
- Working capital analysis
- Scenario planner baseline run (nearshoring)

### Step 6/6: Verification

```
[pipeline] ============================================================
[pipeline]   Step 6/6 — Verification
[pipeline] ============================================================
```

- Counts rows in 18 key tables
- Logs each table name, row count, and OK/EMPTY status
- Writes data quality log entries for each check

### Pipeline Flags

| Flag | Effect |
|------|--------|
| `--skip-schema` | Skip Step 1 (useful after first run) |
| `--skip-seed` | Skip Step 3 (keep existing data) |
| `--skip-warehouse` | Skip Step 4 |
| `--skip-analytics` | Skip Step 5 |
| `--verify-only` | Only run Step 6 |
| `--external DIR` | Use CSV import instead of seed generator |

---

## 14. Data Flow Diagram

```
┌──────────────────┐     ┌──────────────────┐
│  ERP / PO / FX   │     │  Company CSVs    │
│  Source Data      │     │  (7 file types)  │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         v                        v
┌──────────────────┐     ┌──────────────────┐
│ generate_seed_   │     │ external_data_   │
│ data.py          │ OR  │ loader.py        │
│ (14 steps)       │     │ (validate+import)│
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         v                        v
┌─────────────────────────────────────────────┐
│           OLTP Layer (30+ tables)           │
│  suppliers, materials, POs, shipments,      │
│  invoices, FX rates, ESG, carbon, etc.      │
└────────────────────┬────────────────────────┘
                     │
                     v
         ┌───────────────────────┐
         │  populate_warehouse   │
         │  .py (ETL, SCD2)     │
         └───────────┬───────────┘
                     │
                     v
┌─────────────────────────────────────────────┐
│         Warehouse Layer (6 tables)          │
│  dim_date, dim_supplier, dim_material,      │
│  dim_geography, fact_procurement, fact_esg  │
└────────────────────┬────────────────────────┘
                     │
         ┌───────────┼───────────┐
         v           v           v
┌──────────────┐ ┌────────┐ ┌────────────┐
│ 8 Analytics  │ │Streamlit│ │  Power BI  │
│ Engines      │ │Dashboard│ │  Desktop   │
│              │ │(12 pgs) │ │            │
└──────┬───────┘ └────────┘ └────────────┘
       │
       v
┌─────────────────────────────────────────────┐
│       Analytics Output (4 tables)           │
│  scorecards, risk, simulations, HHI         │
└─────────────────────────────────────────────┘
```

---

## 15. Adding Your Own Data

### Option A: Replace Seed Data with CSVs

1. Prepare your CSV files following the schemas in `EXTERNAL_DATA_GUIDE.md` and the templates in `external_data_samples/`
2. Required files: `suppliers.csv`, `materials.csv`, `purchase_orders.csv`, `po_line_items.csv`
3. Optional files: `shipments.csv`, `invoices.csv`, `esg_assessments.csv`
4. Run:
   ```bash
   python run_aegis_pipeline.py --external ./your_data_folder
   ```

This clears all existing data, imports your CSVs, runs warehouse ETL, and executes all analytics.

### Option B: Add Data Incrementally

1. Insert records directly into the OLTP tables via SQL or a custom script
2. Re-run warehouse and analytics:
   ```bash
   python run_aegis_pipeline.py --skip-schema --skip-seed
   ```

### Option C: Use the Data Explorer

Page 11 (Data Explorer) in the dashboard provides an ad-hoc SQL editor where you can run INSERT, UPDATE, or SELECT statements against any table.

---

## Summary

| Component | Count |
|-----------|-------|
| Database tables | 40 |
| SQL schema files | 10 |
| Analytics engines | 8 |
| Streamlit pages | 12 |
| Utility modules | 4 |
| Data ingestion modules | 4 |
| Pytest tests | 49 |
| CI/CD jobs | 3 |
| Power BI assets | 4 files + 3 docs |
| Tracked currencies | 9 |
| Reference countries | 15 |
| Reference ports | 12 |
| Compliance frameworks | 6 |

The entire system runs from a single command (`python run_aegis_pipeline.py`) and the dashboard launches with `streamlit run streamlit_app.py`. For containerized deployment, `docker-compose up -d` brings up both MySQL and the Streamlit app.
