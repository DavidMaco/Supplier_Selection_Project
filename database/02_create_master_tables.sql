-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 02: Master Data Tables
-- Suppliers, Supplier Certifications, Materials,
-- Supplier-Material Catalog, Contracts
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- SUPPLIERS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id              INT AUTO_INCREMENT PRIMARY KEY,
    supplier_code            VARCHAR(20)  NOT NULL UNIQUE,
    supplier_name            VARCHAR(255) NOT NULL,
    legal_entity_name        VARCHAR(300),
    country_id               INT NOT NULL,
    city                     VARCHAR(100),
    sector_id                INT NOT NULL,
    default_currency_id      INT NOT NULL,
    tier_level               ENUM('Strategic','Preferred','Approved','Conditional','Blocked') NOT NULL DEFAULT 'Approved',
    company_size             ENUM('Micro','Small','Medium','Large','Enterprise') DEFAULT 'Medium',
    year_established         INT CHECK (year_established BETWEEN 1800 AND 2030),
    employee_count           INT CHECK (employee_count > 0),
    annual_revenue_usd       DECIMAL(18,2),
    published_lead_time_days INT NOT NULL CHECK (published_lead_time_days > 0),
    lead_time_stddev_days    DECIMAL(8,2)  DEFAULT 0,
    defect_rate_pct          DECIMAL(5,2)  DEFAULT 0 CHECK (defect_rate_pct BETWEEN 0 AND 100),
    contract_margin_pct      DECIMAL(5,2),
    payment_terms_days       INT DEFAULT 30 CHECK (payment_terms_days >= 0),
    is_iso9001_certified     BOOLEAN DEFAULT FALSE,
    is_iso14001_certified    BOOLEAN DEFAULT FALSE,
    is_iso45001_certified    BOOLEAN DEFAULT FALSE,
    is_sa8000_certified      BOOLEAN DEFAULT FALSE,
    modern_slavery_declaration BOOLEAN DEFAULT FALSE,
    sanctions_screened_date  DATE,
    onboarding_date          DATE NOT NULL,
    last_audit_date          DATE,
    contact_name             VARCHAR(200),
    contact_email            VARCHAR(255),
    contact_phone            VARCHAR(50),
    status                   ENUM('Active','Suspended','Under Review','Deactivated') DEFAULT 'Active',
    notes                    TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_sup_country  FOREIGN KEY (country_id)          REFERENCES countries(country_id),
    CONSTRAINT fk_sup_sector   FOREIGN KEY (sector_id)           REFERENCES industry_sectors(sector_id),
    CONSTRAINT fk_sup_currency FOREIGN KEY (default_currency_id) REFERENCES currencies(currency_id),
    INDEX idx_sup_country (country_id),
    INDEX idx_sup_sector  (sector_id),
    INDEX idx_sup_tier    (tier_level),
    INDEX idx_sup_status  (status)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- SUPPLIER CERTIFICATIONS (many-to-many, time-tracked)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supplier_certifications (
    supplier_cert_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id      INT NOT NULL,
    cert_id          INT NOT NULL,
    cert_number      VARCHAR(100),
    issued_date      DATE NOT NULL,
    expiry_date      DATE NOT NULL,
    is_verified      BOOLEAN DEFAULT FALSE,
    verified_by      VARCHAR(200),
    document_url     VARCHAR(500),

    CONSTRAINT fk_sc_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_sc_cert     FOREIGN KEY (cert_id)     REFERENCES certifications_catalog(cert_id),
    UNIQUE KEY uq_sup_cert_date (supplier_id, cert_id, issued_date),
    INDEX idx_cert_expiry (expiry_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- MATERIALS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS materials (
    material_id       INT AUTO_INCREMENT PRIMARY KEY,
    material_code     VARCHAR(30)  NOT NULL UNIQUE,
    material_name     VARCHAR(255) NOT NULL,
    category          VARCHAR(100) NOT NULL,
    sub_category      VARCHAR(100),
    hs_code           VARCHAR(12),
    commodity_group   VARCHAR(100),
    standard_cost_usd DECIMAL(15,2) NOT NULL CHECK (standard_cost_usd > 0),
    unit_of_measure   VARCHAR(20) DEFAULT 'KG',
    is_critical       BOOLEAN DEFAULT FALSE,
    shelf_life_days   INT,
    storage_requirements VARCHAR(200),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_mat_category (category),
    INDEX idx_mat_hs       (hs_code)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- SUPPLIER-MATERIAL CATALOG
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supplier_material_catalog (
    catalog_id        INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id       INT NOT NULL,
    material_id       INT NOT NULL,
    quoted_unit_price DECIMAL(15,4) NOT NULL CHECK (quoted_unit_price > 0),
    currency_id       INT NOT NULL,
    min_order_qty     DECIMAL(15,2) DEFAULT 1,
    max_capacity_qty  DECIMAL(15,2),
    lead_time_days    INT NOT NULL CHECK (lead_time_days > 0),
    is_primary_source BOOLEAN DEFAULT FALSE,
    valid_from        DATE NOT NULL,
    valid_to          DATE,

    CONSTRAINT fk_cat_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_cat_material FOREIGN KEY (material_id) REFERENCES materials(material_id),
    CONSTRAINT fk_cat_currency FOREIGN KEY (currency_id) REFERENCES currencies(currency_id),
    UNIQUE KEY uq_smc (supplier_id, material_id, valid_from),
    INDEX idx_cat_material (material_id),
    INDEX idx_cat_supplier (supplier_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- CONTRACTS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contracts (
    contract_id                INT AUTO_INCREMENT PRIMARY KEY,
    contract_number            VARCHAR(50) NOT NULL UNIQUE,
    supplier_id                INT NOT NULL,
    contract_type              ENUM('Fixed Price','Cost Plus','Framework','Spot','Blanket') NOT NULL,
    start_date                 DATE NOT NULL,
    end_date                   DATE NOT NULL,
    total_value_usd            DECIMAL(18,2),
    currency_id                INT NOT NULL,
    incoterm_id                INT,
    payment_terms_days         INT DEFAULT 30,
    early_payment_discount_pct DECIMAL(4,2) DEFAULT 0,
    penalty_clause_pct         DECIMAL(4,2),
    fx_clause                  ENUM('Fixed Rate','Floating','Collar','None') DEFAULT 'Floating',
    status                     ENUM('Draft','Active','Expired','Terminated') DEFAULT 'Active',

    CONSTRAINT fk_con_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_con_currency FOREIGN KEY (currency_id) REFERENCES currencies(currency_id),
    CONSTRAINT fk_con_incoterm FOREIGN KEY (incoterm_id) REFERENCES incoterms(incoterm_id),
    INDEX idx_con_supplier (supplier_id),
    INDEX idx_con_dates    (start_date, end_date)
) ENGINE=InnoDB;
