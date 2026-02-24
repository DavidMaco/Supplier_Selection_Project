-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 00: MASTER DEPLOY SCRIPT
-- Run this script to create the entire AEGIS database from scratch
--
-- Usage:  mysql -u root -p < 00_MASTER_DEPLOY.sql
-- ═══════════════════════════════════════════════════════════════════

-- Drop & recreate
DROP DATABASE IF EXISTS aegis_procurement;

-- Phase 1: Reference / Lookup tables (incl. CREATE DATABASE)
SOURCE 01_create_reference_tables.sql;

-- Phase 2: Master data tables (suppliers, materials, contracts)
SOURCE 02_create_master_tables.sql;

-- Phase 3: Transaction tables (POs, shipments, inspections, invoices)
SOURCE 03_create_transaction_tables.sql;

-- Phase 4: Market data tables (FX, commodities, country risk)
SOURCE 04_create_market_tables.sql;

-- Phase 5: ESG & Compliance tables
SOURCE 05_create_esg_tables.sql;

-- Phase 6: Warehouse star schema (dimensions + facts)
SOURCE 06_create_warehouse.sql;

-- Phase 7: Analytics results tables (scorecards, risk, simulations)
SOURCE 07_create_analytics_tables.sql;

-- Phase 8: Audit & data quality logging
SOURCE 08_create_audit_tables.sql;

-- Phase 9: Seed reference data
SOURCE 09_seed_reference_data.sql;

-- Verify
SELECT 'AEGIS deployment complete!' AS status;
SELECT TABLE_NAME, TABLE_ROWS
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'aegis_procurement'
ORDER BY TABLE_NAME;
