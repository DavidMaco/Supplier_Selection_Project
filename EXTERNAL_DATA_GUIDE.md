# AEGIS External Data Import Guide

## Overview

AEGIS can operate in two modes:
- **Seed Mode** (default): Uses realistic generated data for demos/testing
- **External Mode**: Imports your company's actual procurement data

This guide explains how to prepare and import your company data.

---

## Quick Start

### Step 1: Prepare CSV Files
Create a directory with your CSV files following the specifications below. At minimum you need 4 files: `suppliers.csv`, `materials.csv`, `purchase_orders.csv`, `po_line_items.csv`.

### Step 2: Validate & Import
```powershell
cd aegis-procurement
python data_ingestion\external_data_loader.py --input-dir .\company_data
```

### Step 3: Populate Warehouse
```powershell
python data_ingestion\populate_warehouse.py
```

### Step 4: Run Analytics
```powershell
python run_aegis_pipeline.py
```

### Step 5: Launch Dashboard
```powershell
streamlit run streamlit_app.py
```

---

## CSV File Specifications

### 1. **suppliers.csv** (Required)

Supplier master data. One row per supplier.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **supplier_name** | Text | Yes | Unique supplier name (e.g., "ABC Chemical Ltd") |
| **country** | Text | Yes | Country name — must match AEGIS reference data (e.g., "Nigeria", "Germany") |
| **currency_code** | Text | Yes | 3-letter currency code: USD, EUR, GBP, CNY, NGN, JPY, KRW, BRL, ZAR, TRY |
| **lead_time_days** | Number | Yes | Average delivery time in days (must be > 0) |
| supplier_code | Text | No | Unique code (auto-generated if missing: SUP-0001, SUP-0002, ...) |
| sector | Text | No | Industry sector name (defaults to first available sector) |
| tier_level | Text | No | Strategic, Preferred, Approved, Conditional, Blocked (default: Approved) |
| company_size | Text | No | Micro, Small, Medium, Large, Enterprise |
| annual_revenue_usd | Number | No | Annual revenue in USD |
| lead_time_stddev | Number | No | Lead time standard deviation (default: 20% of lead_time_days) |
| defect_rate_pct | Number | No | Historical defect rate as % 0-100 (default: 2.0) |
| payment_terms_days | Number | No | Standard payment terms in days (default: 30) |
| is_iso9001_certified | 0/1 | No | ISO 9001 certification status (default: 0) |
| contact_email | Text | No | Primary contact email |

#### Example
```csv
supplier_name,country,currency_code,lead_time_days,lead_time_stddev,defect_rate_pct,tier_level
"AfroPipe Industries",Nigeria,NGN,18,3.6,2.5,Approved
"Rhine Chemical GmbH",Germany,EUR,14,2.8,0.8,Strategic
"Shanghai Heavy Eng",China,CNY,28,5.6,1.5,Preferred
```

**Supported Countries** (pre-loaded in AEGIS):
Nigeria, Germany, China, India, United States, United Kingdom, Brazil, South Africa, Turkey, South Korea, Japan, United Arab Emirates, Saudi Arabia, Ghana, Cameroon

---

### 2. **materials.csv** (Required)

Material/product catalog. One row per material.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **material_name** | Text | Yes | Unique material name (e.g., "Carbon Steel Pipe 6in") |
| **category** | Text | Yes | Material category (e.g., "Pipes", "Valves", "Chemicals") |
| **standard_cost_usd** | Number | Yes | Standard unit cost in USD (must be >= 0) |
| material_code | Text | No | Auto-generated if missing (MAT-0001, ...) |
| sub_category | Text | No | Sub-category for finer grouping |
| commodity_group | Text | No | Commodity group (defaults to category) |
| unit_of_measure | Text | No | UOM (default: KG). Common: KG, MT, EA, LT, M2, SET |
| is_critical | 0/1 | No | Critical material flag (default: 0) |

#### Example
```csv
material_name,category,standard_cost_usd,commodity_group,unit_of_measure,is_critical
"Carbon Steel Pipe 6in",Pipes,45.00,Steel,MT,1
"Gate Valve 8in 150#",Valves,320.00,Valves,EA,1
"Epoxy Coating 2-Part",Coatings,18.00,Chemicals,LT,0
```

---

### 3. **purchase_orders.csv** (Required)

Purchase order headers. One row per PO.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **order_date** | Date | Yes | PO date (format: YYYY-MM-DD) |
| **supplier_name** | Text | Yes | Must match a name in suppliers.csv |
| **currency_code** | Text | Yes | 3-letter currency code |
| **total_amount** | Number | Yes | Total PO value in PO currency (>= 0) |
| po_number | Text | No | Unique PO number (auto-generated if missing) |
| required_date | Date | No | Required delivery date (default: order_date + 45 days) |
| status | Text | No | Draft, Approved, Shipped, In Transit, Customs, Delivered, Closed, Cancelled (default: Delivered) |
| freight_cost_usd | Number | No | Freight cost in USD (default: 0) |
| landed_cost_usd | Number | No | Landed cost in USD (default: total_amount) |
| is_maverick | 0/1 | No | Maverick (off-contract) flag (default: 0) |

#### Example
```csv
po_number,order_date,supplier_name,currency_code,total_amount,status,landed_cost_usd
PO-2024-0001,2024-01-15,"AfroPipe Industries",NGN,8500000,Delivered,7800
PO-2024-0002,2024-01-20,"Rhine Chemical GmbH",EUR,45000,Delivered,48500
```

**Date Format:** ISO 8601 (YYYY-MM-DD)

---

### 4. **po_line_items.csv** (Required)

PO line items linking purchase orders to materials. Multiple rows per PO.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **po_number** | Text | Yes | Must match a po_number from purchase_orders.csv |
| **material_name** | Text | Yes | Must match a material_name from materials.csv |
| **quantity** | Number | Yes | Line item quantity (must be > 0) |
| **unit_price** | Number | Yes | Unit price in PO currency (must be >= 0) |

#### Example
```csv
po_number,material_name,quantity,unit_price
PO-2024-0001,"Carbon Steel Pipe 6in",50,42.00
PO-2024-0001,"Gasket Spiral Wound 6in",100,8.50
PO-2024-0002,"Epoxy Coating 2-Part",200,17.50
```

---

### 5. **shipments.csv** (Optional)

Shipment tracking data. One row per shipment.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **po_number** | Text | Yes | Must match a PO number |
| **transport_mode** | Text | Yes | Sea, Air, Rail, Road, Multimodal |
| **dispatch_date** | Date | Yes | Shipment dispatch date (YYYY-MM-DD) |
| carrier_name | Text | No | Carrier/logistics provider name |
| origin_port | Text | No | Origin port name (must match AEGIS port data) |
| destination_port | Text | No | Destination port name |
| weight_tonnes | Number | No | Shipment weight in metric tonnes (default: 0) |
| eta_date | Date | No | Estimated arrival date |
| actual_arrival | Date | No | Actual arrival date |
| final_delivery_date | Date | No | Final delivery to site |
| status | Text | No | Pending, In Transit, At Port, Customs, Delivered, Exception (default: Delivered) |

#### Example
```csv
po_number,transport_mode,dispatch_date,carrier_name,weight_tonnes,eta_date,actual_arrival,status
PO-2024-0001,Sea,2024-01-20,"Maersk",12.5,2024-02-05,2024-02-07,Delivered
PO-2024-0002,Air,2024-01-22,"DHL Logistics",0.8,2024-01-25,2024-01-25,Delivered
```

---

### 6. **invoices.csv** (Optional)

Invoice and payment data. One row per invoice.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **po_number** | Text | Yes | Must match a PO number |
| **supplier_name** | Text | Yes | Must match a supplier name |
| **invoice_date** | Date | Yes | Invoice issue date (YYYY-MM-DD) |
| **due_date** | Date | Yes | Payment due date |
| **amount** | Number | Yes | Invoice amount in original currency (>= 0) |
| **currency_code** | Text | Yes | 3-letter currency code |
| invoice_number | Text | No | Unique invoice number (auto-generated if missing) |
| amount_usd | Number | No | Amount in USD (default: same as amount) |
| status | Text | No | Pending, Approved, Paid, Disputed, Cancelled (default: Paid) |
| payment_date | Date | No | Actual payment date (leave blank if unpaid) |

#### Example
```csv
po_number,supplier_name,invoice_date,due_date,amount,currency_code,amount_usd,status,payment_date
PO-2024-0001,"AfroPipe Industries",2024-02-10,2024-03-12,8500000,NGN,5400,Paid,2024-03-10
PO-2024-0002,"Rhine Chemical GmbH",2024-02-01,2024-04-01,45000,EUR,48900,Paid,2024-03-25
```

---

### 7. **esg_assessments.csv** (Optional)

ESG (Environmental, Social, Governance) scores per supplier.

#### Columns

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| **supplier_name** | Text | Yes | Must match a supplier name |
| **assessment_date** | Date | Yes | Assessment date (YYYY-MM-DD) |
| **esg_rating** | Text | Yes | A, B, C, D, or F |
| carbon_intensity_score | Number | No | 0-100 (default: 50) |
| waste_management_score | Number | No | 0-100 (default: 50) |
| water_usage_score | Number | No | 0-100 (default: 50) |
| labor_practices_score | Number | No | 0-100 (default: 50) |
| health_safety_score | Number | No | 0-100 (default: 50) |
| community_impact_score | Number | No | 0-100 (default: 50) |
| ethics_compliance_score | Number | No | 0-100 (default: 50) |
| transparency_score | Number | No | 0-100 (default: 50) |
| board_diversity_score | Number | No | 0-100 (default: 50) |

Composite scores (env_composite, social_composite, governance_composite, esg_overall_score) are auto-calculated from individual scores.

#### Example
```csv
supplier_name,assessment_date,esg_rating,carbon_intensity_score,waste_management_score,labor_practices_score,ethics_compliance_score
"Rhine Chemical GmbH",2024-06-01,A,85,90,92,90
"AfroPipe Industries",2024-06-01,C,45,50,60,55
```

---

## Common Issues & Solutions

### "Missing required columns"
Check that your CSV has the exact column names (case-sensitive).
```
Correct:  supplier_name
Wrong:    Supplier Name, supplier_name_en, SupplierName
```

### "Country not found"
The country name must exist in the AEGIS reference data. Pre-loaded countries:
Nigeria, Germany, China, India, United States, United Kingdom, Brazil, South Africa, Turkey, South Korea, Japan, United Arab Emirates, Saudi Arabia, Ghana, Cameroon

### "supplier_name not found"
Ensure the supplier_name in purchase_orders.csv exactly matches suppliers.csv (case-sensitive, no extra spaces).

### "material_name not found"
Ensure the material_name in po_line_items.csv exactly matches materials.csv.

### "transport_mode invalid"
Shipment transport modes must be one of: Sea, Air, Rail, Road, Multimodal (case-sensitive, capitalized).

---

## Data Validation Rules

AEGIS enforces these rules during import:

1. **Suppliers**: lead_time_days > 0, currency_code must be valid, country must exist
2. **Materials**: standard_cost_usd >= 0, category required
3. **Purchase Orders**: order_date must be valid ISO date, total_amount >= 0, supplier must exist
4. **PO Line Items**: quantity > 0, unit_price >= 0, po_number and material_name must exist
5. **Shipments**: transport_mode must be Sea/Air/Rail/Road/Multimodal, po_number must exist
6. **Invoices**: amount >= 0, po_number and supplier_name must exist
7. **ESG**: esg_rating must be A/B/C/D/F, scores 0-100

**Validation Mode:** LENIENT — type mismatches are warnings, missing optional columns get defaults, errors halt import.

---

## Pipeline Behavior

After importing external data:

1. **Transaction Layer** (populated by external_data_loader.py):
   - suppliers, materials, purchase_orders, po_line_items
   - (optional) shipments, invoices, esg_assessments

2. **Warehouse Layer** (populated by populate_warehouse.py):
   - dim_date, dim_supplier (SCD Type 2), dim_material, dim_geography
   - fact_procurement, fact_esg

3. **Analytics Layer** (populated by run_aegis_pipeline.py):
   - supplier_scorecards (MCDA), risk_assessments, concentration_analysis, simulation_runs

---

## Performance Notes

- **Scale:** AEGIS is optimized for 10-500 suppliers, 50-2,000 materials, 500-50,000 POs
- **Date Range:** Recommended 1-5 years of historical data
- **FX Rates:** The system generates realistic FX rate data via GBM simulation if not provided

For large datasets (>50K POs), consider running the pipeline in batches.

---

## Example: Complete Company Data Workflow

### Scenario: Import H1 2024 procurement data

**1. Prepare Files**
```
company_data\
  |- suppliers.csv           (25 suppliers)
  |- materials.csv           (100 materials)
  |- purchase_orders.csv     (3,000 POs from Jan-Jun 2024)
  |- po_line_items.csv       (8,000 line items)
  |- shipments.csv           (2,500 shipments)
  |- invoices.csv            (3,000 invoices)
  |- esg_assessments.csv     (25 ESG assessments)
```

**2. Import**
```powershell
python data_ingestion\external_data_loader.py --input-dir .\company_data
```

**3. Populate Warehouse & Run Analytics**
```powershell
python data_ingestion\populate_warehouse.py
python run_aegis_pipeline.py
```

**4. Launch & Analyze**
```powershell
streamlit run streamlit_app.py
```

Navigate to:
- **Executive Dashboard** — Spend trends, KPI cards
- **Supplier Scorecards** — MCDA scoring (TOPSIS/PROMETHEE/WSM)
- **Risk Radar** — 7-dimension risk heatmap
- **Monte Carlo Lab** — FX/lead-time simulation
- **Concentration Analysis** — HHI across 5 dimensions
- **Carbon Dashboard** — Scope 3 emissions by route/mode
- **Should-Cost** — Cost decomposition & leakage alerts
- **Working Capital** — DPO analysis & EPD optimizer
- **ESG Compliance** — Ratings & OECD due diligence
- **Scenario Planner** — Supplier switch / hedge / nearshore what-ifs
