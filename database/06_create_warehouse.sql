-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 06: Warehouse Layer (Star Schema)
-- dim_date, dim_supplier, dim_material, dim_geography,
-- fact_procurement, fact_esg
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- DIM_DATE (2022-01-01 → 2028-12-31)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INT PRIMARY KEY,
    full_date       DATE        NOT NULL UNIQUE,
    `year`          INT         NOT NULL,
    `quarter`       INT         NOT NULL,
    `month`         INT         NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    week_of_year    INT         NOT NULL,
    day_of_week     INT         NOT NULL,
    day_name        VARCHAR(20) NOT NULL,
    is_weekend      BOOLEAN     NOT NULL,
    is_month_end    BOOLEAN     NOT NULL,
    fiscal_year     INT         NOT NULL,
    fiscal_quarter  INT         NOT NULL
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- DIM_SUPPLIER (SCD Type 2)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_key   INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id    INT          NOT NULL,
    supplier_name  VARCHAR(255) NOT NULL,
    country_name   VARCHAR(100),
    region         VARCHAR(50),
    sector_name    VARCHAR(150),
    tier_level     VARCHAR(20),
    currency_code  CHAR(3),
    is_iso9001     BOOLEAN,
    esg_rating     CHAR(1),
    risk_tier      VARCHAR(20),
    scd_valid_from DATE NOT NULL,
    scd_valid_to   DATE,
    scd_is_current BOOLEAN DEFAULT TRUE,

    INDEX idx_dsup_current (scd_is_current)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- DIM_MATERIAL
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_material (
    material_key    INT AUTO_INCREMENT PRIMARY KEY,
    material_id     INT          NOT NULL,
    material_name   VARCHAR(255) NOT NULL,
    category        VARCHAR(100),
    sub_category    VARCHAR(100),
    commodity_group VARCHAR(100),
    standard_cost_usd DECIMAL(15,2),
    is_critical     BOOLEAN
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- DIM_GEOGRAPHY
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_geography (
    geo_key        INT AUTO_INCREMENT PRIMARY KEY,
    country_id     INT NOT NULL,
    country_name   VARCHAR(100),
    region         VARCHAR(50),
    sub_region     VARCHAR(80),
    income_group   VARCHAR(20),
    sanctions_flag BOOLEAN
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- FACT_PROCUREMENT — grain: one PO line item
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_procurement (
    procurement_key   INT AUTO_INCREMENT PRIMARY KEY,
    date_key          INT NOT NULL,
    supplier_key      INT NOT NULL,
    material_key      INT NOT NULL,
    geo_key           INT NOT NULL,
    po_id             INT NOT NULL,
    contract_id       INT,
    quantity          DECIMAL(15,2),
    unit_price_usd    DECIMAL(15,4),
    line_total_usd    DECIMAL(18,2),
    landed_cost_usd   DECIMAL(18,2),
    fx_rate_applied   DECIMAL(18,6),
    standard_cost_usd DECIMAL(15,2),
    cost_variance_usd DECIMAL(15,2),
    cost_variance_pct DECIMAL(8,2),
    lead_time_days    INT,
    delay_days        INT,
    on_time_flag      BOOLEAN,
    defect_flag       BOOLEAN,
    is_maverick       BOOLEAN,
    co2e_kg           DECIMAL(12,2),

    INDEX idx_fp_date     (date_key),
    INDEX idx_fp_supplier (supplier_key),
    INDEX idx_fp_material (material_key),
    INDEX idx_fp_geo      (geo_key)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- FACT_ESG — grain: one assessment
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_esg (
    esg_key          INT AUTO_INCREMENT PRIMARY KEY,
    date_key         INT NOT NULL,
    supplier_key     INT NOT NULL,
    env_score        DECIMAL(5,2),
    social_score     DECIMAL(5,2),
    governance_score DECIMAL(5,2),
    overall_score    DECIMAL(5,2),
    esg_rating       CHAR(1),
    compliance_gap_count INT DEFAULT 0
) ENGINE=InnoDB;
