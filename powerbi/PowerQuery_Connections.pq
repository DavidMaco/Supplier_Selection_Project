// AEGIS Power BI — Power Query M Connection Scripts
// Import these in Power BI Desktop → Transform Data → Advanced Editor
// Replace connection parameters as needed.

// ============================================================
// 1. MySQL Connection Parameters
// ============================================================
let
    _Server   = "localhost",
    _Database = "aegis_procurement",
    _Source   = MySQL.Database(_Server, _Database)
in
    _Source


// ============================================================
// 2. fact_procurement (Star Schema Fact)
// ============================================================
let
    Source     = MySQL.Database("localhost", "aegis_procurement"),
    fp_table  = Source{[Schema="aegis_procurement", Name="fact_procurement"]}[Data],
    TypedCols = Table.TransformColumnTypes(fp_table, {
        {"date_key",          Int64.Type},
        {"supplier_key",      Int64.Type},
        {"material_key",      Int64.Type},
        {"geography_key",     Int64.Type},
        {"total_value_usd",   Currency.Type},
        {"unit_price_usd",    Currency.Type},
        {"quantity",           Int64.Type},
        {"delay_days",         Int64.Type},
        {"is_maverick",        Int64.Type}
    })
in
    TypedCols


// ============================================================
// 3. dim_date (Calendar Dimension)
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    dd     = Source{[Schema="aegis_procurement", Name="dim_date"]}[Data],
    Typed  = Table.TransformColumnTypes(dd, {
        {"date_key",     Int64.Type},
        {"full_date",    type date},
        {"year",         Int64.Type},
        {"quarter",      Int64.Type},
        {"month",        Int64.Type},
        {"month_name",   type text},
        {"day_of_week",  Int64.Type},
        {"is_weekend",   Int64.Type},
        {"fiscal_year",  Int64.Type},
        {"fiscal_quarter", Int64.Type}
    })
in
    Typed


// ============================================================
// 4. dim_supplier
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    ds     = Source{[Schema="aegis_procurement", Name="dim_supplier"]}[Data],
    Typed  = Table.TransformColumnTypes(ds, {
        {"supplier_key",   Int64.Type},
        {"company_name",   type text},
        {"country",        type text},
        {"tier",           type text},
        {"risk_tier",      type text},
        {"latest_score",   type number}
    })
in
    Typed


// ============================================================
// 5. dim_material
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    dm     = Source{[Schema="aegis_procurement", Name="dim_material"]}[Data],
    Typed  = Table.TransformColumnTypes(dm, {
        {"material_key",  Int64.Type},
        {"material_name", type text},
        {"category",      type text},
        {"uom",           type text}
    })
in
    Typed


// ============================================================
// 6. dim_geography
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    dg     = Source{[Schema="aegis_procurement", Name="dim_geography"]}[Data],
    Typed  = Table.TransformColumnTypes(dg, {
        {"geo_key",        Int64.Type},
        {"country_code",   type text},
        {"country_name",   type text},
        {"region",         type text},
        {"sub_region",     type text},
        {"latitude",       type number},
        {"longitude",      type number}
    })
in
    Typed


// ============================================================
// 7. fact_esg
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    fe     = Source{[Schema="aegis_procurement", Name="fact_esg"]}[Data],
    Typed  = Table.TransformColumnTypes(fe, {
        {"supplier_key",      Int64.Type},
        {"composite_score",   type number},
        {"esg_rating",        type text},
        {"compliance_gap_count", Int64.Type},
        {"total_carbon_kg",   type number}
    })
in
    Typed


// ============================================================
// 8. supplier_scorecards
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    sc     = Source{[Schema="aegis_procurement", Name="supplier_scorecards"]}[Data]
in
    sc


// ============================================================
// 9. risk_assessments
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    ra     = Source{[Schema="aegis_procurement", Name="risk_assessments"]}[Data]
in
    ra


// ============================================================
// 10. concentration_analysis
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    ca     = Source{[Schema="aegis_procurement", Name="concentration_analysis"]}[Data]
in
    ca


// ============================================================
// 11. esg_assessments
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    ea     = Source{[Schema="aegis_procurement", Name="esg_assessments"]}[Data]
in
    ea


// ============================================================
// 12. country_risk_indices
// ============================================================
let
    Source = MySQL.Database("localhost", "aegis_procurement"),
    cri    = Source{[Schema="aegis_procurement", Name="country_risk_indices"]}[Data]
in
    cri


// ============================================================
// 13. fx_rates (filtered to last 90 days for performance)
// ============================================================
let
    Source   = MySQL.Database("localhost", "aegis_procurement"),
    fx      = Source{[Schema="aegis_procurement", Name="fx_rates"]}[Data],
    Recent  = Table.SelectRows(fx, each [rate_date] >= Date.AddDays(DateTime.Date(DateTime.LocalNow()), -90))
in
    Recent


// ============================================================
// 14. commodity_prices (filtered to last 90 days)
// ============================================================
let
    Source   = MySQL.Database("localhost", "aegis_procurement"),
    cp      = Source{[Schema="aegis_procurement", Name="commodity_prices"]}[Data],
    Recent  = Table.SelectRows(cp, each [price_date] >= Date.AddDays(DateTime.Date(DateTime.LocalNow()), -90))
in
    Recent
