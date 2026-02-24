# AEGIS Power BI — DAX Measures Reference

> All measures connect to the AEGIS star-schema warehouse via DirectQuery or Import.

---

## 1. Core Spend Measures

```dax
Total Spend =
    SUM(fact_procurement[total_value_usd])

Spend YoY Growth =
    VAR _CurrentYear = [Total Spend]
    VAR _PriorYear =
        CALCULATE([Total Spend],
            DATEADD(dim_date[full_date], -1, YEAR))
    RETURN
        DIVIDE(_CurrentYear - _PriorYear, _PriorYear, 0)

Average PO Value =
    AVERAGE(fact_procurement[total_value_usd])

Distinct Suppliers =
    DISTINCTCOUNT(fact_procurement[supplier_key])

Maverick Spend =
    CALCULATE([Total Spend],
        fact_procurement[is_maverick] = 1)

Maverick Spend % =
    DIVIDE([Maverick Spend], [Total Spend], 0)
```

## 2. Delivery & Quality Measures

```dax
On-Time Delivery % =
    DIVIDE(
        COUNTROWS(FILTER(fact_procurement,
            fact_procurement[delay_days] <= 0)),
        COUNTROWS(fact_procurement), 0)

Average Delay Days =
    AVERAGE(fact_procurement[delay_days])

Defect Rate =
    DIVIDE(
        SUM(fact_procurement[defect_qty]),
        SUM(fact_procurement[inspected_qty]), 0)

Quality Incidents =
    SUM(fact_procurement[incident_count])
```

## 3. ESG Measures

```dax
Avg ESG Score =
    AVERAGE(fact_esg[composite_score])

ESG A/B Suppliers =
    CALCULATE(
        DISTINCTCOUNT(fact_esg[supplier_key]),
        fact_esg[esg_rating] IN {"A", "B"})

Compliance Rate =
    DIVIDE(
        CALCULATE(COUNTROWS(fact_esg),
            fact_esg[compliance_gap_count] = 0),
        COUNTROWS(fact_esg), 0)

Total Carbon (tonnes) =
    DIVIDE(SUM(fact_esg[total_carbon_kg]), 1000, 0)

Carbon Intensity =
    DIVIDE([Total Carbon (tonnes)],
        [Total Spend] / 1000000, 0)
```

## 4. Financial Measures

```dax
Days Payable Outstanding =
    AVERAGEX(
        SUMMARIZE(fact_procurement,
            fact_procurement[supplier_key],
            "DPO", AVERAGE(fact_procurement[days_to_pay])),
        [DPO])

Landing Cost Variance =
    DIVIDE(
        SUM(fact_procurement[cost_variance_usd]),
        SUM(fact_procurement[total_value_usd]), 0)

Overdue Invoices Amount =
    CALCULATE(SUM(fact_procurement[total_value_usd]),
        fact_procurement[payment_status] = "Overdue")
```

## 5. Concentration Measures

```dax
Top Supplier Share =
    VAR _TopSupplier =
        TOPN(1,
            SUMMARIZE(fact_procurement,
                dim_supplier[company_name],
                "Spend", [Total Spend]),
            [Spend], DESC)
    RETURN
        DIVIDE(MAXX(_TopSupplier, [Spend]), [Total Spend], 0)

Supplier HHI =
    SUMX(
        ADDCOLUMNS(
            SUMMARIZE(fact_procurement,
                fact_procurement[supplier_key]),
            "Share", DIVIDE([Total Spend],
                CALCULATE([Total Spend], ALL(fact_procurement[supplier_key])))),
        [Share] ^ 2) * 10000
```

## 6. Scorecard Measures

```dax
Avg Supplier Score =
    AVERAGE(dim_supplier[latest_score])

Strategic Suppliers =
    CALCULATE(
        DISTINCTCOUNT(dim_supplier[supplier_key]),
        dim_supplier[tier] = "Strategic")

At-Risk Suppliers =
    CALCULATE(
        DISTINCTCOUNT(dim_supplier[supplier_key]),
        dim_supplier[risk_tier] IN {"High", "Critical"})
```

---

## Recommended Report Pages

| # | Page | Key Visuals |
|---|------|-------------|
| 1 | Executive Summary | KPI cards, spend trend, tier donut |
| 2 | Supplier Scorecard | Matrix with conditional formatting, radar |
| 3 | Risk Heatmap | Matrix (supplier × dimension), treemap |
| 4 | Spend Analytics | Waterfall, decomposition tree, map |
| 5 | Quality Tracker | Line trends, Pareto chart |
| 6 | ESG Dashboard | Gauge charts, scatter, compliance matrix |
| 7 | Carbon Footprint | Filled map, stacked bar by mode |
| 8 | Working Capital | Aging waterfall, DPO trend |
| 9 | Concentration | HHI gauge, treemap, sunburst |
| 10 | Scenario Results | Parameter table, what-if visuals |
