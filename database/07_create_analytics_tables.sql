-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 07: Analytics Results Tables
-- supplier_scorecards, risk_assessments, simulation_runs,
-- concentration_analysis
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- SUPPLIER_SCORECARDS — MCDA output per supplier per period
--   7 dimensions: cost, quality, delivery, risk, ESG,
--                 innovation, financial_health
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supplier_scorecards (
    scorecard_id      INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id       INT          NOT NULL,
    assessment_date   DATE         NOT NULL,
    period_label      VARCHAR(20)  NOT NULL COMMENT 'e.g. 2024-Q3',

    -- Raw dimension scores (0-100)
    cost_score        DECIMAL(6,2) NOT NULL,
    quality_score     DECIMAL(6,2) NOT NULL,
    delivery_score    DECIMAL(6,2) NOT NULL,
    risk_score        DECIMAL(6,2) NOT NULL,
    esg_score         DECIMAL(6,2) NOT NULL,
    innovation_score  DECIMAL(6,2) NOT NULL,
    financial_score   DECIMAL(6,2) NOT NULL,

    -- AHP/MCDA weights applied
    w_cost            DECIMAL(5,3) DEFAULT 0.250,
    w_quality         DECIMAL(5,3) DEFAULT 0.200,
    w_delivery        DECIMAL(5,3) DEFAULT 0.175,
    w_risk            DECIMAL(5,3) DEFAULT 0.150,
    w_esg             DECIMAL(5,3) DEFAULT 0.100,
    w_innovation      DECIMAL(5,3) DEFAULT 0.075,
    w_financial       DECIMAL(5,3) DEFAULT 0.050,

    -- Composite weighted score (0-100)
    composite_score   DECIMAL(6,2) NOT NULL,
    `rank`            INT,
    tier_recommendation VARCHAR(20),  -- Strategic / Preferred / Approved / Conditional / Blocked

    methodology       VARCHAR(20) DEFAULT 'TOPSIS'
                      COMMENT 'TOPSIS | PROMETHEE | WSM',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_sc_supplier (supplier_id, assessment_date),
    INDEX idx_sc_period   (period_label),
    INDEX idx_sc_rank     (`rank`),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- RISK_ASSESSMENTS — 7-dimension risk per supplier
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_assessments (
    risk_assessment_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id        INT          NOT NULL,
    assessment_date    DATE         NOT NULL,

    -- Dimension risk scores (0-100, higher = riskier)
    financial_risk     DECIMAL(6,2) NOT NULL,
    operational_risk   DECIMAL(6,2) NOT NULL,
    geopolitical_risk  DECIMAL(6,2) NOT NULL,
    compliance_risk    DECIMAL(6,2) NOT NULL,
    concentration_risk DECIMAL(6,2) NOT NULL,
    esg_risk           DECIMAL(6,2) NOT NULL,
    cyber_risk         DECIMAL(6,2) NOT NULL,

    -- Composite
    composite_risk     DECIMAL(6,2) NOT NULL,
    risk_tier          ENUM('Low','Medium','High','Critical') NOT NULL,
    mitigation_notes   TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ra_supplier (supplier_id, assessment_date),
    INDEX idx_ra_tier     (risk_tier),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- SIMULATION_RUNS — Monte Carlo / scenario output
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS simulation_runs (
    simulation_id    INT AUTO_INCREMENT PRIMARY KEY,
    run_date         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scenario_type    ENUM('FX','LeadTime','Disruption','CostScenario')
                     NOT NULL,
    scenario_label   VARCHAR(255) NOT NULL,
    n_simulations    INT          NOT NULL DEFAULT 10000,

    -- Result distribution
    mean_value       DECIMAL(18,4),
    median_value     DECIMAL(18,4),
    std_dev          DECIMAL(18,4),
    p5_value         DECIMAL(18,4),
    p25_value        DECIMAL(18,4),
    p75_value        DECIMAL(18,4),
    p95_value        DECIMAL(18,4),
    var_95           DECIMAL(18,4) COMMENT 'Value-at-Risk at 95% confidence',
    cvar_95          DECIMAL(18,4) COMMENT 'Conditional VaR at 95%',

    input_parameters JSON,
    created_by       VARCHAR(100) DEFAULT 'system',

    INDEX idx_sim_type (scenario_type, run_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- CONCENTRATION_ANALYSIS — HHI & dependency metrics
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS concentration_analysis (
    concentration_id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_date    DATE NOT NULL,
    dimension        ENUM('Supplier','Country','Currency','Material','Port')
                     NOT NULL,
    dimension_value  VARCHAR(255) NOT NULL COMMENT 'e.g. supplier name or country',
    spend_usd        DECIMAL(18,2),
    spend_share_pct  DECIMAL(8,4),
    hhi_index        DECIMAL(10,4),
    hhi_category     ENUM('Low','Moderate','High') NOT NULL,
    top_n_share_pct  DECIMAL(8,4) COMMENT 'Top-3 share',
    recommendation   TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ca_dim  (dimension, analysis_date),
    INDEX idx_ca_hhi  (hhi_category)
) ENGINE=InnoDB;
