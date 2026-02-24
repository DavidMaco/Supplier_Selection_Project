# AEGIS Architecture

> System architecture for the Adaptive Engine for Global Intelligent Sourcing.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                               │
│  CSV Imports │ MySQL OLTP │ Live FX APIs │ Commodity Feeds    │
└──────────┬───────────┬──────────┬───────────┬────────────────┘
           │           │          │           │
           ▼           ▼          ▼           ▼
┌──────────────────────────────────────────────────────────────┐
│                 INGESTION LAYER                               │
│  generate_seed_data.py  │  external_data_loader.py           │
│  populate_warehouse.py  │  live_data_fetcher.py              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  MYSQL WAREHOUSE                              │
│  ┌─────────┐  ┌────────────┐  ┌─────────────┐               │
│  │Reference │  │  OLTP      │  │ Star Schema │               │
│  │Tables    │  │  Tables    │  │ fact + dim  │               │
│  └─────────┘  └────────────┘  └─────────────┘               │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  ANALYTICS ENGINES (8)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐       │
│  │ Scorecard   │  │ Risk Matrix  │  │ Concentration │       │
│  │ (MCDA)      │  │              │  │ (HHI)        │       │
│  └─────────────┘  └──────────────┘  └───────────────┘       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐       │
│  │ ESG         │  │ Carbon       │  │ Should-Cost   │       │
│  │             │  │ Footprint    │  │               │       │
│  └─────────────┘  └──────────────┘  └───────────────┘       │
│  ┌─────────────┐  ┌──────────────┐                           │
│  │ Working     │  │ Scenario     │                           │
│  │ Capital     │  │ Planner      │                           │
│  └─────────────┘  └──────────────┘                           │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Streamlit   │  │  Power BI    │  │  Excel       │
│  Dashboard   │  │  Reports     │  │  Export      │
│  (12 pages)  │  │  (10 pages)  │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Component Map

### Pipeline Orchestrator
- **`run_aegis_pipeline.py`** — 6-step master pipeline
  - Step 1: Deploy schema (10 SQL files)
  - Step 2: Seed reference data
  - Step 3: Generate sample / import external data
  - Step 4: ETL into warehouse
  - Step 5: Run all 8 analytics engines
  - Step 6: Verify table integrity

### Data Ingestion (`data_ingestion/`)
| Module | Purpose |
|--------|---------|
| `generate_seed_data.py` | Synthetic procurement data (suppliers, POs, invoices, shipments) |
| `populate_warehouse.py` | ETL from OLTP → star schema (fact + dimensions) |
| `external_data_loader.py` | Import company CSVs with validation |
| `live_data_fetcher.py` | Real-time FX rates from 3-tier API fallback |

### Analytics Engines (`analytics/`)
| Engine | Output Table | Algorithm |
|--------|-------------|-----------|
| `scorecard_engine.py` | supplier_scorecards | MCDA weighted scoring (5 dimensions) |
| `risk_engine.py` | risk_assessments | Multi-dimensional risk matrix |
| `concentration_engine.py` | concentration_analysis | HHI, CR3, entropy metrics |
| `esg_engine.py` | esg_assessments | ESG composite with framework compliance |
| `carbon_engine.py` | carbon_estimates | Haversine distance × emission factors |
| `should_cost_engine.py` | (inline results) | Cost decomposition model |
| `working_capital_engine.py` | (inline results) | DIO, DPO, CCC calculation |
| `scenario_planner.py` | simulation_runs | What-if parameter simulation |

### Streamlit Dashboard (`pages/`)
| Page | Content |
|------|---------|
| 01 | Executive Summary — KPIs, trends, alerts |
| 02 | Supplier Scorecards — MCDA matrix, radar |
| 03 | Risk Matrix — Heatmap, drill-down |
| 04 | Spend Analytics — Decomposition, trends |
| 05 | ESG Dashboard — Scores, compliance |
| 06 | Carbon Footprint — Map, transport breakdown |
| 07 | Scenario Planner — What-if simulation |
| 08 | Working Capital — Cash flow, DPO |
| 09 | Should-Cost Model — Cost breakdown |
| 10 | Concentration — HHI, treemap |
| 11 | Data Explorer — SQL query, export |
| 12 | Settings — Weights, config, imports |

### Utilities (`utils/`)
| Module | Purpose |
|--------|---------|
| `logging_config.py` | Structured logging with file + console + DB audit |
| `auth.py` | Dashboard authentication gate (SHA-256) |
| `freshness.py` | Pipeline run tracking + sidebar badge |
| `export.py` | Executive Excel export (multi-sheet) |

### Power BI (`powerbi/`)
| File | Purpose |
|------|---------|
| `AEGIS_Theme.json` | Custom theme (Tableau-10 palette) |
| `DAX_Measures.md` | 25+ DAX measure definitions |
| `AEGIS_Dashboard_BUILD.md` | Page-by-page build instructions |
| `PowerQuery_Connections.pq` | Power Query M scripts for all tables |

### Infrastructure
| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11 container image |
| `docker-compose.yml` | App + MySQL stack (env-var passwords) |
| `.github/workflows/ci.yml` | CI: lint, test, schema deploy |
| `pyproject.toml` | black, ruff, pytest configuration |

---

## Security Model

```
┌─────────────────────────────────────────┐
│  Authentication                          │
│  • Streamlit: SHA-256 login gate         │
│  • Power BI: Row-Level Security          │
│  • MySQL: Credential via env vars        │
│  • Docker: .env file (not committed)     │
└─────────────────────────────────────────┘
```

---

## Data Flow

```
External CSVs / Seed Data
        │
        ▼
  OLTP Tables (suppliers, POs, invoices, shipments)
        │
        ▼ populate_warehouse.py (ETL)
        │
  Star Schema (fact_procurement, fact_esg + 4 dims)
        │
        ▼ 8 Analytics Engines
        │
  Analytics Results (scorecards, risk, concentration, ESG, carbon)
        │
        ├──▶ Streamlit (real-time interactive)
        ├──▶ Power BI (scheduled refresh)
        └──▶ Excel Export (on-demand)
```
