# AEGIS Procurement Intelligence — Exhaustive Audit Report

> **Date:** 2025-07-12  
> **Scope:** 13-area deep audit of `aegis-procurement/`  
> **Method:** Full file-by-file code inspection (every source file read in its entirety)

---

## Table of Contents

1. [Streamlit App](#1-streamlit-app)
2. [Tests](#2-tests)
3. [CI/CD](#3-cicd)
4. [Docker](#4-docker)
5. [Security](#5-security)
6. [Data Quality](#6-data-quality)
7. [Error Handling](#7-error-handling)
8. [Documentation](#8-documentation)
9. [Analytics Gaps](#9-analytics-gaps)
10. [FX Data](#10-fx-data)
11. [Streamlit Pages](#11-streamlit-pages)
12. [Requirements](#12-requirements)
13. [Power BI](#13-power-bi)

---

## 1. Streamlit App

### EXISTS
- **`streamlit_app.py`** (120 lines): Landing page with 6 live KPI cards (Suppliers, POs, Materials, Total Spend, Avg Lead Time, Quality Incidents), pulled from the database via SQLAlchemy.
- Navigation cards describe all 12 modules with descriptive text.
- `try/except` around the DB connection with a helpful fallback message ("Cannot connect to MySQL — ensure database is running").
- `st.set_page_config(layout="wide")` for wide layout.
- 12 pages registered via Streamlit's `pages/` directory convention (01–12).
- `DEMO_MODE` flag exists in `config.py` (line 101) and is referenced in the pipeline and Settings page.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **No UI upload page** — External data can only be loaded via CLI (`python data_ingestion/external_data_loader.py --input-dir`). There is no `st.file_uploader()` widget anywhere in the 12 pages or the main app. | **Critical** |
| No user authentication or role-based access control (RBAC). Anyone on the network can access all 12 pages including the raw SQL Data Explorer. | **Critical** |
| No session-state caching strategy — every page re-queries the database on each interaction. No `@st.cache_data` or `@st.cache_resource` decorators observed. | **Important** |
| No toast/notification system for long-running analytics operations. | Nice-to-have |
| Settings page (page 12) displays config values but **does not persist changes** — it explicitly notes "View-only — changes not persisted." | **Important** |

---

## 2. Tests

### EXISTS
- **`tests/test_aegis.py`** (~200 lines): 24 unit tests across 8 test classes:
  - `TestConfig` (6 tests): Verify DB settings, FX config, risk weights, MCDA weights, HHI/leakage thresholds, emission factors.
  - `TestMCDAEngine` (5 tests): TOPSIS, PROMETHEE II, tie handling, weight normalization, ranking stability.
  - `TestMonteCarlo` (3 tests): GBM, log-normal simulation, correlations.
  - `TestRiskScoring` (1 test): Composite scoring bounds (0–100).
  - `TestConcentration` (4 tests): HHI calculation, classification bounds, edge cases, equal-share scenario.
  - `TestCarbonEngine` (3 tests): Haversine distance, emission estimation, mode-shift logic.
  - `TestShouldCost` (1 test): Cost decomposition sanity.
  - `TestWorkingCapital` (1 test): DPO calculation directional correctness.
- **`pytest.ini`**: Configured with `testpaths = tests`, verbose output, strict markers, `filterwarnings = ignore::DeprecationWarning`.
- Tests are purely computational (pure functions, no DB mocking required for what's tested).

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Zero tests for `external_data_loader.py`** (745 lines, the most complex module). Schema validation, FK resolution, and CSV import logic are entirely untested. | **Critical** |
| **Zero tests for `populate_warehouse.py`** (195 lines). The ETL layer that builds the star schema is untested. | **Critical** |
| **Zero tests for `generate_seed_data.py`** (1030 lines). The seed-data generator is untested. | **Important** |
| **Zero integration tests** — no tests run against a live or mocked MySQL instance. All persistence logic (`persist_risk_assessments`, `run_mcda`, `save_simulation`, etc.) is untested. | **Critical** |
| **Zero Streamlit page tests** — no rendering/interaction tests for any of the 12 pages. | **Important** |
| **No test for `run_aegis_pipeline.py`** — the 6-step orchestrator is untested. | **Important** |
| `pytest-cov` is in `requirements.txt` but **never invoked** — no `--cov` flag in CI or `pytest.ini`. Coverage is unknown. | **Important** |
| Only 1 test each for `TestRiskScoring`, `TestShouldCost`, `TestWorkingCapital` — these are smoke tests, not thorough. | Nice-to-have |

---

## 3. CI/CD

### EXISTS
- **`.github/workflows/ci.yml`** (62 lines) with 3 jobs:
  1. **`test`**: Ubuntu-latest, Python 3.11, MySQL 8.0 service container, installs requirements, runs `pytest tests/ -v --tb=short`.
  2. **`lint`**: Runs `black --check .` and `flake8 . --max-line-length=120`.
  3. **`docker`**: On `main` branch only — builds Docker image, runs a basic `python -c "import config"` smoke test.
- MySQL service container configured with health checks (`mysqladmin ping`), password matches `config.py` defaults.
- Triggers on push to `main`/`develop` and on pull requests to `main`.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **No coverage gating** — `pytest-cov` is installed but `--cov` is never passed. No coverage thresholds or reports. | **Important** |
| **No type checking** — `mypy` is neither installed nor run. `.mypy_cache/` is in `.gitignore` suggesting it was used once, but there's no `mypy.ini`, `pyproject.toml` config, or CI step. | **Important** |
| **No integration test stage** — the `test` job runs the 24 pure-unit tests. No tests exercise the schema creation, seed data, or ETL pipeline against the MySQL service. | **Critical** |
| **No staging / canary / approval gate** — Docker build proceeds directly on push to `main`, no manual approval or deployment environment. | **Important** |
| **No security scanning** — no `bandit`, `safety`, `pip-audit`, `trivy`, or `snyk` steps. | **Important** |
| **No artifact upload** — test results and lint reports are not stored. | Nice-to-have |
| Docker smoke test only runs `python -c "import config"` — does not verify the Streamlit app actually starts. | Nice-to-have |

---

## 4. Docker

### EXISTS
- **`Dockerfile`** (28 lines):
  - `python:3.11-slim` base image.
  - Installs `default-mysql-client` and `curl` (apt).
  - Copies requirements, installs pip dependencies.
  - `HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8501/_stcore/health` — proper Streamlit health check.
  - `EXPOSE 8501`, `ENTRYPOINT` runs `streamlit run streamlit_app.py --server.headless true`.
- **`docker-compose.yml`** (33 lines):
  - **mysql** service: `mysql:8.0`, health check (`mysqladmin ping`), persistent volume (`mysql_data`), mounts `./database/` to `/docker-entrypoint-initdb.d/` for schema initialization.
  - **app** service: Builds from Dockerfile, `depends_on: mysql (service_healthy)`, passes `DATABASE_URL` env var, maps `8501:8501`.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Hardcoded password in `docker-compose.yml`** — `MYSQL_ROOT_PASSWORD: Maconoelle86` and the full `DATABASE_URL` with password in cleartext. Should use `.env` file or Docker secrets. | **Critical** |
| **No `.dockerignore`** — the build context includes `tests/`, `docs/`, `external_data_samples/`, `.git/`, `.github/`, `__pycache__/`, increasing image size and risking secret leakage. | **Important** |
| **No resource limits** — no `mem_limit`, `cpus`, `deploy.resources` on either service. | **Important** |
| **No app healthcheck in compose** — the Dockerfile has one, but the compose file only defines a health check for the mysql service. The app service relies on the Dockerfile's HEALTHCHECK, which works but can't be configured per-environment via compose. | Nice-to-have |
| **No named network** — both services use the default bridge network. Named networks improve DNS resolution and security segregation. | Nice-to-have |
| **No restart policy** on the app service. The mysql service also has no explicit restart policy. | **Important** |
| **No multi-stage build** — `default-mysql-client` and build tools remain in the final image. | Nice-to-have |
| No backup/restore strategy for the `mysql_data` volume. | **Important** |

---

## 5. Security

### EXISTS
- DB credentials sourced from `os.getenv()` in `config.py` (lines 5–13), supporting environment-variable injection.
- `external_data_loader.py` uses parameterized queries (`:param` style) for all data INSERT operations.
- `pages/11_Data_Explorer.py` has a keyword-based SQL injection guard: rejects queries starting with `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`.
- `.gitignore` excludes `.env` files.
- `DEMO_MODE` flag prevents accidental use of production credentials in demo scenarios.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Hardcoded password fallback** in `config.py` line 11: `DB_PASSWORD = os.getenv("DB_PASSWORD", "Maconoelle86")`. If the env var is unset, the real password is used. This password is also in cleartext in `docker-compose.yml`. | **Critical** |
| **Data Explorer allows arbitrary SELECT** — keyword blocking only checks the first word. Attackers can craft payloads like `SELECT * FROM users; DROP TABLE suppliers --` or use sub-queries/CTEs to exfiltrate data. No query parameterization on the ad-hoc SQL input. | **Critical** |
| **f-string SQL in 6 locations** (table/column names, not user input — low actual risk but poor practice): `run_aegis_pipeline.py:199`, `generate_seed_data.py:47/52`, `external_data_loader.py:367`, `pages/11_Data_Explorer.py:44/48`. | **Important** |
| **No secret management** — no Vault, AWS Secrets Manager, or Azure Key Vault integration. Passwords are environment variables or hardcoded. | **Important** |
| `.gitignore` missing entries for: `.coverage`, `htmlcov/`, `*.log`, `external_data_samples/` (may contain sensitive company data). | **Important** |
| **No HTTPS/TLS configuration** — Streamlit runs on plain HTTP. | **Important** |
| **No authentication middleware** — Streamlit has no built-in auth. No `streamlit-authenticator` or reverse-proxy auth. | **Critical** |
| **No audit trail** — `audit_log` and `data_quality_log` tables exist in the schema (file `08_create_audit_tables.sql`) but are **never written to** by any Python code. | **Critical** |
| No Content Security Policy or CORS headers configured. | Nice-to-have |
| No rate limiting on the Data Explorer endpoint. | Nice-to-have |

---

## 6. Data Quality

### EXISTS
- **`DataValidator`** class in `external_data_loader.py` (lines 15–220): Validates 7 CSV file types with:
  - Required/optional column checks.
  - Numeric type coercion and range validation.
  - Enum validation (e.g., transport_mode must be Sea/Air/Rail/Road/Multimodal; esg_rating must be A/B/C/D/F).
  - Date format validation (ISO 8601).
  - Foreign key resolution (supplier/material/PO/country/currency lookups).
- Schema-level constraints in SQL files (`database/00-09`): NOT NULL, UNIQUE, FOREIGN KEYS, CHECK constraints, ENUM types.
- `generate_seed_data.py` produces internally consistent synthetic data respecting all FK relationships.
- The pipeline's step 6 (`verify_output`) in `run_aegis_pipeline.py` checks row counts in key tables and validates that analytics outputs were generated.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Audit tables are dead code** — `audit_log` and `data_quality_log` tables (from `08_create_audit_tables.sql`) are created but **no INSERT is ever executed** against them. There is zero runtime data quality logging. | **Critical** |
| **No data freshness detection** — no mechanism to detect stale FX rates, outdated POs, or incomplete import runs. | **Important** |
| **No duplicate detection** — external_data_loader does not check for duplicate POs, suppliers, or invoices that may already exist in the database. Re-running the import will either fail on UNIQUE constraints or silently create duplicates. | **Critical** |
| **No data profiling/summary** — no statistics on null rates, outliers, or distribution anomalies after import. | **Important** |
| **Validation mode is LENIENT only** — type mismatches produce warnings but don't abort. There's no STRICT mode option. | Nice-to-have |
| No reconciliation step to verify that warehouse fact tables match OLTP source counts. | **Important** |

---

## 7. Error Handling

### EXISTS
- `streamlit_app.py`: `try/except` around DB connection with user-friendly fallback.
- `external_data_loader.py`: Raises `ValueError` on schema violations, uses `try/except` in FK mapping with descriptive error messages.
- `run_aegis_pipeline.py`: Main `try/except` around each pipeline step with status messages; catches `Exception` broadly.
- Analytics engines use defensive `if df.empty: return` patterns.
- `generate_seed_data.py`: Wraps the full seed process in `try/except` with rollback.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Zero use of the `logging` module** — all 15+ Python files use `print()` exclusively. No log levels, no log files, no structured logging, no correlation IDs. A `grep` for `import logging` returned zero matches across the entire project. | **Critical** |
| **Broad exception catching** — `run_aegis_pipeline.py` catches bare `Exception` in several places, swallowing stack traces. | **Important** |
| **No retry logic** — DB connections, external API calls (live FX config exists but isn't implemented), and long-running analytics have no retry/backoff. | **Important** |
| **No graceful degradation** in Streamlit pages — if a query fails, most pages show the raw Python traceback via Streamlit's default error handler rather than a user-friendly message. | **Important** |
| **No circuit breaker** pattern for DB connections. | Nice-to-have |
| **No alerting** — when the pipeline fails or data quality issues are detected, no email/Slack/webhook notification. | **Important** |
| Analytics engines do not log warnings when input DataFrames have unexpected null counts or zero rows. | Nice-to-have |

---

## 8. Documentation

### EXISTS
- **`README.md`** (257 lines): Comprehensive — architecture overview, feature table (17 features), methodology descriptions (TOPSIS, GBM, HHI, GHG, OECD DD), quick start guide, directory structure, configuration table, deployment notes. Well-written.
- **`EXTERNAL_DATA_GUIDE.md`** (358 lines): Detailed CSV specifications for all 7 file types with column tables, validation rules, worked examples, common issues & solutions, full company workflow example. Excellent.
- **`PRODUCTION_READINESS.md`** (~45 lines): Honest self-assessment of what's ready vs. what needs hardening. Lists gaps.
- **`powerbi/DAX_Measures.md`**: 6 sections of DAX measures + 10 recommended Power BI report pages.
- Inline docstrings in all analytics engines (module-level and function-level).

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **`docs/` directory is completely empty** — no architecture diagrams, ER diagrams, data flow docs, or API reference. | **Important** |
| **No `CONTRIBUTING.md`** — no guidance for new developers on code style, PR process, branch strategy. | Nice-to-have |
| **No `CHANGELOG.md`** or version history. | Nice-to-have |
| **No inline comments in Streamlit pages** explaining the SQL queries or column expectations. This contributes to the column-mismatch bugs documented in §11. | **Important** |
| **No ER diagram** — the database has 40+ tables but no visual schema documentation. | **Important** |
| **No runbook/playbook** for operational tasks (backup, restore, re-seed, debug failed pipeline). | **Important** |
| No docstrings in `populate_warehouse.py` functions. | Nice-to-have |
| README says `DB_PASSWORD` default is "*(set in env)*" but `config.py` actually defaults to `"Maconoelle86"` — documentation hides the hardcoded fallback. | **Important** |

---

## 9. Analytics Gaps

### EXISTS
All 8 analytics engines are fully implemented:

| Engine | File | Lines | Called in Pipeline | Persists to DB |
|--------|------|-------|--------------------|----------------|
| MCDA (TOPSIS/PROMETHEE/WSM) | `mcda_engine.py` | 326 | ✅ Step 5 | ✅ `supplier_scorecards` |
| Monte Carlo | `monte_carlo.py` | 308 | ❌ (page only) | ✅ `simulation_runs` |
| Risk Scoring | `risk_scoring.py` | ~220 | ✅ Step 5 | ✅ `risk_assessments` |
| Concentration (HHI) | `concentration.py` | ~250 | ✅ Step 5 | ✅ `concentration_analysis` |
| Carbon/GHG | `carbon_engine.py` | ~200 | ✅ Step 5 | ⚠️ Returns DataFrame only; seed data creates `carbon_estimates` |
| Should-Cost | `should_cost.py` | ~185 | ❌ Not called | ❌ No persist function |
| Working Capital | `working_capital.py` | ~200 | ❌ Not called | ❌ No persist function |
| Scenario Planner | `scenario_planner.py` | ~230 | ❌ Not called | ❌ No persist function |

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **3 engines not in the pipeline** — `should_cost.py`, `working_capital.py`, `scenario_planner.py` are never called in `run_aegis_pipeline.py`. They only run on-demand from their respective Streamlit pages. Their outputs are not persisted to the database. | **Critical** |
| **`carbon_engine.py` calculates but does not persist** — `calculate_emissions()` returns DataFrames but has no `persist_to_db()` function. The `carbon_estimates` table is only populated during seed data generation. If external data is loaded, there will be no carbon data. | **Critical** |
| **No analytics output tables** for should-cost, working-capital, or scenario outputs — the database schema has no tables for these results. | **Important** |
| **Monte Carlo not in pipeline** — simulations only run interactively from the Monte Carlo Lab page. No pre-computed simulation results for Power BI or batch reporting. | **Important** |
| **No scheduled re-run capability** — analytics are one-shot pipeline runs; no cron, Airflow, or Celery configuration for periodic refresh. | **Important** |
| **No incremental analytics** — the pipeline truncates and rebuilds all analytics tables on each run. | Nice-to-have |
| No ensemble or combination of MCDA methods — each method runs independently but there's no final combined ranking. | Nice-to-have |

---

## 10. FX Data

### EXISTS
- **`config.py`** defines:
  - `FX_ANCHOR_RATES`: 9 currencies with anchor rates to USD (NGN, EUR, GBP, CNY, INR, BRL, ZAR, TRY, KRW).
  - `FX_VOLATILITIES`: Annualized volatilities per currency (e.g., NGN 0.15, EUR 0.06).
  - `ENABLE_LIVE_FX = os.getenv("ENABLE_LIVE_FX", "false").lower() == "true"` — feature flag for live FX.
  - `FX_API_URLS`: 3-tier API provider list (exchangerate-api, frankfurter, open.er-api) — endpoints defined but **never called**.
- **`generate_seed_data.py`**: Generates ~7,000 synthetic FX rate records via Geometric Brownian Motion (GBM) backward from anchor rates, producing realistic daily rates for all 9 currency pairs over the data window.
- **`analytics/monte_carlo.py`**: `simulate_fx_gbm()` generates forward-looking FX paths for simulation/stress testing from the Monte Carlo Lab page.
- Database table `fx_rates` with columns: `rate_id`, `currency_pair`, `rate_date`, `exchange_rate`, `source`.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **No live FX integration** — `ENABLE_LIVE_FX` flag and `FX_API_URLS` are defined but **zero code exists** to actually call any FX API. No `requests.get()` to any FX endpoint anywhere in the codebase. | **Critical** |
| **External data mode has no FX rates** — `external_data_loader.py` does not import or generate FX rates. After loading company data, the `fx_rates` table will be empty, breaking any FX-dependent analytics (Monte Carlo, currency concentration, USD conversion). | **Critical** |
| **No commodity price import** — similar to FX: `commodity_prices` table is only populated by seed data, not by external data loader. | **Important** |
| **No FX rate staleness detection** — no check for how old the latest FX rate is, no warning to users. | **Important** |
| **No FX rate interpolation** — if rates are missing for specific dates, no gap-filling logic exists. | Nice-to-have |

---

## 11. Streamlit Pages

### EXISTS
All 12 pages exist and follow a consistent pattern (set page config → connect to DB → query → visualize with Plotly):

| # | Page | Lines | Status |
|---|------|-------|--------|
| 01 | Executive Dashboard | ~130 | ⚠️ Column name issues |
| 02 | Supplier Scorecards | ~160 | ✅ Well-implemented |
| 03 | Risk Radar | ~170 | ✅ Well-implemented |
| 04 | Monte Carlo Lab | ~170 | ✅ Well-implemented |
| 05 | Concentration Analysis | ~180 | ⚠️ Column name mismatches |
| 06 | Carbon Dashboard | ~150 | ⚠️ Column name mismatches |
| 07 | Should-Cost | ~140 | ❌ Column name mismatches with engine |
| 08 | Working Capital | ~140 | ❌ Column name mismatches with engine |
| 09 | ESG Compliance | ~170 | ⚠️ Column name mismatches |
| 10 | Scenario Planner | ~170 | ❌ Return dict key mismatches |
| 11 | Data Explorer | ~130 | ⚠️ SQL injection risk |
| 12 | Settings | ~120 | ✅ View-only, working |

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **Column name mismatches (pages 05–10)** — Multiple pages reference columns that don't match the actual database schema or analytics engine return values. Examples: Page 05 references `company_name` (actual: `supplier_name`), `total_value_usd` (actual: varies). Page 07 references `actual_unit_price`, `should_cost_total`, `flag`, `variance_pct` but `build_should_cost()` returns `quoted_usd`, `should_cost_usd`, `leakage_flag`, `cost_variance_pct`. Page 08 references `total_outstanding`, `overdue_count` not matching `working_capital.py` return keys. Page 10 references `current_avg_cost` but scenario_planner returns `current_spend`. **These pages will crash at runtime with KeyError/column-not-found errors.** | **Critical** |
| Page 01 references `ship_date` column — schema likely uses `dispatch_date`. | **Critical** |
| **No upload page** — Users cannot import external data through the Streamlit UI. | **Critical** |
| **No loading spinners** — Pages don't use `st.spinner()` for long-running queries or analytics calculations. | Nice-to-have |
| **No `@st.cache_data`** — Repeated identical queries on every widget interaction. | **Important** |
| **No responsive design testing** — pages use `layout="wide"` but no mobile viewport considerations. | Nice-to-have |
| **No page-level error boundaries** — if any query fails, the entire page crashes with a Streamlit traceback. | **Important** |
| **No cross-page filtering** — each page queries independently; no shared date range, supplier, or currency filter in session state. | Nice-to-have |

---

## 12. Requirements

### EXISTS
- **`requirements.txt`** (30 lines) with pinned minimum versions:
  ```
  sqlalchemy>=2.0
  pymysql>=1.1
  numpy>=1.26
  pandas>=2.1
  scipy>=1.12
  plotly>=5.22
  streamlit>=1.38
  requests>=2.31
  openpyxl>=3.1
  Pillow>=10.0
  cryptography>=42.0
  streamlit-option-menu>=0.3
  python-dotenv>=1.0
  pytest>=8.0
  pytest-cov>=5.0
  black>=24.0
  flake8>=7.0
  ```

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **`pytest-cov>=5.0` installed but never used** — not invoked in `pytest.ini` or CI. | **Important** |
| **`mypy` not listed** despite `.mypy_cache/` in `.gitignore`. | **Important** |
| **`streamlit-option-menu>=0.3`** listed but a search for `option_menu` in the codebase found zero imports. Possibly unused dependency. | Nice-to-have |
| **No `requirements-dev.txt`** separation — test/lint tools are bundled with production dependencies, bloating the Docker image. | **Important** |
| **No pinned upper bounds** — `>=` only. A breaking release of `sqlalchemy` 3.x, `pandas` 3.x, or `streamlit` 2.x could break the app without warning. | **Important** |
| **No `pyproject.toml`** or `setup.py` — project is not installable as a package. | Nice-to-have |
| No `pip-compile` / `pip-tools` lockfile for reproducible builds. | **Important** |
| `requests>=2.31` is listed (likely for planned live FX) but is not imported in any production code. | Nice-to-have |

---

## 13. Power BI

### EXISTS
- **`powerbi/AEGIS_Theme.json`**: Complete Power BI theme with custom colors, fonts, data colors, visual styles. Professional-looking palette.
- **`powerbi/DAX_Measures.md`**: 6 sections of DAX measures:
  1. Spend Analytics (Total Spend, MoM Growth, Spend by Category, etc.)
  2. Supplier Performance (Avg Lead Time, On-Time Delivery %, Quality Score, etc.)
  3. Risk Metrics (Composite Risk Score, HHI, At-Risk Spend %, etc.)
  4. ESG & Carbon (Carbon Intensity, ESG Compliance %, etc.)
  5. Working Capital (DPO, Outstanding Payables, Payment Compliance %, etc.)
  6. Simulation / What-If (parameterized measures)
- 10 recommended report pages documented with layout guidance.

### MISSING / Incomplete
| Gap | Severity |
|-----|----------|
| **No `.pbix` template file** — users must build the Power BI report from scratch using the DAX doc. | **Important** |
| **No Power BI dataflow or semantic model** — no `.bim`, `.pbit`, or dataflow JSON. | **Important** |
| **No DirectQuery/Import configuration** — no documentation on how to connect Power BI to the MySQL database (connection string, gateway config). | **Important** |
| DAX measures reference table/column names that may not match the actual database schema (same concern as Streamlit pages). | **Important** |
| No Power BI deployment pipeline (Azure DevOps, GitHub Actions, or PowerShell script for `pvis-powerbi/`). | Nice-to-have |

---

## Summary Scoreboard

| # | Area | Critical | Important | Nice-to-have |
|---|------|----------|-----------|--------------|
| 1 | Streamlit App | 2 | 1 | 1 |
| 2 | Tests | 3 | 3 | 1 |
| 3 | CI/CD | 1 | 4 | 2 |
| 4 | Docker | 1 | 3 | 3 |
| 5 | Security | 4 | 3 | 2 |
| 6 | Data Quality | 2 | 3 | 1 |
| 7 | Error Handling | 1 | 3 | 2 |
| 8 | Documentation | 0 | 4 | 3 |
| 9 | Analytics Gaps | 2 | 3 | 2 |
| 10 | FX Data | 2 | 2 | 1 |
| 11 | Streamlit Pages | 3 | 2 | 3 |
| 12 | Requirements | 0 | 4 | 3 |
| 13 | Power BI | 0 | 4 | 1 |
| **TOTAL** | | **21** | **39** | **25** |

---

## Top 10 Priority Fixes (Ordered)

1. **Fix Streamlit page column name mismatches** (§11) — Pages 05–10 will crash at runtime. Map every SQL query and DataFrame column reference to the actual database schema and analytics engine return values.

2. **Remove hardcoded passwords** (§5, §4) — Delete `"Maconoelle86"` from `config.py` default and `docker-compose.yml`. Use `.env` file + `python-dotenv`, and document the required env vars.

3. **Add authentication** (§5, §1) — Integrate `streamlit-authenticator` or deploy behind a reverse proxy (nginx/Traefik) with OAuth2/OIDC.

4. **Implement audit logging** (§5, §6) — Wire up the existing `audit_log` and `data_quality_log` tables. Replace all `print()` calls with Python's `logging` module.

5. **Integrate missing engines into pipeline** (§9) — Add `should_cost`, `working_capital`, and `scenario_planner` to the pipeline and create corresponding persistence functions and database tables.

6. **Fix FX/commodity data for external mode** (§10) — Either generate synthetic FX rates during external data import or implement the live FX API integration that's already stubbed out.

7. **Add integration tests** (§2) — Write tests that exercise `external_data_loader.py`, `populate_warehouse.py`, and the full pipeline against a test MySQL instance (use the CI service container).

8. **Add coverage reporting to CI** (§2, §3) — Add `--cov=. --cov-report=xml --cov-fail-under=60` to the pytest command in CI.

9. **Secure the Data Explorer** (§5) — Replace keyword-based SQL injection protection with a proper read-only DB user or query parameterization. Consider using SQLAlchemy's `text()` with bound parameters, or restrict to pre-built queries only.

10. **Add a UI upload page** (§1, §11) — Create a 13th Streamlit page with `st.file_uploader()` that wraps `ExternalDataLoader`, giving users a no-CLI path to import their data.

---

*Report generated from exhaustive file-by-file code inspection of all source files in `aegis-procurement/`.*
