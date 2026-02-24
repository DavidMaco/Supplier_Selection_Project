# AEGIS — Power BI Setup Guide

> End-to-end instructions for connecting Power BI to the AEGIS procurement warehouse.

---

## 1. Install MySQL ODBC Connector

Power BI's native MySQL connector requires the MySQL ODBC driver.

1. Download **MySQL Connector/ODBC 8.0** from [dev.mysql.com](https://dev.mysql.com/downloads/connector/odbc/).
2. Install the **64-bit** version (matches Power BI Desktop architecture).
3. Restart Power BI Desktop after installation.

---

## 2. Verify Database is Ready

Before connecting Power BI, ensure the AEGIS pipeline has been run:

```powershell
cd aegis-procurement
.\.venv\Scripts\activate
python run_aegis_pipeline.py --steps all
```

Verify key tables are populated:

```sql
SELECT 'fact_procurement' AS tbl, COUNT(*) AS rows FROM fact_procurement
UNION ALL
SELECT 'dim_supplier',     COUNT(*) FROM dim_supplier
UNION ALL
SELECT 'dim_date',         COUNT(*) FROM dim_date
UNION ALL
SELECT 'supplier_scorecards', COUNT(*) FROM supplier_scorecards;
```

---

## 3. Connect Power BI to MySQL

### Option A: Native MySQL Connector

1. **Get Data** → **MySQL database**
2. Server: `localhost` (or your MySQL host IP)
3. Database: `aegis_procurement`
4. Data Connectivity: **Import** (recommended) or **DirectQuery**
5. Enter MySQL credentials when prompted

### Option B: ODBC Data Source

1. Open **ODBC Data Source Administrator (64-bit)** on Windows
2. Add a **System DSN** with:
   - Driver: `MySQL ODBC 8.0 Unicode Driver`
   - Data Source Name: `AEGIS_Procurement`
   - TCP/IP Server: `localhost`
   - Port: `3306`
   - Database: `aegis_procurement`
3. In Power BI: **Get Data → ODBC** → select `AEGIS_Procurement`

### Option C: Use Provided Power Query Scripts

1. **Get Data → Blank Query**
2. Open **Advanced Editor**
3. Paste the relevant query from `powerbi/PowerQuery_Connections.pq`
4. Repeat for each table

---

## 4. Import Tables

Import tables in this order for clean relationship detection:

1. **Dimensions first**: `dim_date`, `dim_supplier`, `dim_material`, `dim_geography`
2. **Facts**: `fact_procurement`, `fact_esg`
3. **Analytics**: `supplier_scorecards`, `risk_assessments`, `concentration_analysis`, `esg_assessments`
4. **Reference** (optional): `fx_rates`, `commodity_prices`, `country_risk_indices`

---

## 5. Configure Relationships

Power BI may auto-detect some relationships. Verify and create:

| From (Many) | To (One) | Key |
|-------------|----------|-----|
| fact_procurement | dim_date | date_key |
| fact_procurement | dim_supplier | supplier_key |
| fact_procurement | dim_material | material_key |
| fact_procurement | dim_geography | geography_key |
| fact_esg | dim_supplier | supplier_key |
| supplier_scorecards | suppliers | supplier_id |
| risk_assessments | suppliers | supplier_id |

Set all to **Single direction** cross-filtering.

---

## 6. Apply Theme & Measures

1. **View → Themes → Browse** → select `powerbi/AEGIS_Theme.json`
2. Create a **Measures table**: `Measures = ROW("x", 0)` → hide the column
3. Add DAX measures from `powerbi/DAX_Measures.md`
4. Follow the visual layout in `powerbi/AEGIS_Dashboard_BUILD.md`

---

## 7. Configure Date Table

1. Select `dim_date` in Model view
2. **Table tools → Mark as date table**
3. Select `full_date` as the date column
4. This enables DAX time intelligence functions (DATEADD, SAMEPERIODLASTYEAR, etc.)

---

## 8. Scheduled Refresh (Power BI Service)

After publishing to Power BI Service:

1. Install **Power BI Gateway** on a machine with MySQL access
2. Configure the gateway data source with MySQL credentials
3. Set refresh schedule (recommended: daily at 06:00)
4. Enable **Incremental Refresh** on `fact_procurement` by date range

---

## 9. Row-Level Security (Optional)

For multi-team access control:

```dax
-- Create role: Regional Manager
[dim_geography[region]] = USERPRINCIPALNAME()

-- Or by supplier tier
[dim_supplier[tier]] = "Strategic"
```

Configure role assignments in Power BI Service → Dataset → Security.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "MySQL connector not found" | Install MySQL ODBC 8.0 (64-bit) and restart Power BI |
| Empty tables after import | Run `python run_aegis_pipeline.py --steps all` first |
| Relationship errors | Check key columns match types (INT↔INT) |
| Slow refresh | Switch from DirectQuery to Import mode |
| FX/commodity tables too large | Apply date filter in Power Query (last 90 days) |
| Gateway connection fails | Verify MySQL allows remote connections (`bind-address = 0.0.0.0`) |
