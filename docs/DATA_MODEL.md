# AEGIS Data Model Reference

> Star-schema warehouse model powering both the Streamlit dashboard and Power BI reports.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│  Layer 1 — OLTP (Source)                            │
│  suppliers, purchase_orders, po_line_items,          │
│  invoices, shipments, materials                     │
├─────────────────────────────────────────────────────┤
│  Layer 2 — Warehouse (Star Schema)                  │
│  fact_procurement, fact_esg                          │
│  dim_date, dim_supplier, dim_material, dim_geography│
├─────────────────────────────────────────────────────┤
│  Layer 3 — Analytics Results                        │
│  supplier_scorecards, risk_assessments,              │
│  concentration_analysis, esg_assessments,            │
│  country_risk_indices, carbon_estimates             │
├─────────────────────────────────────────────────────┤
│  Layer 4 — Audit & Operations                       │
│  audit_log, data_quality_log, pipeline_runs          │
└─────────────────────────────────────────────────────┘
```

---

## Star Schema

### Fact Tables

#### `fact_procurement`
**Grain**: One row per PO line item, converted to USD at order-date FX rate.

| Column | Type | Description |
|--------|------|-------------|
| `procurement_fact_id` | INT PK | Surrogate key |
| `date_key` | INT FK | → dim_date |
| `supplier_key` | INT FK | → dim_supplier |
| `material_key` | INT FK | → dim_material |
| `geography_key` | INT FK | → dim_geography |
| `po_number` | VARCHAR | Source PO reference |
| `quantity` | INT | Units ordered |
| `unit_price_usd` | DECIMAL | Unit price in USD |
| `total_value_usd` | DECIMAL | Line total in USD |
| `original_currency` | VARCHAR | Source currency code |
| `fx_rate_applied` | DECIMAL | FX rate used |
| `delay_days` | INT | Actual − planned delivery days |
| `defect_qty` | INT | Defective units (if inspected) |
| `inspected_qty` | INT | Units inspected |
| `incident_count` | INT | Quality incidents |
| `cost_variance_usd` | DECIMAL | Actual − standard cost |
| `days_to_pay` | INT | Invoice payment days |
| `payment_status` | VARCHAR | Paid / Overdue / Pending |
| `is_maverick` | TINYINT | 1 = off-contract purchase |
| `transport_mode` | VARCHAR | Sea / Air / Road / Rail |
| `carbon_kg` | DECIMAL | Estimated CO₂ for line |

#### `fact_esg`
**Grain**: One row per supplier ESG assessment period.

| Column | Type | Description |
|--------|------|-------------|
| `esg_fact_id` | INT PK | Surrogate key |
| `supplier_key` | INT FK | → dim_supplier |
| `assessment_date` | DATE | Assessment date |
| `environmental_score` | DECIMAL | 0–100 |
| `social_score` | DECIMAL | 0–100 |
| `governance_score` | DECIMAL | 0–100 |
| `composite_score` | DECIMAL | Weighted average |
| `esg_rating` | CHAR(1) | A / B / C / D / F |
| `compliance_gap_count` | INT | # frameworks non-compliant |
| `total_carbon_kg` | DECIMAL | Total CO₂ for supplier |

---

### Dimension Tables

#### `dim_date`
**Grain**: One row per calendar day (2024-01-01 to 2030-12-31).

| Column | Type | Description |
|--------|------|-------------|
| `date_key` | INT PK | YYYYMMDD integer |
| `full_date` | DATE | Calendar date |
| `year` | INT | Calendar year |
| `quarter` | INT | 1–4 |
| `month` | INT | 1–12 |
| `month_name` | VARCHAR | January, February, … |
| `week_of_year` | INT | ISO week number |
| `day_of_week` | INT | 1 (Mon) – 7 (Sun) |
| `day_name` | VARCHAR | Monday, Tuesday, … |
| `is_weekend` | TINYINT | 1 = Sat/Sun |
| `fiscal_year` | INT | Fiscal year (Apr start) |
| `fiscal_quarter` | INT | Fiscal quarter |

#### `dim_supplier`
**Grain**: One row per supplier (SCD Type 1).

| Column | Type | Description |
|--------|------|-------------|
| `supplier_key` | INT PK | Surrogate key |
| `supplier_id` | INT | Source system ID |
| `company_name` | VARCHAR | Legal entity name |
| `country` | VARCHAR | Headquarters country |
| `tier` | VARCHAR | Strategic / Preferred / Approved / Transactional |
| `risk_tier` | VARCHAR | Low / Medium / High / Critical |
| `latest_score` | DECIMAL | Most recent MCDA score |
| `effective_from` | DATE | Record effective date |

#### `dim_material`
**Grain**: One row per material.

| Column | Type | Description |
|--------|------|-------------|
| `material_key` | INT PK | Surrogate key |
| `material_id` | INT | Source system ID |
| `material_name` | VARCHAR | Material description |
| `category` | VARCHAR | Raw Material / Component / Packaging / MRO |
| `uom` | VARCHAR | Unit of measure |

#### `dim_geography`
**Grain**: One row per country.

| Column | Type | Description |
|--------|------|-------------|
| `geo_key` | INT PK | Surrogate key |
| `country_code` | CHAR(3) | ISO 3166-1 alpha-3 |
| `country_name` | VARCHAR | Full country name |
| `region` | VARCHAR | Continent/macro region |
| `sub_region` | VARCHAR | Sub-region |
| `latitude` | DECIMAL | Capital city lat |
| `longitude` | DECIMAL | Capital city lon |

---

## Relationship Diagram

```
                    ┌─────────────┐
                    │  dim_date   │
                    │  date_key   │
                    └──────┬──────┘
                           │ 1
                           │
         ┌─────────────┐   │   ┌──────────────┐
         │dim_supplier │   │   │dim_material  │
         │supplier_key │   │   │material_key  │
         └──────┬──────┘   │   └──────┬───────┘
                │ 1        │          │ 1
                │      ┌───┴───┐      │
                └──────┤ fact_ ├──────┘
                       │procure│
                       │ment   │
                ┌──────┤       ├──────┐
                │      └───────┘      │
                │ 1                   │
         ┌──────┴──────┐       ┌──────┴──────┐
         │dim_geography│       │  fact_esg   │
         │  geo_key    │       │supplier_key │
         └─────────────┘       └─────────────┘
```

---

## Analytics Result Tables

| Table | Grain | Key Columns |
|-------|-------|-------------|
| `supplier_scorecards` | 1 per supplier | composite_score, quality_score, delivery_score, cost_score, risk_score, esg_score, tier |
| `risk_assessments` | 1 per supplier | overall_risk, financial_risk, operational_risk, geographic_risk, compliance_risk, risk_tier |
| `concentration_analysis` | 1 per dimension×value | dimension (supplier/category/country), metric_name, hhi_index, top_share_pct |
| `esg_assessments` | 1 per supplier | environmental_score, social_score, governance_score, composite_score, esg_grade |
| `country_risk_indices` | 1 per country×year | political_stability, economic_freedom, logistics_perf, composite_index |
| `carbon_estimates` | 1 per supplier×route | transport_mode, distance_km, carbon_kg, carbon_per_usd |

---

## Key Measures Summary

| Measure | Formula | Source |
|---------|---------|--------|
| Total Spend | `SUM(fact_procurement[total_value_usd])` | fact_procurement |
| On-Time % | `COUNT(delay_days ≤ 0) / COUNT(*)` | fact_procurement |
| Defect Rate | `SUM(defect_qty) / SUM(inspected_qty)` | fact_procurement |
| Maverick % | `SUM(spend WHERE maverick=1) / Total Spend` | fact_procurement |
| HHI | `Σ(supplier_share²) × 10000` | concentration_analysis |
| ESG Score | `AVERAGE(composite_score)` | fact_esg |
| Carbon Intensity | `Total Carbon / (Total Spend / 1M)` | fact_esg + fact_procurement |
| DPO | `AVERAGE(days_to_pay)` | fact_procurement |

---

## Power BI Relationship Guidance

1. Set `dim_date` as the **Date table** → enables Time Intelligence DAX functions.
2. All relationships should be **Many-to-One** from fact to dimension.
3. Use **single-direction** cross-filtering unless a visual needs bi-directional.
4. Analytics result tables relate to `suppliers` via `supplier_id` (not through dim_supplier).
5. Mark `dim_date[full_date]` as the **Sort by Column** for `dim_date[month_name]`.
