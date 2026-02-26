# AEGIS — Project Walkthrough

> **Adaptive Engine for Global Intelligent Sourcing**
>
> Investment-grade procurement analytics platform combining MCDA supplier
> selection, Monte Carlo risk simulation, ESG compliance tracking, and
> should-cost modelling across a 40+ table normalised schema.

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
│
├── config.py                          # Central configuration (3-tier secret resolution)
├── streamlit_app.py                   # Streamlit entry point (landing page)
├── run_aegis_pipeline.py              # 6-step pipeline orchestrator
├── Dockerfile                         # Python 3.11-slim + Streamlit CMD
├── docker-compose.yml                 # MySQL 8.0 + App (two-service stack)
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Dev/test dependencies (pytest, black, flake8)
├── pytest.ini                         # Pytest configuration
├── README.md                          # Quick-start and overview
├── PROJECT_WALKTHROUGH.md             # ← You are here
│
├── .github/workflows/
│   └── ci.yml                         # 3-job CI (test + lint + docker)
│
├── database/                          # 10 SQL files (executed in order)
│   ├── 00_MASTER_DEPLOY.sql           # Convenience wrapper
│   ├── 01_create_reference_tables.sql # 9 lookup tables
│   ├── 02_create_master_tables.sql    # 5 master/entity tables
│   ├── 03_create_transaction_tables.sql # 7 transactional tables
│   ├── 04_create_market_tables.sql    # 3 market data tables
│   ├── 05_create_esg_tables.sql       # 4 ESG/compliance tables
│   ├── 06_create_warehouse.sql        # 4 dimensions + 2 fact tables
│   ├── 07_create_analytics_tables.sql # 4 analytics output tables
│   ├── 08_create_audit_tables.sql     # 2 audit/DQ tables
│   └── 09_seed_reference_data.sql     # Reference data inserts
│
├── data_ingestion/
│   ├── generate_seed_data.py          # 14-step realistic data generator (1 000+ lines)
│   ├── populate_warehouse.py          # Star-schema ETL with SCD Type 2
│   ├── external_data_loader.py        # Import company CSV data
│   └── live_data_fetcher.py           # Live FX rates (3-tier API failover)
│
├── analytics/                         # 8 independent engines
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
│   ├── 01_📈_Executive_Dashboard.py
│   ├── 02_🏆_Supplier_Scorecards.py
│   ├── 03_⚡_Risk_Radar.py
│   ├── 04_🎲_Monte_Carlo_Lab.py
│   ├── 05_🔎_Concentration_Analysis.py
│   ├── 06_🌍_Carbon_Dashboard.py
│   ├── 07_💲_Should_Cost.py
│   ├── 08_🏦_Working_Capital.py
│   ├── 09_🌱_ESG_Compliance.py
│   ├── 10_🔮_Scenario_Planner.py
│   ├── 11_🗄_Data_Explorer.py
│   └── 12_⚙️_Settings.py
│
├── utils/
│   ├── auth.py                        # HMAC-SHA-256 login gate (env-var driven)
│   ├── db.py                          # Cached SQLAlchemy engine, connection check
│   ├── export.py                      # Excel/CSV export helpers
│   ├── freshness.py                   # Pipeline run tracking + sidebar badge
│   └── logging_config.py              # File + console logging, AuditLogger, DQLogger
│
├── powerbi/                           # Power BI companion assets
│   ├── AEGIS_Dashboard_BUILD.md       # 10-page build guide
│   ├── AEGIS_Theme.json               # Custom colour theme
│   ├── DAX_Measures.md                # 25+ DAX measure definitions
│   └── PowerQuery_Connections.pq      # 14 Power Query M scripts
│
├── external_data_samples/             # 7 CSV templates for company data
├── tests/                             # 49 pytest tests (2 files, 16 classes)
├── docs/                              # DATA_MODEL.md, SETUP_GUIDE.md, ARCHITECTURE.md
├── logs/                              # Runtime log output (auto-created)
└── .streamlit/                        # Streamlit Cloud secrets template
```

---

## 2. Configuration

All tuneable parameters live in **`config.py`** (156 lines). Nothing is hard-coded in the analytics or ingestion modules; they all `import config`.

### 2.1 Three-Tier Secret Resolution

Every database credential is resolved through a priority chain:

```
1.  Streamlit Cloud secrets   →  st.secrets["database"]["DB_HOST"]
2.  Environment variables     →  os.getenv("DB_HOST")
3.  Built-in defaults         →  "localhost"
```

This is implemented by the `_secret(section, key, fallback)` helper function. The design lets the same code run on Streamlit Cloud (secrets TOML), in Docker (env vars), and locally (defaults) without any code changes.

### 2.2 Database Connection

```python
DB_HOST     = _secret("database", "DB_HOST", "localhost")
DB_PORT     = int(_secret("database", "DB_PORT", "3306"))
DB_USER     = _secret("database", "DB_USER", "root")
DB_PASSWORD = _secret("database", "DB_PASSWORD", "")
DB_NAME     = _secret("database", "DB_NAME", "aegis_procurement")
DB_SSL      = _secret("database", "DB_SSL", "false")  # → bool

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# If DB_SSL is true, appends ?ssl_verify_cert=true&ssl_verify_identity=true
```

`pymysql_ssl_context()` returns an `ssl.SSLContext` for raw pymysql connections when SSL is enabled, or `None` when it is not. This is used by the pipeline orchestrator and the logging/audit modules.

### 2.3 FX Anchor Rates (Live Feed)

The module-level constant `FX_ANCHOR_RATES` is populated at import time by calling `_fetch_live_fx()`. This function implements a **3-tier API failover**:

| Priority | API Endpoint | Timeout |
|----------|-------------|---------|
| 1 (primary) | `open.er-api.com/v6/latest/USD` | 8 s |
| 2 (secondary) | `api.exchangerate-api.com/v4/latest/USD` | 8 s |
| 3 (tertiary) | `api.frankfurter.dev/latest?base=USD` | 8 s |

If a live API provides rates, any currencies not returned (e.g. Frankfurter may omit NGN) are back-filled from a static fallback table. If **all three APIs fail**, the static table is used in full.

**Offline guard:** Setting `AEGIS_FX_OFFLINE=1` as an environment variable skips all HTTP requests and returns the static rates immediately. This is used in CI/CD Docker tests to prevent network dependencies from failing builds.

**Static fallback rates** (updated 25 Feb 2026):

| Currency | Rate to USD |
|----------|------------|
| EUR | 0.85 |
| GBP | 0.74 |
| CNY | 6.89 |
| NGN | 1,354.88 |
| JPY | 155.70 |
| KRW | 1,442.00 |
| BRL | 5.17 |
| ZAR | 15.97 |
| TRY | 43.86 |

### 2.4 FX Volatilities

Nine currencies are tracked, each with a calibrated annual volatility used as σ in Monte Carlo GBM simulations:

| Currency | Annual Volatility |
|----------|-------------------|
| EUR | 8% |
| GBP | 10% |
| CNY | 6% |
| NGN | 40% |
| JPY | 12% |
| KRW | 10% |
| BRL | 18% |
| ZAR | 15% |
| TRY | 35% |

### 2.5 MCDA Weights

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

Users can adjust these interactively on the Supplier Scorecards page. The sliders auto-normalise so they always sum to 1.0.

### 2.6 Risk Weights

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

### 2.7 Other Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `MC_DEFAULT_PATHS` | 10,000 | Monte Carlo default simulation count |
| `MC_MAX_PATHS` | 100,000 | Upper bound for simulations |
| `MC_DEFAULT_HORIZON_DAYS` | 90 | Default forecast window (trading days) |
| `MC_MAX_HORIZON_DAYS` | 365 | Maximum forecast horizon |
| `EMISSION_FACTORS` | Sea 0.016, Air 0.602, Rail 0.028, Road 0.062 | kgCO₂e per tonne-km (DEFRA 2025) |
| `COST_LEAKAGE_INVESTIGATE_PCT` | 5% | Should-cost leakage threshold (yellow) |
| `COST_LEAKAGE_ESCALATE_PCT` | 15% | Leakage threshold (orange) |
| `COST_LEAKAGE_RED_FLAG_PCT` | 25% | Leakage threshold (red) |
| `HHI_COMPETITIVE` | 1,500 | HHI threshold for "Low" concentration |
| `HHI_MODERATE` | 2,500 | HHI threshold for "Moderate" |
| `HHI_CONCENTRATED` | 5,000 | HHI threshold for "High" |
| `RANDOM_SEED` | 42 | Reproducible data generation |
| `ENABLE_LIVE_FX` | false (default) | Toggle live FX fetching in the dashboard |
| `DEMO_MODE` | true (default) | Demo/production mode flag |

---

## 3. Database Schema

The schema is split into 10 SQL files executed in numeric order. Together they create **40+ tables** across **8 logical layers**.

### 3.1 Reference Tables (01)

Nine lookup tables that rarely change after initial setup.

| Table | Rows | Description |
|-------|------|-------------|
| `countries` | 15 | ISO code, region, income group, WGI governance score, CPI corruption index, sanctions flag, grid emission factor |
| `currencies` | 10 | Currency code/name, major flag, volatility class (Low / Medium / High / Very High) |
| `industry_sectors` | 6 | ISIC-aligned sectors with risk profile classification |
| `ports` | 12 | Global ports with lat/long coordinates and congestion risk scores |
| `incoterms` | 7 | ICC 2020 trade terms with buyer-bears-freight and buyer-bears-insurance flags |
| `compliance_frameworks` | 6 | UK Modern Slavery Act, EU CSRD, OECD DD, Nigerian NCDMB, US Dodd-Frank §1502, ISO 20400 |
| `certifications_catalog` | 10 | ISO 9001/14001/45001/27001, SA8000, OHSAS, API Q1, ASME, CE, LEED |
| `risk_categories` | 7 | The 7 risk dimensions with default weights |
| `emission_factors` | 4 | Transport mode emission factors per GHG Protocol |

### 3.2 Master Data Tables (02)

Five tables representing the core business entities.

| Table | Description |
|-------|-------------|
| `suppliers` | 50 suppliers across 15 countries. Fields: tier level (Strategic → Blocked), annual revenue, lead times, defect rate, ISO cert flags, payment terms, status |
| `supplier_certifications` | Many-to-many link between suppliers and the certifications catalog with issue/expiry dates |
| `materials` | 80 industrial materials with HS codes, commodity groups, standard costs, and criticality flags |
| `supplier_material_catalog` | Which suppliers can provide which materials at what price and lead time |
| `contracts` | 40 contracts (Fixed Price, Cost Plus, Framework, Spot, Blanket) with FX clauses and EPD terms |

### 3.3 Transaction Tables (03)

Seven tables capturing operational activity.

| Table | Volume | Description |
|-------|--------|-------------|
| `purchase_orders` | ~2,000 | PO header with supplier, contract, dates, amounts, maverick flag, status |
| `po_line_items` | ~6,000 | One row per material ordered: quantity, unit price, line total, USD value |
| `shipments` | ~1,800 | Transport mode, carrier, origin/destination port, ETA vs. actual arrival, delay days |
| `shipment_milestones` | varies | 9 milestone types from "Order Placed" through "Exception" |
| `quality_inspections` | ~1,500 | Sample size, defects found, computed defect rate, pass/fail/conditional result |
| `quality_incidents` | ~120 | Severity (Minor / Major / Critical), category, CAPA status, financial impact |
| `invoices` | ~2,000 | Amount, due date, paid date, days-to-pay, EPD taken flag, status |

### 3.4 Market Data Tables (04)

| Table | Volume | Description |
|-------|--------|-------------|
| `fx_rates` | ~7,000 | Daily exchange rates per currency (2022–2025), generated via GBM |
| `commodity_prices` | ~2,000 | Weekly prices for 8 commodity groups (HRC Steel, Copper, Brent, Nickel, Aluminium, etc.) |
| `country_risk_indices` | 60 | Annual political stability, regulatory quality, rule of law, logistics performance per country |

### 3.5 ESG and Compliance Tables (05)

| Table | Volume | Description |
|-------|--------|-------------|
| `esg_assessments` | 100 | Environmental (carbon/waste/water), Social (labour/H&S), Governance (ethics/transparency/board diversity), overall score, A–F rating |
| `compliance_checks` | varies | Status per supplier per framework (Compliant, Partially Compliant, Non-Compliant) with remediation plans |
| `carbon_estimates` | ~1,800 | Per-shipment CO₂e: transport mode, distance, weight, emission factor, resulting kgCO₂e |
| `due_diligence_records` | varies | OECD 6-step due diligence status (Policy, Identify, Mitigate, Verify, Communicate, Remediate) |

### 3.6 Warehouse — Star Schema (06)

Four dimension tables and two fact tables, designed for analytical queries and Power BI consumption.

**Dimensions:**

| Table | Type | Key Fields |
|-------|------|------------|
| `dim_date` | Calendar | Year, quarter, month, week, day-of-week, is_weekend, fiscal year/quarter (April start) |
| `dim_supplier` | SCD Type 2 | Supplier attributes plus `scd_valid_from`, `scd_valid_to`, `scd_is_current` for historical tracking |
| `dim_material` | Standard | Category, commodity group, standard cost, criticality |
| `dim_geography` | Standard | Country, region, income group, sanctions flag |

**Facts:**

| Table | Grain | Key Measures |
|-------|-------|--------------|
| `fact_procurement` | One PO line item | quantity, unit_price_usd, line_total_usd, landed_cost_usd, fx_rate_applied, cost_variance_pct, lead_time_days, delay_days, on_time_flag, defect_flag, is_maverick, co2e_kg |
| `fact_esg` | One ESG assessment | env/social/governance sub-scores, overall score, rating, compliance gap count |

### 3.7 Analytics Output Tables (07)

| Table | Description |
|-------|-------------|
| `supplier_scorecards` | MCDA output: 7 dimension scores, 7 weights, composite score, rank, tier, methodology used |
| `risk_assessments` | 7 risk dimension scores, composite risk, risk tier per supplier |
| `simulation_runs` | Monte Carlo results: scenario type, paths, distribution stats (mean/median/std/P5–P95), VaR, CVaR, input params stored as JSON |
| `concentration_analysis` | HHI per dimension: spend shares, index value, category, text recommendations |

### 3.8 Audit Tables (08)

| Table | Description |
|-------|-------------|
| `audit_log` | Row-level change tracking: table, record ID, action (INSERT/UPDATE/DELETE), old/new values as JSON, changed_by, timestamp |
| `data_quality_log` | DQ check results: check name/type, table/column, records checked/failed, computed failure %, severity |
| `pipeline_runs` | Auto-created by `utils/freshness.py` — stores run_id, start/finish timestamps, status, duration, steps run |

---

## 4. Data Ingestion

### 4.1 Seed Data Generator (`generate_seed_data.py`)

A 14-step data generator (1,000+ lines) that populates all master and transactional tables with realistic, internally consistent data. It runs inside a single database transaction so that either everything succeeds or nothing changes.

**Steps and what they produce:**

| Step | Function | Output |
|------|----------|--------|
| 1 | `seed_suppliers` | 50 suppliers across 15 countries with weighted tier distribution (10% Strategic, 25% Preferred, 40% Approved, 20% Conditional, 5% Blocked) |
| 2 | `seed_materials` | 80 industrial materials spanning 20+ commodity groups (Ferrous Metals, Flow Control, Instrumentation, Rotating Equipment, Wellhead, Subsea, Drilling, etc.) |
| 3 | `seed_catalog` | ~200 supplier-material catalog entries, priced at 75%–135% of standard cost |
| 4 | `seed_contracts` | 40 contracts (Fixed Price, Cost Plus, Framework, Spot, Blanket) with randomised FX clauses and EPD percentages |
| 5 | `seed_purchase_orders` | 2,000 POs with weighted statuses (60% Delivered, 12% Closed, 5% Cancelled) and ~6,000 line items |
| 6 | `seed_shipments` | 1,800 shipments with mode weights (55% Sea, 20% Air, 15% Road, 10% Rail). Delay drawn from Normal(2, 5) |
| 7 | `seed_quality` | 1,500 quality inspections (defect rate from Normal(3, 4)) and 120 incidents (50% Minor, 35% Major, 15% Critical) |
| 8 | `seed_invoices` | ~2,000 invoices (85% paid, 25% with EPD taken). Days-to-pay varies −10 to +30 days relative to due date |
| 9 | `seed_fx_rates` | Daily FX rates for 9 currencies (2022–2025) generated via GBM, re-scaled so the final value matches the anchor rate in config |
| 10 | `seed_commodity_prices` | Weekly prices for 8 commodities via GBM with 20% annual volatility |
| 11 | `seed_country_risk` | 15 countries × 4 years = 60 annual risk index records |
| 12 | `seed_esg` | 100 ESG assessments (50 suppliers × 2 years). Overall = 35% Environmental + 35% Social + 30% Governance |
| 13 | `seed_carbon` | 1,800 carbon estimates using GLEC Framework emission factors |
| 14 | `seed_certifications` / `seed_compliance` | ~150 certification links and compliance/due diligence records |

All randomness uses `config.RANDOM_SEED = 42` so that results are reproducible across runs.

### 4.2 External Data Loader (`external_data_loader.py`)

An alternative to the seed generator for importing real company data from CSV files.

**Two-phase process:**

**Phase 1 — Validation** (`load_all_files`):
- Scans an input directory for 4 required files (`suppliers.csv`, `materials.csv`, `purchase_orders.csv`, `po_line_items.csv`) and 3 optional files (`shipments.csv`, `invoices.csv`, `esg_assessments.csv`)
- Validates each file against a schema definition (required columns, numeric fields, value ranges)
- Per-file rules: lead_time > 0, standard_cost ≥ 0, valid transport modes, valid ESG ratings
- Logs detailed error and warning messages before aborting on failure

**Phase 2 — Import** (`import_data`):
- Clears 30 tables in reverse-FK order
- Inserts data in FK order, resolving foreign keys via lookup helpers (country name → country_id, currency code → currency_id, etc.)
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
2. `api.exchangerate-api.com` (secondary)
3. `api.frankfurter.dev` (tertiary)

Each attempt has an 8-second timeout. Only currencies present in `config.FX_VOLATILITIES` are kept.

When successful, today's rates are upserted into `fx_rates` using `ON DUPLICATE KEY UPDATE`. The fetcher is called from the pipeline and is also available as a manual refresh button on the Settings page.

---

## 5. Warehouse ETL

`populate_warehouse.py` transforms the OLTP tables into a star schema suitable for analytical queries and Power BI.

### ETL Steps

| Step | Function | What It Does |
|------|----------|--------------|
| 1 | `populate_dim_date` | Generates a calendar dimension from 2022-01-01 to 2028-12-31. Includes year, quarter, month, week, day-of-week, is_weekend, and fiscal year/quarter (April start). Date key is an integer in YYYYMMDD format |
| 2 | `populate_dim_supplier` | SCD Type 2 initial load. Joins `suppliers` with `countries`, `industry_sectors`, `currencies`, latest ESG rating, and latest risk tier. Sets `scd_is_current = TRUE` |
| 3 | `populate_dim_material` | Copies from `materials` into `dim_material` |
| 4 | `populate_dim_geography` | Copies from `countries` into `dim_geography` |
| 5 | `populate_fact_procurement` | Grain = one PO line item. Joins through purchase_orders, suppliers, materials, shipments, quality inspections, carbon estimates, and FX rates. Populates 20 measures including landed cost, cost variance, lead time, delay, on-time flag, defect flag, and CO₂e |
| 6 | `populate_fact_esg` | Grain = one ESG assessment. Joins to dim_supplier and adds compliance gap count |

The ETL uses a **full-refresh pattern** (DELETE then INSERT) within a single transaction. This keeps the logic simple and makes every run idempotent.

---

## 6. Analytics Engines

Eight independent engines, each reading from the database and writing results back. They can run standalone or as part of the pipeline.

### 6.1 MCDA Engine (`mcda_engine.py`)

Multi-criteria decision analysis for supplier ranking. 333 lines.

**Decision matrix construction** (`build_decision_matrix`): a complex SQL query joining 7 tables (suppliers, PO line items, shipments, quality inspections, ESG assessments, risk assessments, supplier certifications) to produce 7 criteria per supplier:
- **Cost** — weighted average unit price across all PO line items
- **Quality** — average defect rate from quality inspections
- **Delivery** — on-time delivery percentage from shipments
- **Risk** — composite risk score from risk_assessments
- **ESG** — overall ESG score
- **Innovation** — certification count as a proxy
- **Financial Health** — supplier annual revenue (log-scaled)

**Three scoring methods:**

**TOPSIS** (Technique for Order of Preference by Similarity to Ideal Solution):
1. Build a decision matrix from 7 criteria per supplier
2. Vector-normalise each column: $r_{ij} = x_{ij} / \sqrt{\sum_k x_{kj}^2}$
3. Multiply by weights: $v_{ij} = w_j \cdot r_{ij}$
4. Identify the ideal best ($A^+$) and ideal worst ($A^-$) vectors
5. Compute Euclidean distance from each supplier to both
6. Closeness coefficient: $C_i = D_i^- / (D_i^+ + D_i^-)$

**PROMETHEE-II** (Preference Ranking Organization Method for Enrichment Evaluation):
- Uses a linear preference function with indifference threshold $q$ and strict preference threshold $p$
- Computes pairwise preference indices $\pi(a_i, a_j)$
- Positive flow $\phi^+$, negative flow $\phi^-$, net flow $\phi = \phi^+ - \phi^-$

**WSM** (Weighted Sum Model):
- Min-max normalise each column to [0, 1]
- Dot product with weight vector: $S_i = \sum_j w_j \cdot \hat{x}_{ij}$

After scoring, results are scaled to 0–100 and suppliers are assigned to tiers:

| Score | Tier |
|-------|------|
| ≥ 80 | Strategic |
| ≥ 65 | Preferred |
| ≥ 50 | Approved |
| ≥ 35 | Conditional |
| < 35 | Blocked |

Results are written to `supplier_scorecards` using SQLAlchemy bulk insert.

### 6.2 Risk Scoring (`risk_scoring.py`)

Computes a 7-dimension composite risk score for each supplier. 209 lines.

**Data acquisition** (`compute_risk_scores`): a single SQL query with 7 LEFT JOINs aggregating data from suppliers, purchase orders, shipments, quality inspections, quality incidents, compliance checks, ESG assessments, and countries.

**Risk dimensions (all normalised to 0–100, higher = riskier):**

| Dimension | Calculation |
|-----------|-------------|
| Financial | Based on supplier revenue. Lower revenue = higher risk |
| Operational | Weighted sum of defect rate, on-time delivery shortfall, and incident count |
| Geopolitical | Weighted sum of WGI governance gap, Fragile States Index, and sanctions flag |
| Compliance | Based on non-compliant check count and certification gap |
| Concentration | Mapped from supplier tier level (Strategic = 15, Blocked = 90) |
| ESG | Inverse of ESG overall score |
| Cyber | Based on currency volatility, governance gap, and certification count |

**Composite risk** is the weighted sum using `config.RISK_WEIGHTS`. The result is classified into tiers via `pd.cut`:

| Score | Tier |
|-------|------|
| < 30 | Low |
| < 55 | Medium |
| < 75 | High |
| ≥ 75 | Critical |

Results are written to `risk_assessments` using `persist_risk_assessments()`.

### 6.3 Monte Carlo Simulations (`monte_carlo.py`)

Four types of stochastic simulation. 315 lines.

**FX Risk (Geometric Brownian Motion):**

$$S_{t+1} = S_t \cdot \exp\!\left(\left(-\tfrac{1}{2}\sigma^2\right)\Delta t + \sigma\sqrt{\Delta t} \cdot Z\right)$$

where $Z \sim N(0,1)$. Default: 10,000 paths (configurable up to 100,000) over 90 trading days (configurable up to 365). Reports P5, P25, P50, P75, P95, VaR(95%), and CVaR(95%).

**Lead-Time Risk:**
- Queries historical shipment lead times from the `shipments` table
- Fits a log-normal distribution: computes $\mu$ and $\sigma$ of $\ln(\text{lead\_time})$
- Generates random samples from that distribution
- Falls back to a preset array if fewer than 5 historical data points exist

**Disruption Risk:**
- Four preset scenarios: port closure, supplier failure, sanctions, natural disaster
- Each has a cost multiplier (drawn from Normal distribution) and a lead-time addition (days)
- Multiplies baseline annual spend by the sampled cost multiplier
- Returns distribution of total cost impact

**Combined Cost Scenario:**
- Simulates FX movements per currency (GBM, 90 days) and commodity price shocks (Normal, mean=1, std=0.10, floor at 0.7)
- Multiplies baseline spend by combined FX and commodity factors
- Returns full cost distribution with savings-at-risk

All simulation results are persisted to `simulation_runs` with JSON-serialised input parameters via `save_simulation()`.

### 6.4 Concentration Analysis (`concentration.py`)

Herfindahl-Hirschman Index across 5 dimensions. 215 lines.

$$HHI = \sum_{i=1}^{N} s_i^2$$

where $s_i$ is spend share as a percentage. Computed separately for:

| Dimension | SQL Group-By | Measures |
|-----------|-------------|----------|
| Supplier | `supplier_name` | Total spend, share %, HHI |
| Country | `country_name` | Total spend, share %, HHI |
| Currency | `currency_code` | Total spend, share %, HHI |
| Material | `commodity_group` | Total spend, share %, HHI |
| Port | `port_name` | Total spend, share %, HHI |

**HHI classification:**

| HHI | Category |
|-----|----------|
| < 1,500 | Low (competitive) |
| < 2,500 | Moderate |
| ≥ 2,500 | High (concentrated) |

For each dimension, the engine computes top-3 concentration share and generates text recommendations for any entity holding > 25% or > 40% of spend. Results are written to `concentration_analysis` in batches of 100 via `persist_concentration()`.

### 6.5 Carbon Engine (`carbon_engine.py`)

GHG Protocol Scope 3 Category 4 (upstream transport) emissions. ~200 lines.

$$\text{CO}_2\text{e (kg)} = \text{weight (tonnes)} \times \text{distance (km)} \times \text{EF}$$

- **Emission factors (EF)** come from DEFRA 2025: Sea 0.016, Air 0.602, Rail 0.028, Road 0.062 kgCO₂e/tonne-km
- **Distance** is computed using the Haversine formula between origin and destination port coordinates:

$$d = 2R \cdot \arcsin\!\sqrt{\sin^2\!\left(\tfrac{\Delta\phi}{2}\right) + \cos\phi_1 \cos\phi_2 \sin^2\!\left(\tfrac{\Delta\lambda}{2}\right)}$$

where $R = 6{,}371$ km (Earth's mean radius).

- **Mode-shift analysis** (`get_reduction_opportunities`): filters air shipments and calculates CO₂e savings from switching to sea or rail
- **Carbon intensity**: kgCO₂e per $1,000 freight value

### 6.6 Should-Cost Model (`should_cost.py`)

Bottom-up cost estimation and leakage detection per material-supplier combination. ~200 lines.

**Five cost components:**

| Component | Calculation |
|-----------|-------------|
| Material cost | `standard_cost_usd` from materials table |
| Freight | Region-based % of material cost (Africa 12%, Europe 5%, Asia 8%, Americas 7%, Middle East 6%) |
| Customs/duties | Region-based (Africa 10%, Asia 7%, else 3%) |
| Overhead | Fixed 5% of material cost |
| Supplier margin | Assumed 12% |

**Should-cost total** = sum of all five components. **Variance** = quoted price − should-cost (both absolute and as a percentage).

**Leakage classification:**

| Variance | Flag |
|----------|------|
| < 5% | Within Range |
| 5–15% | Investigate |
| 15–25% | Escalate |
| ≥ 25% | Red Flag |

The leakage summary (`get_leakage_summary`) reports total quoted vs. should-cost, total leakage in dollars and percent, and the top 10 overpriced items.

### 6.7 Working Capital (`working_capital.py`)

DPO analysis, invoice aging, and early payment discount optimisation. ~200 lines.

**`analyze_working_capital`** runs three SQL queries:
1. **Aging by supplier** — invoice count, total amount, average days-to-pay, overdue amount, EPD captured/missed
2. **Monthly DPO trend** — average DPO, total spend, overdue count
3. **EPD analysis** by payment terms bucket — volume, discount captured value, average early payment timing

**`optimize_payment_timing`** implements a **greedy knapsack algorithm** for EPD:
1. Query pending invoices that have an EPD percentage
2. Compute annualised return for each: $(EPD\% / 100) \times (365 / \text{days\_early})$
3. Filter invoices where the annualised return exceeds the cost of capital (default 8%)
4. Sort by annualised return descending
5. Greedily select highest-return invoices until the budget constraint (default $500K) is exhausted

Returns: selected invoices, total discount captured, total capital deployed, blended annualised return.

### 6.8 Scenario Planner (`scenario_planner.py`)

Three what-if scenarios. 232 lines.

**Supplier Switch** (`scenario_supplier_switch`):
- Compares two suppliers on cost, lead-time, quality, and ESG
- Queries each supplier's PO history, catalog pricing, delay stats, defect rate, and latest ESG score
- Returns estimated spend change (%), delay change (days), quality delta, and ESG delta

**Currency Hedge** (`scenario_currency_hedge`):
- Models hedging a percentage (default 80%) of currency exposure at a forward rate (default 2% premium)
- Calls `monte_carlo.simulate_fx` internally (5,000 paths, 90 days)
- Compares unhedged mean/P95 cost vs. hedged cost (fixed-rate portion + simulated remainder)
- Returns savings at P95 and hedge premium cost

**Nearshoring** (`scenario_nearshoring`):
- Models reallocating a percentage (default 30%) of spend to a target region
- Assumptions: 5% higher unit cost, 40% lower freight, 30% faster delivery
- Returns net cost impact, freight savings, lead-time improvement, and carbon reduction estimate

---

## 7. Streamlit Dashboard

The dashboard is a **12-page Streamlit multipage app**. Every page is protected by a login gate (`utils/auth.py`) and shows a data freshness badge in the sidebar. Pages are emoji-prefixed for Streamlit's sidebar ordering.

### 7.1 Entry Point (`streamlit_app.py`)

- Sets page config (wide layout, AEGIS branding, 🛡️ icon)
- Runs `login_gate()` before rendering — stops execution if authentication fails
- Injects custom CSS: metric card styling, dark sidebar gradient (`#1a1a2e` → `#16213e`), heading colours
- Sidebar: placeholder logo, data freshness badge (cached 120 s), version label (v1.0.0), logout button
- **Landing page content:**
  - 6 KPIs from a single SQL query (cached 5 min via `@st.cache_data(ttl=300)`): Active Suppliers, Purchase Orders, Total Spend, Countries, Shipments, Materials
  - Graceful degradation: if the database is unreachable, shows a warning with connection hints for both local and Streamlit Cloud setups
  - Navigation cards with descriptions linking to all 12 analytics modules

### 7.2 Page-by-Page Overview

**Page 1 — 📈 Executive Dashboard**
- Year selector in sidebar (default: **2025**)
- 6 KPIs: Total Spend, Active Suppliers, On-Time %, Defect Rate %, Maverick Spend %, Overdue Invoices
- Monthly spend trend (line chart)
- Spend by region (donut chart)
- Supplier tier distribution (bar chart)
- Active quality incident alerts table

**Page 2 — 🏆 Supplier Scorecards**
- Sidebar controls: methodology selector (TOPSIS / PROMETHEE-II / WSM), year filter, 7 weight sliders with **auto-normalisation** (adjusting one slider proportionally redistributes the others to maintain sum = 1.0)
- "Run MCDA" button triggers real-time re-computation via `mcda_engine.run_mcda()`
- Ranked supplier table with gradient-coloured score cells
- Tier distribution pie chart
- Radar chart for the top-ranked supplier across all 7 dimensions
- Composite score histogram coloured by tier

**Page 3 — ⚡ Risk Radar**
- Risk heatmap showing top 20 suppliers across 7 risk dimensions
- KPIs: suppliers assessed, average risk score, Critical/High counts
- Risk tier distribution pie chart
- Average risk by region horizontal bar chart
- Single-supplier radar drill-down (select a supplier from a dropdown to see its 7-dimension radar)

**Page 4 — 🎲 Monte Carlo Lab**
- 4 tabs, each with a "Run Simulation" button:
  - **FX Risk:** Select currency, paths (1K–100K slider), horizon (30–365 days), optional volatility override. Shows current rate, simulated mean, P95, VaR(95%), CVaR(95%). Histogram with **P5, P50, P95 vertical markers**
  - **Lead Time:** Select simulation count and optional supplier filter. Shows historical mean, simulated mean, P95, standard deviation. Histogram with P5/P50/P95 markers
  - **Disruption:** Select scenario type (port closure / supplier failure / sanctions / natural disaster), affected entity, duration. Shows baseline spend, cost impact (mean/P95), lead-time addition, CVaR
  - **Total Cost:** Combined FX + commodity simulation. Shows baseline/mean/P95 cost, VaR. Histogram with P5/P50/P95 markers

**Page 5 — 🔎 Concentration Analysis**
- Year selector in sidebar (default: **2025**)
- KPI row with HHI score and top entity per dimension — colour-coded green (< 1,500) / yellow (< 2,500) / red (≥ 2,500)
- HHI bar chart with horizontal threshold lines at 1,500 and 2,500
- 4 spend distribution tabs: By Supplier (treemap), By Country (pie), By Currency (pie), By Material (treemap by commodity group)

**Page 6 — 🌍 Carbon Dashboard**
- 3 KPIs: total estimates, total CO₂e in tonnes, average carbon intensity per $1K
- Emissions by transport mode (bar + pie charts)
- Top 15 emitting suppliers (horizontal bar coloured by intensity)
- Top 15 emitting routes (horizontal bar coloured by mode)
- Mode-shift reduction opportunities table with total potential savings in tonnes

**Page 7 — 💲 Should-Cost**
- Year selector in sidebar (default: **2025**)
- 5 KPIs: items analysed, total quoted, total should-cost, total leakage (USD), leakage percentage
- Leakage classification distribution (bar + pie): Within Range / Investigate / Escalate / Red Flag
- Waterfall chart decomposing the highest-leakage item into its 5 cost components vs. quoted price
- Detailed leakage table filterable by flag severity

**Page 8 — 🏦 Working Capital**
- 3 tabs:
  - **Overview** — DPO trend over time (line chart), summary metrics (total spend, overdue amount, discount captured vs. missed)
  - **Invoice Aging** — grouped/stacked bar chart by supplier showing current, 30-day, 60-day, 90+ day buckets
  - **Early Payment Discount** — interactive budget slider ($100K–$2M) and cost-of-capital input (%). Shows prioritised invoice list sorted by annualised return, total savings, capital deployed

**Page 9 — 🌱 ESG Compliance**
- 3 tabs:
  - **ESG Ratings** — EcoVadis-style overall and sub-score display with scatter plot and single-supplier radar drill-down
  - **Compliance** — Framework pass/fail summary per supplier with colour-coded status (Compliant / Partial / Non-Compliant)
  - **OECD Due Diligence** — 6-step progress tracker per supplier (Policy, Identify, Mitigate, Verify, Communicate, Remediate)

**Page 10 — 🔮 Scenario Planner**
- 3 tabs:
  - **Supplier Switch** — pick two suppliers, compare on cost/lead-time/quality/ESG with before/after radar chart
  - **Currency Hedge** — pick currency, hedge percentage, forward premium. Shows unhedged vs. hedged cost, P95 savings
  - **Nearshoring** — pick target region, reallocation %. Shows net cost impact, freight savings, lead-time improvement

**Page 11 — 🗄 Data Explorer**
- 3 tabs:
  - **Table Browser** — dropdown to select any of the 40+ tables, shows row count, column schema (name, type, nullable), and first N rows
  - **Ad-Hoc SQL** — text area for custom queries with a **safety-validation regex** that blocks DROP, ALTER, TRUNCATE, and other DDL statements. Results displayed as a table with CSV download
  - **Executive Export** — one-click multi-sheet Excel download with 5 sheets: Supplier Scorecards, Risk Assessments, Concentration, Spend Summary, Carbon Emissions

**Page 12 — ⚙️ Settings**
- 5 tabs:
  - **MCDA Weights** — view/modify the 7 AHP criteria weights
  - **Risk Config** — view/modify HHI thresholds, leakage thresholds, risk weights
  - **FX Config** — view current anchor rates, live fetch button (calls `_fetch_live_fx()`), toggle live FX
  - **CSV Import** — drag-and-drop CSV upload for ad-hoc data loading
  - **System** — pipeline run history, database connection info, Streamlit/Python version

### 7.3 Authentication (`utils/auth.py`)

HMAC-SHA-256 login gate controlled entirely via environment variables:

| Variable | Purpose |
|----------|---------|
| `AEGIS_DASHBOARD_USER` | Expected username |
| `AEGIS_DASHBOARD_PASS_HASH` | SHA-256 hex digest of the expected password |

**Behaviour:**
- If **both** env vars are set: a centred login form is displayed with username/password fields. Passwords are hashed with SHA-256 and compared using `hmac.compare_digest()` (constant-time comparison to prevent timing attacks).
- If **either** env var is missing: authentication is bypassed — the dashboard is publicly accessible. This is the default development experience.
- Session state (`st.session_state["authenticated"]`) persists the login across page navigations. A sidebar logout button clears the state and forces re-login.

### 7.4 Database Connection (`utils/db.py`)

- `get_engine()` — returns a SQLAlchemy 2.x engine, **cached once per Streamlit session** via `@st.cache_resource`. Configured with `pool_pre_ping=True` (stale connection detection), `pool_recycle=300` (5-min recycling), and a 5-second connect timeout.
- `check_connection(engine)` — runs `SELECT 1` and returns True/False.
- `show_connection_error()` — renders a standardised error banner with connection hints for both local and cloud, masking the password in the displayed URL.

Every page imports `get_engine()` from this module to get a shared, cached database engine.

---

## 8. Utilities

### 8.1 Logging (`utils/logging_config.py`)

- `get_logger(name)` returns a logger under the `aegis.*` namespace with two handlers:
  - **File handler:** writes to `logs/aegis_pipeline.log` at DEBUG level
  - **Console handler:** writes to stdout at INFO level
- Log directory is auto-created on import.

**`AuditLogger`** — writes row-level change events to the `audit_log` table (table name, record ID, action INSERT/UPDATE/DELETE, old/new values as JSON, changed_by). Uses `_get_connection()` for a raw pymysql connection (with SSL support).

**`DataQualityLogger`** — writes DQ check results to `data_quality_log` (check name/type, table_name, column_name, records checked/failed, severity, details). Used by the pipeline verifier after every run.

### 8.2 Export (`utils/export.py`)

- `to_excel_bytes(dataframes)` — takes a dict of `{sheet_name: DataFrame}` and returns openpyxl bytes. Sheet names are truncated to 31 characters (Excel limit).
- `to_csv_bytes(df)` — returns UTF-8 CSV bytes
- `generate_executive_summary(engine)` — queries 5 sheets of data (Supplier Scorecards, Risk Assessments, Concentration, Spend Summary, Carbon Emissions) for a one-click executive export from the Data Explorer page

### 8.3 Freshness Tracking (`utils/freshness.py`)

- `record_start()` — creates a `pipeline_runs` row (auto-creates table if missing) with status `"running"`. Returns a `run_id`
- `record_finish(run_id, status, duration)` — updates that row with finish time, status (`"success"` / `"failed"`), and elapsed seconds
- `get_last_run()` — returns the most recent successful run record
- `freshness_badge()` — computes the age of the last successful run and returns an emoji string:
  - 🟢 Fresh (< 1 hour)
  - 🟡 Stale (< 24 hours)
  - 🔴 Very stale (> 24 hours)
  - ⚠️ No pipeline run recorded

The badge is shown in the Streamlit sidebar on every page load (cached for 120 seconds).

---

## 9. Testing

**49 tests** across 2 files and 16 test classes. Tests are designed to run **without a database connection** by testing pure logic (maths, config validation, imports, module structure).

### `tests/test_aegis.py` (24 tests)

| Class | Tests | What It Covers |
|-------|-------|----------------|
| `TestConfig` (6) | `test_database_url_set`, `test_fx_volatilities_valid`, `test_risk_weights_sum_to_one`, `test_mcda_weights_sum_to_one`, `test_hhi_thresholds_ordered`, `test_emission_factors_positive` | Validates all config parameters are well-formed and consistent |
| `TestMCDAEngine` (5) | `test_topsis_returns_correct_shape`, `test_topsis_best_alternative`, `test_promethee_returns_correct_shape`, `test_wsm_returns_correct_shape`, `test_tier_from_score` | Pure-math MCDA scoring on synthetic matrices |
| `TestMonteCarlo` (3) | `test_simulate_fx_returns_dict`, `test_simulate_fx_gbm_positive`, `test_simulate_fx_var_positive` | GBM output shape, positivity, VaR sanity |
| `TestRiskScoring` (1) | `test_risk_tier_mapping` | Tier boundary classification |
| `TestConcentration` (4) | `test_compute_hhi_uniform`, `test_compute_hhi_monopoly`, `test_compute_hhi_equal_ten`, `test_categorize_hhi` | HHI maths and classification |
| `TestCarbonEngine` (3) | `test_haversine`, `test_haversine_same_point`, `test_emission_factors_exist` | Haversine formula accuracy and factor presence |
| `TestShouldCost` (1) | `test_leakage_flags` | Leakage threshold classification |
| `TestWorkingCapital` (1) | `test_epd_annualized_return` | EPD return formula |

### `tests/test_extended.py` (25 tests)

| Class | Tests | What It Covers |
|-------|-------|----------------|
| `TestAuth` (4) | `test_default_password_hash`, `test_check_password_correct`, `test_check_password_wrong`, `test_default_username` | SHA-256 login mechanism |
| `TestLoggingConfig` (5) | `test_get_logger_returns_logger`, `test_logger_has_handlers`, `test_log_dir_exists`, `test_data_quality_logger_instantiates`, `test_audit_logger_instantiates` | Logger setup and handler attachment |
| `TestExternalDataLoader` (4) | `test_loader_detects_csv_files`, `test_loader_validates_columns`, `test_loader_empty_dir`, `test_loader_invalid_csv` | CSV validation and error handling |
| `TestScenarioPlannerMath` (2) | `test_hedge_savings_formula`, `test_nearshoring_cost_premium` | Hedge and nearshoring maths |
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

`.github/workflows/ci.yml` defines **three jobs** that run on every push to `main` / `develop` and on pull requests to `main`.

### Job 1: `test`

1. Starts a **MySQL 8.0** service container with a health check (`mysqladmin ping`, 10 s interval, 10 retries)
2. Installs Python 3.11 and project dependencies (`requirements.txt` + `requirements-dev.txt`)
3. Waits for MySQL using an inline Python script that retries `pymysql.connect()` up to 60 times (2 s apart), then runs `CREATE DATABASE IF NOT EXISTS aegis_procurement`
4. Runs `pytest tests/ -v --tb=short` with `DATABASE_URL` pointing to the CI MySQL service

### Job 2: `lint`

1. Runs `black --check --diff .` — **non-blocking** (prints a `::warning` if formatting differs, does not fail the build)
2. Runs `flake8 --max-line-length=120` with an extended ignore list for cosmetic codes (E501, W503, W504, E402, F401, etc.), excluding `__pycache__`, `.venv`, and `logs`

### Job 3: `docker`

1. Only runs on **`main` branch** pushes, _after_ the `test` job passes (`needs: test`)
2. **Builds** the Docker image from the Dockerfile
3. **Smoke-tests** the image:
   ```bash
   docker run --rm -e AEGIS_FX_OFFLINE=1 aegis-procurement python -c "import config; print('OK')"
   ```
   The `AEGIS_FX_OFFLINE=1` environment variable prevents `_fetch_live_fx()` from making HTTP requests inside the container, which would fail without network access and cause a build failure.

---

## 11. Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENV PYTHONUNBUFFERED=1

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true"]
```

### docker-compose.yml

Two services:

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `mysql` | mysql:8.0 | 3307 (host) → 3306 (container) | SQL files in `database/` are auto-executed via Docker's init directory. Persistent volume `aegis-mysql-data` |
| `app` | Built from Dockerfile | 8501 | `depends_on: mysql (service_healthy)`. `DATABASE_URL` set to point at the `mysql` container. `restart: unless-stopped` |

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

Environment variables `DB_PASSWORD` and `DB_NAME` can be set in a `.env` file alongside `docker-compose.yml`.

### Environment Variables Reference

| Variable | Default | Used By |
|----------|---------|---------|
| `DATABASE_URL` | (built from DB_* vars) | All modules |
| `DB_HOST` | `localhost` | config.py |
| `DB_PORT` | `3306` | config.py |
| `DB_USER` | `root` | config.py |
| `DB_PASSWORD` | (empty) | config.py |
| `DB_NAME` | `aegis_procurement` | config.py |
| `DB_SSL` | `false` | config.py |
| `AEGIS_FX_OFFLINE` | (unset) | config.py — skips live FX fetch |
| `AEGIS_DASHBOARD_USER` | (unset) | utils/auth.py — auth bypassed if unset |
| `AEGIS_DASHBOARD_PASS_HASH` | (unset) | utils/auth.py — SHA-256 hex of password |
| `ENABLE_LIVE_FX` | `false` | config.py |
| `DEMO_MODE` | `true` | config.py |
| `AEGIS_DEBUG` | `false` | streamlit_app.py — shows raw error text |

---

## 12. Power BI Layer

The `powerbi/` directory contains everything needed to build a Power BI executive dashboard on top of the same MySQL database.

| File | Description |
|------|-------------|
| `AEGIS_Dashboard_BUILD.md` | 10-page step-by-step build guide with visual layout instructions |
| `AEGIS_Theme.json` | Custom colour theme (Tableau-10 palette adapted for AEGIS) |
| `DAX_Measures.md` | 25+ DAX measure definitions: Total Spend, YoY Growth, OTD %, Defect Rate, Risk Score avg, HHI, CO₂ Intensity, Working Capital metrics |
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

### Step 1/6 — Deploy Database Schema

```
[pipeline]  Step 1/6 — Deploy Database Schema
```

- Opens a raw PyMySQL connection (not SQLAlchemy) with `CLIENT.MULTI_STATEMENTS` enabled and SSL if configured
- Runs `CREATE DATABASE IF NOT EXISTS aegis_procurement CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`
- Validates the database name against a safe regex (`^[A-Za-z0-9_]+$`) before use
- Iterates through SQL files 01–09 in sorted order (skips `00_MASTER_DEPLOY.sql`)
- Each file is read, stripped of any `CREATE DATABASE` / `USE` statements (already handled), and executed
- Errors for "already exists" or "duplicate" are silently ignored (idempotent)

### Step 2/6 — Seed Reference Data

```
[pipeline]  Step 2/6 — Seed Reference Data
```

- Re-executes `09_seed_reference_data.sql` to ensure all 9 lookup tables have their baseline rows
- Uses `INSERT IGNORE` so existing rows are not duplicated

### Step 3/6 — Generate Sample Data (or Load External Data)

```
[pipeline]  Step 3/6 — Generate Sample Data
```

- If `--external DIR` was passed: runs `ExternalDataLoader` against the CSV directory (validate → import)
- Otherwise: runs `generate_seed_data.main()` to create all transactional data (14 steps)

### Step 4/6 — Populate Data Warehouse

```
[pipeline]  Step 4/6 — Populate Data Warehouse
```

- Runs the 6-step ETL: dim_date → dim_supplier (SCD2) → dim_material → dim_geography → fact_procurement → fact_esg
- Full refresh (delete + insert) inside a single transaction

### Step 5/6 — Run Analytics Engines

```
[pipeline]  Step 5/6 — Run Analytics Engines
```

Runs all 8 engines in sequence:
1. **MCDA scoring** (TOPSIS by default)
2. **Risk scoring** (7 dimensions, composite, tier assignment)
3. **Concentration analysis** (HHI across 5 dimensions)
4. **Carbon emission calculations**
5. **Should-cost** leakage summary (logs total leakage USD and %)
6. **Working capital** analysis (logs average DPO and total spend)
7. **Scenario planner** baseline run (nearshoring — logs net cost impact)

Each engine is imported lazily (inside the function) to avoid loading unused dependencies.

### Step 6/6 — Verification

```
[pipeline]  Step 6/6 — Verification
```

- Counts rows in **18 key tables** (countries, currencies, suppliers, materials, purchase_orders, po_line_items, shipments, invoices, fx_rates, commodity_prices, esg_assessments, carbon_estimates, dim_date, dim_supplier, fact_procurement, supplier_scorecards, risk_assessments, concentration_analysis)
- Logs each table name, row count, and OK/EMPTY status
- Writes a `DataQualityLogger` entry for each check (table presence, row count)

After verification, `record_finish()` marks the pipeline run as successful and logs the total elapsed time.

### Pipeline Flags

| Flag | Effect |
|------|--------|
| `--skip-schema` | Skip Step 1 (useful after first run) |
| `--skip-seed` | Skip Step 3 (keep existing data) |
| `--skip-warehouse` | Skip Step 4 |
| `--skip-analytics` | Skip Step 5 |
| `--verify-only` | Only run Step 6 |
| `--external DIR` | Use CSV import instead of seed generator in Step 3 |

---

## 14. Data Flow Diagram

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ERP / PO / FX   │     │  Company CSVs    │     │  Live FX APIs    │
│  Source Data      │     │  (7 file types)  │     │  (3-tier failover)│
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                         │
         v                        v                         v
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ generate_seed_   │     │ external_data_   │     │ live_data_       │
│ data.py          │ OR  │ loader.py        │     │ fetcher.py       │
│ (14 steps)       │     │ (validate+import)│     │ (upsert fx_rates)│
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                         │
         v                        v                         v
┌─────────────────────────────────────────────────────────────────────┐
│                    OLTP Layer (30+ tables)                         │
│  suppliers, materials, purchase_orders, po_line_items, shipments,  │
│  invoices, fx_rates, commodity_prices, esg_assessments, carbon,   │
│  compliance_checks, due_diligence_records, quality_*, contracts   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               v
                  ┌───────────────────────┐
                  │  populate_warehouse   │
                  │  .py (ETL, SCD2)     │
                  └───────────┬───────────┘
                              │
                              v
┌─────────────────────────────────────────────────────────────────────┐
│                  Warehouse Layer (6 tables)                        │
│  dim_date, dim_supplier (SCD2), dim_material, dim_geography,      │
│  fact_procurement, fact_esg                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              v                v                v
┌──────────────────┐ ┌────────────────┐ ┌────────────────┐
│  8 Analytics     │ │ Streamlit App  │ │  Power BI      │
│  Engines         │ │ (12 pages)     │ │  Desktop       │
│  ┌─ MCDA         │ │                │ │  (14 PQ, 25+  │
│  ├─ Risk         │ │                │ │   DAX measures)│
│  ├─ Monte Carlo  │ │                │ │                │
│  ├─ HHI          │ └────────────────┘ └────────────────┘
│  ├─ Carbon       │
│  ├─ Should-Cost  │
│  ├─ Working Cap  │
│  └─ Scenarios    │
└────────┬─────────┘
         │
         v
┌─────────────────────────────────────────────────────────────────────┐
│              Analytics Output (4 tables)                           │
│  supplier_scorecards, risk_assessments, simulation_runs,          │
│  concentration_analysis                                           │
└─────────────────────────────────────────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────────────────────────────────┐
│              Audit Layer (3 tables)                                │
│  audit_log, data_quality_log, pipeline_runs                       │
└─────────────────────────────────────────────────────────────────────┘
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

This clears all existing data, imports your CSVs, auto-generates the supplier-material catalog, seeds market data, runs warehouse ETL, and executes all analytics.

### Option B: Add Data Incrementally

1. Insert records directly into the OLTP tables via SQL or a custom script
2. Re-run warehouse and analytics:
   ```bash
   python run_aegis_pipeline.py --skip-schema --skip-seed
   ```

### Option C: Use the Dashboard

Page 12 (Settings → CSV Import) provides drag-and-drop CSV upload. Page 11 (Data Explorer → Ad-Hoc SQL) provides a SQL editor for INSERT, UPDATE, or SELECT statements against any table (DDL is blocked by the safety regex).

---

## Summary

| Component | Count |
|-----------|-------|
| Database tables | 40+ |
| SQL schema files | 10 |
| Analytics engines | 8 |
| Streamlit pages | 12 |
| Utility modules | 5 |
| Data ingestion modules | 4 |
| Pytest tests | 49 |
| CI/CD jobs | 3 |
| Power BI assets | 4 files + 3 docs |
| Tracked currencies | 9 |
| Reference countries | 15 |
| Reference ports | 12 |
| Compliance frameworks | 6 |
| Certifications in catalog | 10 |
| Environment variables | 12 |

The entire system runs from a single command:

```bash
python run_aegis_pipeline.py       # Initialize DB + seed data + ETL + analytics
streamlit run streamlit_app.py     # Launch dashboard at localhost:8501
```

For containerised deployment:

```bash
docker-compose up -d               # MySQL + Streamlit at localhost:8501
```

Live deployment: [https://supplierselectionproject.streamlit.app](https://supplierselectionproject.streamlit.app)
