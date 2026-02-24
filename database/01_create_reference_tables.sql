-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 01: Reference Tables
-- Countries, Currencies, Sectors, Ports, Incoterms, Compliance,
-- Certifications, Risk Categories, Emission Factors
-- ═══════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS aegis_procurement
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- COUNTRIES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS countries (
    country_id           INT AUTO_INCREMENT PRIMARY KEY,
    country_name         VARCHAR(100) NOT NULL UNIQUE,
    iso_alpha2           CHAR(2)      NOT NULL UNIQUE,
    iso_alpha3           CHAR(3)      NOT NULL UNIQUE,
    region               VARCHAR(50)  NOT NULL,
    sub_region           VARCHAR(80),
    income_group         ENUM('High','Upper-Middle','Lower-Middle','Low') NOT NULL,
    wgi_governance_score DECIMAL(4,2),
    cpi_corruption_score INT CHECK (cpi_corruption_score BETWEEN 0 AND 100),
    fragile_state_index  DECIMAL(5,1),
    grid_emission_factor DECIMAL(10,4),
    sanctions_flag       BOOLEAN DEFAULT FALSE,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- CURRENCIES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS currencies (
    currency_id      INT AUTO_INCREMENT PRIMARY KEY,
    currency_code    CHAR(3)      NOT NULL UNIQUE,
    currency_name    VARCHAR(100) NOT NULL,
    is_major         BOOLEAN DEFAULT FALSE,
    volatility_class ENUM('Low','Medium','High','Extreme') DEFAULT 'Medium'
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- INDUSTRY SECTORS (ISIC-aligned)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS industry_sectors (
    sector_id            INT AUTO_INCREMENT PRIMARY KEY,
    sector_code          VARCHAR(10)  NOT NULL UNIQUE,
    sector_name          VARCHAR(150) NOT NULL,
    risk_profile         ENUM('Low','Medium','High','Critical') DEFAULT 'Medium',
    esg_materiality_notes TEXT
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- PORTS (UN/LOCODE)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ports (
    port_id          INT AUTO_INCREMENT PRIMARY KEY,
    port_name        VARCHAR(100) NOT NULL,
    port_code        VARCHAR(10)  UNIQUE,
    country_id       INT NOT NULL,
    port_type        ENUM('Sea','Air','Rail','Inland','Multimodal') NOT NULL,
    latitude         DECIMAL(9,6),
    longitude        DECIMAL(9,6),
    avg_customs_days INT DEFAULT 5,
    congestion_risk  ENUM('Low','Medium','High') DEFAULT 'Medium',
    CONSTRAINT fk_port_country FOREIGN KEY (country_id) REFERENCES countries(country_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- INCOTERMS (ICC 2020)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incoterms (
    incoterm_id          INT AUTO_INCREMENT PRIMARY KEY,
    incoterm_code        CHAR(3)      NOT NULL UNIQUE,
    incoterm_name        VARCHAR(100) NOT NULL,
    risk_transfer_point  VARCHAR(200),
    buyer_bears_freight  BOOLEAN NOT NULL,
    buyer_bears_insurance BOOLEAN NOT NULL
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- COMPLIANCE FRAMEWORKS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_frameworks (
    framework_id          INT AUTO_INCREMENT PRIMARY KEY,
    framework_code        VARCHAR(20)  NOT NULL UNIQUE,
    framework_name        VARCHAR(200) NOT NULL,
    jurisdiction          VARCHAR(100) NOT NULL,
    effective_date        DATE NOT NULL,
    penalty_description   TEXT,
    applies_to_description TEXT
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- CERTIFICATIONS CATALOG
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS certifications_catalog (
    cert_id        INT AUTO_INCREMENT PRIMARY KEY,
    cert_code      VARCHAR(30)  NOT NULL UNIQUE,
    cert_name      VARCHAR(200) NOT NULL,
    cert_body      VARCHAR(200),
    category       ENUM('Quality','Environmental','Social','Safety','Industry','Security') NOT NULL,
    validity_years INT DEFAULT 3
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- RISK CATEGORIES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_categories (
    category_id    INT AUTO_INCREMENT PRIMARY KEY,
    category_code  VARCHAR(20)  NOT NULL UNIQUE,
    category_name  VARCHAR(100) NOT NULL,
    description    TEXT,
    default_weight DECIMAL(4,3) NOT NULL CHECK (default_weight BETWEEN 0 AND 1)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- EMISSION FACTORS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS emission_factors (
    factor_id                  INT AUTO_INCREMENT PRIMARY KEY,
    transport_mode             ENUM('Sea','Air','Rail','Road') NOT NULL,
    factor_kgco2_per_tonne_km  DECIMAL(10,6) NOT NULL,
    source                     VARCHAR(200),
    valid_from                 DATE NOT NULL,
    valid_to                   DATE
) ENGINE=InnoDB;
