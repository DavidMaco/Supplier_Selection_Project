-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 08: Audit & Data Quality Tables
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- AUDIT_LOG — change capture for critical tables
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name    VARCHAR(100)   NOT NULL,
    record_id     INT            NOT NULL,
    action        ENUM('INSERT','UPDATE','DELETE') NOT NULL,
    old_values    JSON,
    new_values    JSON,
    changed_by    VARCHAR(100)   DEFAULT 'system',
    changed_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_al_table (table_name, record_id),
    INDEX idx_al_ts    (changed_at)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- DATA_QUALITY_LOG — validation & integrity checks
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_log (
    dq_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    check_name      VARCHAR(200)  NOT NULL,
    check_type      ENUM('Completeness','Consistency','Timeliness',
                         'Accuracy','Uniqueness','Validity') NOT NULL,
    table_name      VARCHAR(100)  NOT NULL,
    column_name     VARCHAR(100),
    records_checked INT DEFAULT 0,
    records_failed  INT DEFAULT 0,
    failure_pct     DECIMAL(8,4) GENERATED ALWAYS AS (
        CASE WHEN records_checked > 0
             THEN (records_failed / records_checked) * 100
             ELSE 0
        END
    ) STORED,
    severity        ENUM('Info','Warning','Error','Critical') DEFAULT 'Warning',
    details         TEXT,
    run_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_dq_table (table_name, run_at),
    INDEX idx_dq_sev   (severity)
) ENGINE=InnoDB;
