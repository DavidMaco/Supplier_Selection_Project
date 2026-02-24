-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 04: Market Data Tables
-- FX Rates, Commodity Prices, Country Risk Indices
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- FX RATES (daily)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fx_rates (
    fx_rate_id  INT AUTO_INCREMENT PRIMARY KEY,
    currency_id INT  NOT NULL,
    rate_date   DATE NOT NULL,
    rate_to_usd DECIMAL(18,6) NOT NULL CHECK (rate_to_usd > 0),
    source      VARCHAR(50) DEFAULT 'API',

    CONSTRAINT fk_fx_currency FOREIGN KEY (currency_id) REFERENCES currencies(currency_id),
    UNIQUE KEY uq_fx (currency_id, rate_date),
    INDEX idx_fx_date (rate_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- COMMODITY PRICES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS commodity_prices (
    price_id        INT AUTO_INCREMENT PRIMARY KEY,
    commodity_group VARCHAR(100) NOT NULL,
    price_date      DATE         NOT NULL,
    price_usd       DECIMAL(15,4) NOT NULL,
    unit            VARCHAR(20)  NOT NULL,
    source          VARCHAR(100),

    UNIQUE KEY uq_cp (commodity_group, price_date),
    INDEX idx_cp_commodity (commodity_group),
    INDEX idx_cp_date      (price_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- COUNTRY RISK INDICES (annual snapshot)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS country_risk_indices (
    index_id                   INT AUTO_INCREMENT PRIMARY KEY,
    country_id                 INT NOT NULL,
    assessment_year            INT NOT NULL,
    political_stability_score  DECIMAL(5,2),
    regulatory_quality_score   DECIMAL(5,2),
    rule_of_law_score          DECIMAL(5,2),
    control_of_corruption_score DECIMAL(5,2),
    ease_of_business_rank      INT,
    logistics_performance_index DECIMAL(4,2),
    composite_country_risk     DECIMAL(5,2),

    CONSTRAINT fk_cri_country FOREIGN KEY (country_id) REFERENCES countries(country_id),
    UNIQUE KEY uq_cri (country_id, assessment_year)
) ENGINE=InnoDB;
