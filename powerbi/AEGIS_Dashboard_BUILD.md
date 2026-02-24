# AEGIS Power BI Dashboard — Build Guide

> Step-by-step instructions for building the AEGIS procurement dashboard in Power BI Desktop.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Power BI Desktop | June 2024 or later |
| MySQL ODBC Connector | 8.0+ ([download](https://dev.mysql.com/downloads/connector/odbc/)) |
| AEGIS database | `aegis_procurement` with pipeline completed |

---

## 1. Connect to MySQL

1. Open **Power BI Desktop → Get Data → MySQL database**.
2. Enter connection details:
   - Server: `localhost` (or your host)
   - Database: `aegis_procurement`
3. Authenticate with your MySQL credentials.
4. Alternatively, use **ODBC** connector with the connection string in `PowerQuery_Connections.pq`.

---

## 2. Import Tables

Import the following tables in order. Use **Import** mode for best performance (DirectQuery supported for real-time needs).

### Star Schema (Core)

| Table | Type | Description |
|-------|------|-------------|
| `fact_procurement` | Fact | PO line items at USD, one row per line |
| `fact_esg` | Fact | ESG assessments per supplier |
| `dim_date` | Dimension | Calendar spine (2024–2030) |
| `dim_supplier` | Dimension | Supplier master with scores & tiers |
| `dim_material` | Dimension | Material master with categories |
| `dim_geography` | Dimension | Country geography with regions |

### Analytics Results

| Table | Description |
|-------|-------------|
| `supplier_scorecards` | MCDA composite scores |
| `risk_assessments` | Multi-dimensional risk scores |
| `concentration_analysis` | HHI and concentration metrics |
| `esg_assessments` | ESG composite scores |
| `country_risk_indices` | Geopolitical risk by country |

### Reference / Supporting

| Table | Description |
|-------|-------------|
| `fx_rates` | Daily FX rates (USD base) |
| `commodity_prices` | Material commodity price history |
| `suppliers` | Source supplier data |
| `purchase_orders` | PO headers |
| `po_line_items` | PO line detail |
| `invoices` | Invoice records |
| `shipments` | Logistics data |

---

## 3. Define Relationships

Create the following relationships in the **Model** view:

```
fact_procurement[date_key]       →  dim_date[date_key]         (Many:1)
fact_procurement[supplier_key]   →  dim_supplier[supplier_key]  (Many:1)
fact_procurement[material_key]   →  dim_material[material_key]  (Many:1)
fact_procurement[geography_key]  →  dim_geography[geo_key]      (Many:1)

fact_esg[supplier_key]           →  dim_supplier[supplier_key]  (Many:1)

supplier_scorecards[supplier_id] →  suppliers[supplier_id]      (Many:1)
risk_assessments[supplier_id]    →  suppliers[supplier_id]      (Many:1)
esg_assessments[supplier_id]     →  suppliers[supplier_id]      (Many:1)
```

- Use **single-direction** cross-filtering by default.
- Enable bi-directional only where visuals specifically require it.

---

## 4. Apply Theme

1. Go to **View → Themes → Browse for themes**.
2. Select `powerbi/AEGIS_Theme.json`.
3. The Tableau-10 palette and typography will apply automatically.

---

## 5. Create DAX Measures

Open `DAX_Measures.md` and create each measure in a **Measures** table:

1. Right-click in Fields pane → **New Table** → `Measures = ROW("x", 0)`.
2. Hide the dummy column.
3. Create each measure from the reference document.

### Priority Measures (create first)

- `Total Spend`
- `On-Time Delivery %`
- `Defect Rate`
- `Avg ESG Score`
- `Top Supplier Share`
- `Supplier HHI`
- `Maverick Spend %`

---

## 6. Build Report Pages

### Page 1: Executive Summary
- **Layout**: 4 KPI cards top row + trend line + tier donut
- **Visuals**:
  - Card: `Total Spend`, `Distinct Suppliers`, `On-Time Delivery %`, `Avg ESG Score`
  - Line chart: `Total Spend` by `dim_date[year_month]`
  - Donut chart: `Total Spend` by `dim_supplier[tier]`
  - Table: Top 5 suppliers by spend

### Page 2: Supplier Scorecard
- **Layout**: Matrix with conditional formatting + radar chart
- **Visuals**:
  - Matrix: `supplier_scorecards` with heatmap formatting on score columns
  - Radar/spider chart (custom visual): quality, delivery, cost, ESG, risk dimensions
  - Slicer: Supplier tier, Category

### Page 3: Risk Heatmap
- **Layout**: Risk matrix + treemap
- **Visuals**:
  - Matrix: Supplier × risk dimension with conditional formatting (Red/Amber/Green)
  - Treemap: `risk_assessments` by `risk_tier`
  - Map: Country risk overlay using `country_risk_indices`
  - Card: `At-Risk Suppliers`

### Page 4: Spend Analytics
- **Layout**: Waterfall + decomposition tree + map
- **Visuals**:
  - Waterfall chart: Spend change by category YoY
  - Decomposition tree: Drill from total spend → category → supplier → material
  - Filled map: Spend by `dim_geography[country_name]`
  - Card: `Maverick Spend %`

### Page 5: Quality Tracker
- **Layout**: Trend lines + Pareto chart
- **Visuals**:
  - Line chart: `Defect Rate` over time
  - Pareto chart: Quality incidents by supplier (bar + cumulative line)
  - Card: `Quality Incidents`, `On-Time Delivery %`

### Page 6: ESG Dashboard
- **Layout**: Gauges + scatter + compliance matrix
- **Visuals**:
  - Gauge charts: Environmental, Social, Governance scores
  - Scatter plot: ESG Score vs Spend (bubble = carbon)
  - Matrix: Supplier × compliance framework status
  - Card: `ESG A/B Suppliers`, `Compliance Rate`

### Page 7: Carbon Footprint
- **Layout**: Map + stacked bar
- **Visuals**:
  - Filled map: Carbon by supplier country
  - Stacked bar: Carbon by transport mode
  - Line chart: `Carbon Intensity` trend
  - Card: `Total Carbon (tonnes)`

### Page 8: Working Capital
- **Layout**: Aging waterfall + DPO trend
- **Visuals**:
  - Waterfall: Invoice aging buckets (0–30, 31–60, 61–90, 90+)
  - Line chart: `Days Payable Outstanding` trend
  - Table: Overdue invoices by supplier
  - Card: `Overdue Invoices Amount`

### Page 9: Concentration Analysis
- **Layout**: HHI gauge + treemap + sunburst
- **Visuals**:
  - Gauge: `Supplier HHI` (thresholds: <1500 green, 1500–2500 amber, >2500 red)
  - Treemap: Spend share by supplier
  - Sunburst (custom visual): Category → Supplier → Material hierarchy
  - Card: `Top Supplier Share`

### Page 10: Scenario Planning
- **Layout**: What-if parameter sliders + comparison table
- **Visuals**:
  - What-If parameters: FX rate change, demand shift, lead time delta
  - Clustered bar: Scenario comparison (baseline vs modified)
  - Table: Scenario results with delta columns
  - Card: Impact summary

---

## 7. Publish

1. Save as `AEGIS_Dashboard.pbix` in this directory.
2. **Publish** to Power BI Service workspace.
3. Configure **Scheduled Refresh** (daily recommended).
4. Set up **Row-Level Security** if multi-tenant access is needed.

---

## Tips

- Use **Bookmarks** for toggling between supplier detail and overview.
- Use **Drillthrough** from any supplier card to the Scorecard page.
- Enable **Q&A** visual on Executive Summary for natural language queries.
- Set `dim_date` as the **Date table** in Model view for time intelligence.
