-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 09: Seed Reference Data
-- Aligned to 01_create_reference_tables.sql column definitions
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- COUNTRIES — 15 strategically diverse nations
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO countries (country_name, iso_alpha2, iso_alpha3, region, sub_region,
                       income_group, wgi_governance_score, cpi_corruption_score,
                       fragile_state_index, grid_emission_factor, sanctions_flag)
VALUES
('Nigeria',       'NG','NGA','Africa','West Africa',       'Lower-Middle', 28.5, 24, 97.0, 0.420, FALSE),
('South Africa',  'ZA','ZAF','Africa','Southern Africa',   'Upper-Middle', 55.0, 43, 72.0, 0.950, FALSE),
('Ghana',         'GH','GHA','Africa','West Africa',       'Lower-Middle', 56.2, 43, 68.5, 0.350, FALSE),
('Kenya',         'KE','KEN','Africa','East Africa',       'Lower-Middle', 40.1, 31, 81.0, 0.310, FALSE),
('United Kingdom','GB','GBR','Europe','Northern Europe',    'High',         88.5, 73, 30.0, 0.230, FALSE),
('Germany',       'DE','DEU','Europe','Western Europe',     'High',         90.2, 79, 25.0, 0.380, FALSE),
('Netherlands',   'NL','NLD','Europe','Western Europe',     'High',         91.0, 82, 23.0, 0.400, FALSE),
('United States', 'US','USA','Americas','Northern America', 'High',         82.0, 69, 35.0, 0.420, FALSE),
('China',         'CN','CHN','Asia','Eastern Asia',         'Upper-Middle', 42.0, 45, 68.0, 0.560, FALSE),
('India',         'IN','IND','Asia','Southern Asia',        'Lower-Middle', 46.5, 40, 74.0, 0.710, FALSE),
('Japan',         'JP','JPN','Asia','Eastern Asia',         'High',         87.0, 73, 28.0, 0.470, FALSE),
('Turkey',        'TR','TUR','Asia','Western Asia',         'Upper-Middle', 35.0, 36, 75.0, 0.480, FALSE),
('Brazil',        'BR','BRA','Americas','South America',    'Upper-Middle', 45.0, 38, 66.0, 0.090, FALSE),
('UAE',           'AE','ARE','Asia','Western Asia',         'High',         68.0, 71, 45.0, 0.620, FALSE),
('Singapore',     'SG','SGP','Asia','South-Eastern Asia',   'High',         95.0, 85, 20.0, 0.420, FALSE);

-- ─────────────────────────────────────────────────────────
-- CURRENCIES — 10 with volatility classification
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO currencies (currency_code, currency_name, is_major, volatility_class)
VALUES
('USD', 'US Dollar',           TRUE,  'Low'),
('EUR', 'Euro',                TRUE,  'Low'),
('GBP', 'British Pound',       TRUE,  'Low'),
('NGN', 'Nigerian Naira',      FALSE, 'High'),
('ZAR', 'South African Rand',  FALSE, 'Medium'),
('CNY', 'Chinese Yuan',        FALSE, 'Low'),
('INR', 'Indian Rupee',        FALSE, 'Medium'),
('JPY', 'Japanese Yen',        TRUE,  'Low'),
('TRY', 'Turkish Lira',        FALSE, 'Extreme'),
('BRL', 'Brazilian Real',      FALSE, 'Medium');

-- ─────────────────────────────────────────────────────────
-- INDUSTRY_SECTORS — ISIC-aligned
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO industry_sectors (sector_code, sector_name, risk_profile)
VALUES
('B06', 'Oil & Gas',              'High'),
('C25', 'Manufacturing',          'Medium'),
('F41', 'Construction',           'Medium'),
('J62', 'IT & Technology',        'Low'),
('H49', 'Logistics & Transport',  'Medium'),
('M70', 'Professional Services',  'Low');

-- ─────────────────────────────────────────────────────────
-- PORTS — 12 global trade nodes
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO ports (port_name, port_code, country_id, port_type, latitude, longitude, avg_customs_days, congestion_risk)
VALUES
('Lagos (Apapa)',     'NGAPP', (SELECT country_id FROM countries WHERE iso_alpha2='NG'), 'Sea',
  6.4541,  3.3841, 14, 'High'),
('Lagos (Tin Can)',   'NGTIN', (SELECT country_id FROM countries WHERE iso_alpha2='NG'), 'Sea',
  6.4320,  3.3580, 12, 'High'),
('Durban',            'ZADUR', (SELECT country_id FROM countries WHERE iso_alpha2='ZA'), 'Sea',
 -29.8587, 31.0218, 5,  'Medium'),
('Tema',              'GHTEM', (SELECT country_id FROM countries WHERE iso_alpha2='GH'), 'Sea',
  5.6295, -0.0187, 8,  'Medium'),
('Mombasa',           'KEMBA', (SELECT country_id FROM countries WHERE iso_alpha2='KE'), 'Sea',
 -4.0435, 39.6682, 9,  'Medium'),
('Felixstowe',        'GBFXT', (SELECT country_id FROM countries WHERE iso_alpha2='GB'), 'Sea',
  51.9615, 1.3509, 2,  'Low'),
('Rotterdam',         'NLRTM', (SELECT country_id FROM countries WHERE iso_alpha2='NL'), 'Sea',
  51.9225, 4.4792, 1,  'Low'),
('Shanghai',          'CNSHA', (SELECT country_id FROM countries WHERE iso_alpha2='CN'), 'Sea',
  31.2304,121.4737, 3,  'Medium'),
('Mumbai (JNPT)',     'INNSA', (SELECT country_id FROM countries WHERE iso_alpha2='IN'), 'Sea',
  18.9500, 72.9500, 6,  'Medium'),
('Houston',           'USHOU', (SELECT country_id FROM countries WHERE iso_alpha2='US'), 'Sea',
  29.7604,-95.3698, 2,  'Low'),
('Jebel Ali',         'AEJEA', (SELECT country_id FROM countries WHERE iso_alpha2='AE'), 'Sea',
  25.0143, 55.0600, 2,  'Low'),
('Singapore',         'SGSIN', (SELECT country_id FROM countries WHERE iso_alpha2='SG'), 'Multimodal',
  1.2655, 103.8222, 1,  'Low');

-- ─────────────────────────────────────────────────────────
-- INCOTERMS — ICC 2020
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO incoterms (incoterm_code, incoterm_name, risk_transfer_point, buyer_bears_freight, buyer_bears_insurance)
VALUES
('EXW', 'Ex Works',               'Seller premises',          TRUE,  TRUE),
('FOB', 'Free On Board',          'On board vessel at port',  TRUE,  TRUE),
('CIF', 'Cost Insurance Freight', 'On board vessel at port',  FALSE, FALSE),
('CFR', 'Cost and Freight',       'On board vessel at port',  FALSE, TRUE),
('DDP', 'Delivered Duty Paid',    'Buyer premises',           FALSE, FALSE),
('DAP', 'Delivered at Place',     'Named destination',        FALSE, TRUE),
('FCA', 'Free Carrier',           'Named carrier point',      TRUE,  TRUE);

-- ─────────────────────────────────────────────────────────
-- COMPLIANCE_FRAMEWORKS
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO compliance_frameworks (framework_code, framework_name, jurisdiction, effective_date, penalty_description)
VALUES
('UKMSA',  'UK Modern Slavery Act',   'United Kingdom', '2015-10-29', 'Injunction, unlimited fines for non-compliance with transparency statements.'),
('EUCSRD', 'EU CSRD',                 'European Union', '2024-01-01', 'Administrative fines under national transposition law.'),
('OECDDD', 'OECD Due Diligence',      'International',  '2018-05-30', 'Non-binding guidance; reputational risk for non-adherence.'),
('NCDMB',  'Nigerian NCDMB',          'Nigeria',        '2010-04-22', 'Contract rejection, licence revocation for non-compliance with local content.'),
('DF1502', 'US Dodd-Frank Sec 1502',  'United States',  '2012-08-22', 'SEC enforcement actions for conflict minerals non-disclosure.'),
('ISO204', 'ISO 20400',               'International',  '2017-04-01', 'Voluntary standard; no regulatory penalty.');

-- ─────────────────────────────────────────────────────────
-- CERTIFICATIONS_CATALOG
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO certifications_catalog (cert_code, cert_name, cert_body, category, validity_years)
VALUES
('ISO9001',   'ISO 9001 Quality Management',        'ISO',    'Quality',       3),
('ISO14001',  'ISO 14001 Environmental Management',  'ISO',    'Environmental', 3),
('ISO45001',  'ISO 45001 Occupational H&S',          'ISO',    'Safety',        3),
('ISO27001',  'ISO 27001 Information Security',       'ISO',    'Security',      3),
('SA8000',    'SA8000 Social Accountability',         'SAI',    'Social',        3),
('OHSAS',     'OHSAS 18001 (Legacy H&S)',            'BSI',    'Safety',        3),
('APIQ1',     'API Q1 Oil & Gas Quality',            'API',    'Industry',      3),
('ASME',      'ASME Boiler & Pressure Vessel',       'ASME',   'Industry',      5),
('CEMARK',    'CE Marking',                           'EU',     'Quality',       0),
('LEED',      'LEED Green Building',                  'USGBC',  'Environmental', 0);

-- ─────────────────────────────────────────────────────────
-- RISK_CATEGORIES — 7 dimensions with default weights
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO risk_categories (category_code, category_name, description, default_weight)
VALUES
('FIN',  'Financial',     'Supplier financial stability, credit risk, liquidity',         0.200),
('OPS',  'Operational',   'Delivery reliability, capacity constraints, quality issues',    0.200),
('GEO',  'Geopolitical',  'Country risk, sanctions, political instability',                0.150),
('COMP', 'Compliance',    'Regulatory adherence, modern slavery, anti-bribery',            0.150),
('CONC', 'Concentration', 'Single-source dependency, geographic concentration',            0.100),
('ESG',  'ESG',           'Environmental, social, governance performance',                 0.100),
('CYB',  'Cyber',         'IT security posture, data protection, incident history',        0.100);

-- ─────────────────────────────────────────────────────────
-- EMISSION_FACTORS — GHG Protocol Scope 3 Category 4
-- ─────────────────────────────────────────────────────────
INSERT IGNORE INTO emission_factors (transport_mode, factor_kgco2_per_tonne_km, source, valid_from)
VALUES
('Sea',   0.016000, 'GLEC Framework / IMO Fourth GHG Study 2020', '2020-01-01'),
('Air',   0.602000, 'GLEC Framework / ICAO Carbon Calculator',     '2020-01-01'),
('Rail',  0.028000, 'GLEC Framework / UIC',                         '2020-01-01'),
('Road',  0.062000, 'GLEC Framework / HBEFA',                       '2020-01-01');
