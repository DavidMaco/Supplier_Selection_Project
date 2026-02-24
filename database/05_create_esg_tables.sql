-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 05: ESG & Compliance Tables
-- ESG Assessments, Compliance Checks, Carbon Estimates,
-- Due Diligence Records
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- ESG ASSESSMENTS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS esg_assessments (
    assessment_id            INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id              INT  NOT NULL,
    assessment_date          DATE NOT NULL,
    assessor                 VARCHAR(200),

    -- Environmental (0–100)
    carbon_intensity_score   INT CHECK (carbon_intensity_score   BETWEEN 0 AND 100),
    waste_management_score   INT CHECK (waste_management_score   BETWEEN 0 AND 100),
    water_usage_score        INT CHECK (water_usage_score        BETWEEN 0 AND 100),
    environmental_incidents  INT DEFAULT 0,
    env_composite            DECIMAL(5,2),

    -- Social (0–100)
    labor_practices_score    INT CHECK (labor_practices_score    BETWEEN 0 AND 100),
    health_safety_score      INT CHECK (health_safety_score      BETWEEN 0 AND 100),
    community_impact_score   INT CHECK (community_impact_score   BETWEEN 0 AND 100),
    modern_slavery_risk      ENUM('Low','Medium','High','Critical') DEFAULT 'Low',
    social_composite         DECIMAL(5,2),

    -- Governance (0–100)
    ethics_compliance_score  INT CHECK (ethics_compliance_score  BETWEEN 0 AND 100),
    transparency_score       INT CHECK (transparency_score       BETWEEN 0 AND 100),
    board_diversity_score    INT CHECK (board_diversity_score    BETWEEN 0 AND 100),
    governance_composite     DECIMAL(5,2),

    -- Overall
    esg_overall_score        DECIMAL(5,2),
    esg_rating               ENUM('A','B','C','D','F') NOT NULL,

    CONSTRAINT fk_esg_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    INDEX idx_esg_supplier (supplier_id),
    INDEX idx_esg_date     (assessment_date),
    INDEX idx_esg_rating   (esg_rating)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- COMPLIANCE CHECKS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_checks (
    check_id             INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id          INT  NOT NULL,
    framework_id         INT  NOT NULL,
    check_date           DATE NOT NULL,
    status               ENUM('Compliant','Partially Compliant',
                              'Non-Compliant','Not Assessed') NOT NULL,
    gaps_identified      TEXT,
    remediation_plan     TEXT,
    remediation_deadline DATE,
    evidence_url         VARCHAR(500),

    CONSTRAINT fk_cc_supplier  FOREIGN KEY (supplier_id)  REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_cc_framework FOREIGN KEY (framework_id) REFERENCES compliance_frameworks(framework_id),
    INDEX idx_cc_supplier  (supplier_id),
    INDEX idx_cc_framework (framework_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- CARBON ESTIMATES (per-shipment)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS carbon_estimates (
    estimate_id        INT AUTO_INCREMENT PRIMARY KEY,
    shipment_id        INT NOT NULL,
    transport_mode     ENUM('Sea','Air','Rail','Road') NOT NULL,
    distance_km        DECIMAL(10,1) NOT NULL,
    weight_tonnes      DECIMAL(10,3) NOT NULL,
    emission_factor_id INT,
    co2e_kg            DECIMAL(12,2) NOT NULL,
    calculation_method VARCHAR(50) DEFAULT 'GHG Protocol',

    CONSTRAINT fk_ce_shipment FOREIGN KEY (shipment_id)        REFERENCES shipments(shipment_id),
    CONSTRAINT fk_ce_factor   FOREIGN KEY (emission_factor_id) REFERENCES emission_factors(factor_id),
    INDEX idx_ce_shipment (shipment_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- DUE DILIGENCE RECORDS (OECD 6-step)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS due_diligence_records (
    dd_id              INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id        INT  NOT NULL,
    dd_date            DATE NOT NULL,
    step_1_policy      ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    step_2_identify    ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    step_3_mitigate    ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    step_4_verify      ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    step_5_communicate ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    step_6_remediate   ENUM('Done','Partial','Not Done') DEFAULT 'Not Done',
    overall_status     ENUM('Complete','In Progress','Overdue','Not Started') DEFAULT 'Not Started',
    findings           TEXT,

    CONSTRAINT fk_dd_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    INDEX idx_dd_supplier (supplier_id)
) ENGINE=InnoDB;
