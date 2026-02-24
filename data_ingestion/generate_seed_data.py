"""
AEGIS — Seed Data Generator
Generates realistic procurement data for 50 suppliers across 15 countries.

Volumes:
  - 50 suppliers, 80 materials, ~200 catalog entries, 40 contracts
  - 2,000 POs, ~6,000 line items, 1,800 shipments
  - 1,500 quality inspections, 120 incidents
  - ~2,000 invoices, 100 ESG assessments, 1,800 carbon estimates
  - FX rates via Geometric Brownian Motion (GBM) backward from anchor
"""

import random
import math
import datetime as dt
from decimal import Decimal

import numpy as np
from sqlalchemy import create_engine, text

import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ─── Reproducibility ─────────────────────────────────────────────────
np.random.seed(config.RANDOM_SEED)
random.seed(config.RANDOM_SEED)

ENGINE = create_engine(config.DATABASE_URL, echo=False)

# ─── Date helpers ────────────────────────────────────────────────────
START_DATE = dt.date(2022, 1, 1)
END_DATE = dt.date(2025, 12, 31)
DAYS_SPAN = (END_DATE - START_DATE).days


def rand_date(start=START_DATE, end=END_DATE):
    return start + dt.timedelta(days=random.randint(0, (end - start).days))


# ═════════════════════════════════════════════════════════════════════
#  HELPERS — fetch IDs from reference tables
# ═════════════════════════════════════════════════════════════════════
def fetch_ids(conn, table, id_col):
    rows = conn.execute(text(f"SELECT {id_col} FROM {table}")).fetchall()
    return [r[0] for r in rows]


def fetch_map(conn, table, key_col, val_col):
    rows = conn.execute(text(f"SELECT {key_col}, {val_col} FROM {table}")).fetchall()
    return {r[0]: r[1] for r in rows}


# ═════════════════════════════════════════════════════════════════════
#  1. SUPPLIERS (50)
# ═════════════════════════════════════════════════════════════════════
SUPPLIER_NAMES = [
    "AfroPipe Industries", "Lagos Steel Works", "NigerDelta Valves",
    "Sahel Equipment Co", "PortHarcourt Fabrication", "Gulf of Guinea Logistics",
    "Abuja Precision Eng", "Cape Industrial Supply", "Joburg Heavy Metals",
    "Durban Maritime Services", "Accra Engineering Group", "Tema Port Services",
    "Nairobi Industrial Co", "Mombasa Shipping Ltd", "London Procurement Hub",
    "Thames Engineering", "Sheffield Specialty Steel", "Rhine Industrial GmbH",
    "Berlin Automation AG", "München Precision Tools", "Rotterdam Marine Supply",
    "Amsterdam Tech Solutions", "Houston Oilfield Supply", "Texas Pipe & Fitting",
    "Delaware Chemicals Inc", "Shanghai Heavy Machinery", "Shenzhen Electronics",
    "Beijing Industrial Corp", "Mumbai Castings Ltd", "Delhi Automation Pvt",
    "Chennai Fabrication", "Tokyo Precision Eng", "Osaka Industrial Co",
    "Istanbul Marine Equipment", "Ankara Steel Works", "São Paulo Industrial",
    "Rio Engineering Group", "Dubai Supply Chain Co", "Abu Dhabi Logistics",
    "Singapore Precision Eng", "Zurich Quality Instruments", "Milan Fashion Textiles",
    "Warsaw Manufacturing Co", "Sydney Mining Equipment", "Toronto Industrial Supply",
    "Calgary Oil Tools", "Seoul Electronics", "Jakarta Marine Co",
    "Manila Engineering", "Casablanca Trade Co"
]

TIER_LEVELS = ["Strategic", "Preferred", "Approved", "Conditional", "Blocked"]
TIER_WEIGHTS = [0.10, 0.25, 0.40, 0.20, 0.05]

COMPANY_SIZES = ["Micro", "Small", "Medium", "Large", "Enterprise"]


def seed_suppliers(conn):
    country_ids = fetch_ids(conn, "countries", "country_id")
    sector_ids = fetch_ids(conn, "industry_sectors", "sector_id")
    currency_map = fetch_map(conn, "currencies", "currency_id", "currency_code")
    currency_ids = list(currency_map.keys())

    # Country-currency mapping (approximate)
    currencies_by_code = {v: k for k, v in currency_map.items()}
    country_to_code = fetch_map(conn, "countries", "country_id", "iso_alpha2")
    cc_map = {
        "NG": "NGN", "ZA": "ZAR", "GH": "USD", "KE": "USD",
        "GB": "GBP", "DE": "EUR", "NL": "EUR", "US": "USD",
        "CN": "CNY", "IN": "INR", "JP": "JPY", "TR": "TRY",
        "BR": "BRL", "AE": "USD", "SG": "USD",
    }
    country_currency = {}
    for cid, iso2 in country_to_code.items():
        cc = cc_map.get(iso2, "USD")
        country_currency[cid] = currencies_by_code.get(cc, currency_ids[0])

    suppliers = []
    for i, name in enumerate(SUPPLIER_NAMES):
        cid = country_ids[i % len(country_ids)]
        sid = sector_ids[i % len(sector_ids)]
        tier = random.choices(TIER_LEVELS, weights=TIER_WEIGHTS, k=1)[0]
        cur_id = country_currency.get(cid, random.choice(currency_ids))
        employees = random.randint(20, 5000)
        annual_rev = round(random.uniform(500_000, 500_000_000), 2)
        lead_time = random.randint(7, 90)
        lead_stddev = round(random.uniform(1, lead_time * 0.3), 1)
        defect = round(random.uniform(0, 8), 2)
        iso9001 = random.random() < 0.7
        iso14001 = random.random() < 0.4
        iso45001 = random.random() < 0.3
        sa8000 = random.random() < 0.15
        modern_slavery = random.random() < 0.6
        onboarded = rand_date(dt.date(2020, 1, 1), dt.date(2023, 12, 31))
        year_est = random.randint(1965, 2020)
        size_idx = min(4, employees // 1000)
        status = "Suspended" if tier == "Blocked" else "Active"

        suppliers.append({
            "supplier_code": f"SUP-{str(i + 1).zfill(4)}",
            "supplier_name": name,
            "country_id": cid,
            "sector_id": sid,
            "default_currency_id": cur_id,
            "tier_level": tier,
            "company_size": COMPANY_SIZES[size_idx],
            "year_established": year_est,
            "employee_count": employees,
            "annual_revenue_usd": annual_rev,
            "published_lead_time_days": lead_time,
            "lead_time_stddev_days": lead_stddev,
            "defect_rate_pct": defect,
            "payment_terms_days": random.choice([30, 45, 60, 90]),
            "is_iso9001_certified": iso9001,
            "is_iso14001_certified": iso14001,
            "is_iso45001_certified": iso45001,
            "is_sa8000_certified": sa8000,
            "modern_slavery_declaration": modern_slavery,
            "onboarding_date": onboarded,
            "status": status,
        })

    conn.execute(text("""
        INSERT INTO suppliers (supplier_code, supplier_name, country_id, sector_id,
            default_currency_id, tier_level, company_size, year_established,
            employee_count, annual_revenue_usd, published_lead_time_days,
            lead_time_stddev_days, defect_rate_pct, payment_terms_days,
            is_iso9001_certified, is_iso14001_certified, is_iso45001_certified,
            is_sa8000_certified, modern_slavery_declaration, onboarding_date, status)
        VALUES (:supplier_code, :supplier_name, :country_id, :sector_id,
            :default_currency_id, :tier_level, :company_size, :year_established,
            :employee_count, :annual_revenue_usd, :published_lead_time_days,
            :lead_time_stddev_days, :defect_rate_pct, :payment_terms_days,
            :is_iso9001_certified, :is_iso14001_certified, :is_iso45001_certified,
            :is_sa8000_certified, :modern_slavery_declaration, :onboarding_date, :status)
    """), suppliers)
    print(f"  ✓ {len(suppliers)} suppliers inserted")
    return fetch_ids(conn, "suppliers", "supplier_id")


# ═════════════════════════════════════════════════════════════════════
#  2. MATERIALS (80)
# ═════════════════════════════════════════════════════════════════════
MATERIAL_DEFS = [
    # (name, category, sub_category, commodity_group, hs_code, unit, std_cost, critical)
    ("Carbon Steel Pipe 6in",    "Steel",      "Pipe",       "Ferrous Metals", "7304.19", "meter",  85.0,  True),
    ("Carbon Steel Pipe 8in",    "Steel",      "Pipe",       "Ferrous Metals", "7304.19", "meter",  120.0, True),
    ("Carbon Steel Pipe 12in",   "Steel",      "Pipe",       "Ferrous Metals", "7304.19", "meter",  180.0, True),
    ("Stainless Steel Pipe 4in", "Steel",      "Pipe",       "Ferrous Metals", "7304.41", "meter",  210.0, True),
    ("Stainless Steel Plate",    "Steel",      "Plate",      "Ferrous Metals", "7219.11", "tonne",  3200.0,True),
    ("Carbon Steel Plate 10mm",  "Steel",      "Plate",      "Ferrous Metals", "7208.51", "tonne",  1800.0,False),
    ("Gate Valve 6in 150#",      "Valves",     "Gate",       "Flow Control",   "8481.80", "each",   450.0, True),
    ("Gate Valve 8in 300#",      "Valves",     "Gate",       "Flow Control",   "8481.80", "each",   780.0, True),
    ("Ball Valve 4in 150#",      "Valves",     "Ball",       "Flow Control",   "8481.80", "each",   320.0, False),
    ("Check Valve 6in",          "Valves",     "Check",      "Flow Control",   "8481.30", "each",   280.0, False),
    ("Butterfly Valve 12in",     "Valves",     "Butterfly",  "Flow Control",   "8481.80", "each",   520.0, False),
    ("Pressure Transmitter",     "Instruments","Pressure",   "Instrumentation","9026.20", "each",   1200.0,True),
    ("Temperature Transmitter",  "Instruments","Temperature","Instrumentation","9025.19", "each",   950.0, False),
    ("Flow Meter (Coriolis)",    "Instruments","Flow",       "Instrumentation","9026.10", "each",   4500.0,True),
    ("Level Transmitter",        "Instruments","Level",      "Instrumentation","9026.80", "each",   850.0, False),
    ("Control Valve 4in",        "Valves",     "Control",    "Flow Control",   "8481.80", "each",   2800.0,True),
    ("Control Valve 6in",        "Valves",     "Control",    "Flow Control",   "8481.80", "each",   3500.0,True),
    ("Flange Weld Neck 6in",     "Fittings",   "Flange",     "Ferrous Metals", "7307.91", "each",   95.0,  False),
    ("Flange Weld Neck 8in",     "Fittings",   "Flange",     "Ferrous Metals", "7307.91", "each",   140.0, False),
    ("Elbow 90deg 6in",          "Fittings",   "Elbow",      "Ferrous Metals", "7307.93", "each",   65.0,  False),
    ("Reducer 8x6in",            "Fittings",   "Reducer",    "Ferrous Metals", "7307.93", "each",   75.0,  False),
    ("Gasket Spiral Wound 6in",  "Seals",      "Gasket",     "Sealing",        "8484.10", "each",   25.0,  False),
    ("Bolt Set ASTM A193 B7",    "Fasteners",  "Bolt Set",   "Fasteners",      "7318.15", "set",    18.0,  False),
    ("Centrifugal Pump 50HP",    "Rotating",   "Pump",       "Rotating Equip", "8413.70", "each",   12000.0,True),
    ("Submersible Pump 25HP",    "Rotating",   "Pump",       "Rotating Equip", "8413.70", "each",   8500.0,False),
    ("Air Compressor 100HP",     "Rotating",   "Compressor", "Rotating Equip", "8414.80", "each",   25000.0,True),
    ("Heat Exchanger Shell-Tube","Vessels",     "HX",         "Static Equip",   "8419.50", "each",   35000.0,True),
    ("Pressure Vessel 5m3",      "Vessels",     "PV",         "Static Equip",   "7311.00", "each",   45000.0,True),
    ("Separator 3-Phase",        "Vessels",     "Separator",  "Static Equip",   "8421.29", "each",   55000.0,True),
    ("Electric Motor 75HP",      "Electrical",  "Motor",     "Electrical",      "8501.52", "each",   5500.0,False),
    ("Electric Motor 150HP",     "Electrical",  "Motor",     "Electrical",      "8501.52", "each",   9800.0,False),
    ("Transformer 500kVA",       "Electrical",  "Transformer","Electrical",     "8504.23", "each",   18000.0,True),
    ("Cable XLPE 3x95mm",        "Electrical",  "Cable",     "Electrical",      "8544.60", "meter",  35.0,  False),
    ("Cable Tray Hot Dip 300mm", "Electrical",  "Cable Tray","Electrical",      "7326.90", "meter",  28.0,  False),
    ("PLC Controller",           "Automation",  "PLC",       "Instrumentation", "8537.10", "each",   6500.0,True),
    ("HMI Panel 15in",           "Automation",  "HMI",       "Instrumentation", "8471.60", "each",   3200.0,False),
    ("Safety Relief Valve 4in",  "Valves",      "Safety",    "Flow Control",    "8481.40", "each",   1800.0,True),
    ("Fire Extinguisher CO2",    "Safety",      "FireProt",  "Safety",          "8424.10", "each",   95.0,  False),
    ("PPE Hard Hat",             "Safety",      "PPE",       "Safety",          "6506.10", "each",   15.0,  False),
    ("PPE Safety Boots",         "Safety",      "PPE",       "Safety",          "6402.91", "pair",   55.0,  False),
    ("Welding Rod E7018",        "Consumables", "Welding",   "Consumables",     "8311.10", "kg",     3.5,   False),
    ("Paint Epoxy Primer",       "Consumables", "Coating",   "Consumables",     "3208.10", "litre",  12.0,  False),
    ("Pipe Support Clamp 6in",   "Structural",  "Support",   "Structural",      "7308.90", "each",   18.0,  False),
    ("Structural Steel Beam HEA","Structural",  "Beam",      "Structural",      "7216.33", "tonne",  1600.0,False),
    ("Concrete Pre-Mix Grade 40","Civil",       "Concrete",  "Civil",           "3824.50", "m3",     120.0, False),
    ("Rebar 16mm Grade 60",      "Civil",       "Rebar",     "Civil",           "7214.20", "tonne",  900.0, False),
    ("Insulation Rockwool 50mm", "Insulation",  "Mineral",   "Insulation",      "6806.10", "m2",     22.0,  False),
    ("Insulation Cladding Al",   "Insulation",  "Cladding",  "Insulation",      "7606.12", "m2",     18.0,  False),
    ("Diesel Generator 500kW",   "Power",       "Generator", "Power Gen",       "8502.13", "each",   85000.0,True),
    ("Solar Panel 450W Mono",    "Power",       "Solar",     "Power Gen",       "8541.40", "each",   180.0, False),
    ("Chemical Corrosion Inhib", "Chemicals",   "Treatment", "Chemicals",       "3824.99", "litre",  45.0,  False),
    ("Chemical Demulsifier",     "Chemicals",   "Treatment", "Chemicals",       "3402.90", "litre",  65.0,  False),
    ("Scaffolding Tube 6m",      "Construction","Scaffold",  "Construction",    "7308.90", "each",   22.0,  False),
    ("Scaffolding Board",        "Construction","Scaffold",  "Construction",    "4418.90", "each",   8.0,   False),
    ("Crane Wire Rope 22mm",     "Lifting",     "Wire Rope", "Lifting",         "7312.10", "meter",  25.0,  False),
    ("Shackle Bow 25t",          "Lifting",     "Shackle",   "Lifting",         "7315.12", "each",   85.0,  False),
    ("Hydraulic Hose 3/4in",     "Hydraulics",  "Hose",      "Hydraulics",      "4009.42", "meter",  18.0,  False),
    ("Hydraulic Pump PV Series", "Hydraulics",  "Pump",      "Hydraulics",      "8413.50", "each",   4200.0,False),
    ("Pneumatic Actuator DA",    "Automation",  "Actuator",  "Instrumentation", "8412.31", "each",   2200.0,False),
    ("Filter Element Hydraulic", "Filtration",  "Element",   "Filtration",      "8421.23", "each",   120.0, False),
    ("Fuel Filter Assembly",     "Filtration",  "Assembly",  "Filtration",      "8421.23", "each",   85.0,  False),
    ("Bearing SKF 6310",         "Bearings",    "Ball",      "Bearings",        "8482.10", "each",   45.0,  False),
    ("Bearing Roller Tapered",   "Bearings",    "Roller",    "Bearings",        "8482.20", "each",   95.0,  False),
    ("Conveyor Belt 800mm",      "Conveyance",  "Belt",      "Material Handling","4010.19","meter",  65.0,  False),
    ("Coupling Flexible 4in",    "Rotating",    "Coupling",  "Rotating Equip",  "8483.60", "each",   350.0, False),
    ("Seal Mechanical 2in",      "Seals",       "Mechanical","Sealing",         "8484.20", "each",   680.0, False),
    ("HVAC Unit 50kW",           "HVAC",        "Unit",      "HVAC",            "8415.83", "each",   12000.0,False),
    ("Fire Alarm Panel",         "Safety",      "FireDet",   "Safety",          "8531.10", "each",   3500.0,False),
    ("UPS System 10kVA",         "Electrical",  "UPS",       "Electrical",      "8504.40", "each",   4500.0,False),
    ("Battery Li-Ion 100Ah",     "Electrical",  "Battery",   "Electrical",      "8507.60", "each",   250.0, False),
    ("Radar Level Gauge",        "Instruments", "Level",     "Instrumentation", "9015.80", "each",   5500.0,True),
    ("Gas Detector H2S",         "Safety",      "GasDet",    "Safety",          "9027.10", "each",   2800.0,True),
    ("Pig Launcher 12in",        "Pipeline",    "PIG",       "Pipeline",        "7326.90", "each",   15000.0,True),
    ("Cathodic Protection Anode", "Pipeline",   "CP",        "Pipeline",        "7508.10", "each",   350.0, False),
    ("Subsea Connector 6in",     "Subsea",      "Connector", "Subsea",          "7307.99", "each",   25000.0,True),
    ("ROV Manipulator Arm",      "Subsea",      "ROV",       "Subsea",          "8479.89", "each",   45000.0,True),
    ("Christmas Tree Valve",     "Wellhead",    "Tree",      "Wellhead",        "8481.80", "each",   120000.0,True),
    ("BOP Stack 15k",            "Wellhead",    "BOP",       "Wellhead",        "8481.80", "each",   350000.0,True),
    ("Drill Bit PDC 8.5in",     "Drilling",    "Bit",       "Drilling",        "8207.19", "each",   18000.0,True),
    ("Mud Pump Liner",           "Drilling",    "Pump Part", "Drilling",        "8413.91", "each",   2500.0,False),
]


def seed_materials(conn):
    materials = []
    for i, m in enumerate(MATERIAL_DEFS):
        materials.append({
            "material_code": f"MAT-{str(i + 1).zfill(4)}",
            "material_name": m[0], "category": m[1], "sub_category": m[2],
            "commodity_group": m[3], "hs_code": m[4], "unit_of_measure": m[5],
            "standard_cost_usd": m[6], "is_critical": m[7],
        })
    conn.execute(text("""
        INSERT INTO materials (material_code, material_name, category, sub_category,
            commodity_group, hs_code, unit_of_measure, standard_cost_usd, is_critical)
        VALUES (:material_code, :material_name, :category, :sub_category,
            :commodity_group, :hs_code, :unit_of_measure, :standard_cost_usd, :is_critical)
    """), materials)
    print(f"  ✓ {len(materials)} materials inserted")
    return fetch_ids(conn, "materials", "material_id")


# ═════════════════════════════════════════════════════════════════════
#  3. SUPPLIER_MATERIAL_CATALOG (~200 entries)
# ═════════════════════════════════════════════════════════════════════
def seed_catalog(conn, supplier_ids, material_ids):
    catalog = []
    currency_ids = fetch_ids(conn, "currencies", "currency_id")
    std_costs = fetch_map(conn, "materials", "material_id", "standard_cost_usd")

    for sid in supplier_ids:
        n_materials = random.randint(2, 8)
        chosen = random.sample(material_ids, min(n_materials, len(material_ids)))
        for mid in chosen:
            base = float(std_costs.get(mid, 100))
            price = round(base * random.uniform(0.75, 1.35), 2)
            lead = random.randint(7, 120)
            moq = random.choice([1, 5, 10, 25, 50, 100])
            cur = random.choice(currency_ids)
            catalog.append({
                "supplier_id": sid, "material_id": mid,
                "quoted_unit_price": price, "currency_id": cur,
                "lead_time_days": lead, "min_order_qty": moq,
                "valid_from": rand_date(dt.date(2023, 1, 1), dt.date(2024, 6, 1)),
                "valid_to": rand_date(dt.date(2025, 1, 1), dt.date(2026, 12, 31)),
            })

    conn.execute(text("""
        INSERT INTO supplier_material_catalog
            (supplier_id, material_id, quoted_unit_price, currency_id,
             lead_time_days, min_order_qty, valid_from, valid_to)
        VALUES (:supplier_id, :material_id, :quoted_unit_price, :currency_id,
                :lead_time_days, :min_order_qty, :valid_from, :valid_to)
    """), catalog)
    print(f"  ✓ {len(catalog)} catalog entries inserted")
    return catalog


# ═════════════════════════════════════════════════════════════════════
#  4. CONTRACTS (40)
# ═════════════════════════════════════════════════════════════════════
CONTRACT_TYPES = ["Fixed Price", "Cost Plus", "Framework", "Spot", "Blanket"]
FX_CLAUSES = ["Fixed Rate", "Floating", "Collar", "None"]


def seed_contracts(conn, supplier_ids):
    incoterm_ids = fetch_ids(conn, "incoterms", "incoterm_id")
    currency_ids = fetch_ids(conn, "currencies", "currency_id")
    contracts = []
    chosen_suppliers = random.sample(supplier_ids, min(40, len(supplier_ids)))

    for i, sid in enumerate(chosen_suppliers):
        start = rand_date(dt.date(2023, 1, 1), dt.date(2024, 6, 1))
        end = start + dt.timedelta(days=random.choice([365, 730, 1095]))
        value = round(random.uniform(50_000, 5_000_000), 2)
        contracts.append({
            "contract_number": f"AEGIS-CTR-{str(i + 1).zfill(4)}",
            "supplier_id": sid,
            "contract_type": random.choice(CONTRACT_TYPES),
            "start_date": start, "end_date": end,
            "total_value_usd": value,
            "currency_id": random.choice(currency_ids),
            "incoterm_id": random.choice(incoterm_ids),
            "payment_terms_days": random.choice([30, 45, 60, 90]),
            "fx_clause": random.choice(FX_CLAUSES),
            "early_payment_discount_pct": random.choice([0, 0, 1.5, 2.0, 2.5]),
            "status": "Active",
        })

    conn.execute(text("""
        INSERT INTO contracts (contract_number, supplier_id, contract_type,
            start_date, end_date, total_value_usd, currency_id, incoterm_id,
            payment_terms_days, fx_clause, early_payment_discount_pct, status)
        VALUES (:contract_number, :supplier_id, :contract_type,
            :start_date, :end_date, :total_value_usd, :currency_id, :incoterm_id,
            :payment_terms_days, :fx_clause, :early_payment_discount_pct, :status)
    """), contracts)
    print(f"  ✓ {len(contracts)} contracts inserted")
    return fetch_ids(conn, "contracts", "contract_id")


# ═════════════════════════════════════════════════════════════════════
#  5. PURCHASE ORDERS (2,000) + PO LINE ITEMS (~6,000)
# ═════════════════════════════════════════════════════════════════════
PO_STATUSES = ["Draft", "Approved", "Shipped", "In Transit", "Customs", "Delivered", "Closed", "Cancelled"]
PO_STATUS_WEIGHTS = [0.02, 0.05, 0.05, 0.08, 0.03, 0.60, 0.12, 0.05]


def seed_purchase_orders(conn, supplier_ids, material_ids, contract_ids):
    currency_ids = fetch_ids(conn, "currencies", "currency_id")
    std_costs = fetch_map(conn, "materials", "material_id", "standard_cost_usd")

    po_count = 2000
    pos = []
    for i in range(po_count):
        sid = random.choice(supplier_ids)
        order_date = rand_date()
        expected_days = random.randint(14, 120)
        required = order_date + dt.timedelta(days=expected_days)
        cur = random.choice(currency_ids)
        cid = random.choice(contract_ids) if random.random() < 0.7 else None
        maverick = random.random() < 0.12
        # Estimate total — will be adjusted after line items
        total_amount = round(random.uniform(1_000, 500_000), 2)

        pos.append({
            "po_number": f"PO-{2022 + i // 500}-{str(i + 1).zfill(5)}",
            "supplier_id": sid,
            "order_date": order_date,
            "required_date": required,
            "currency_id": cur,
            "contract_id": cid,
            "total_amount": total_amount,
            "is_maverick": maverick,
            "status": random.choices(PO_STATUSES, weights=PO_STATUS_WEIGHTS, k=1)[0],
        })

    conn.execute(text("""
        INSERT INTO purchase_orders (po_number, supplier_id, order_date,
            required_date, currency_id, contract_id, total_amount, is_maverick, status)
        VALUES (:po_number, :supplier_id, :order_date, :required_date,
            :currency_id, :contract_id, :total_amount, :is_maverick, :status)
    """), pos)

    # Fetch PO IDs
    po_ids = fetch_ids(conn, "purchase_orders", "po_id")

    # Line items: 1-5 per PO
    items = []
    for po_id in po_ids:
        n_lines = random.randint(1, 5)
        for line in range(1, n_lines + 1):
            mid = random.choice(material_ids)
            base = float(std_costs.get(mid, 100))
            qty = random.randint(1, 200)
            price = round(base * random.uniform(0.8, 1.4), 2)
            items.append({
                "po_id": po_id,
                "material_id": mid,
                "quantity": qty,
                "unit_price": price,
            })

    # Batch insert in chunks for performance
    chunk = 500
    for i in range(0, len(items), chunk):
        conn.execute(text("""
            INSERT INTO po_line_items (po_id, material_id, quantity, unit_price)
            VALUES (:po_id, :material_id, :quantity, :unit_price)
        """), items[i:i + chunk])

    print(f"  ✓ {len(pos)} POs, {len(items)} line items inserted")
    return po_ids


# ═════════════════════════════════════════════════════════════════════
#  6. SHIPMENTS (1,800)
# ═════════════════════════════════════════════════════════════════════
SHIP_STATUSES = ["Pending", "In Transit", "At Port", "Customs", "Delivered", "Exception"]
CARRIERS = ["Maersk", "MSC", "CMA CGM", "Hapag-Lloyd", "COSCO", "Emirates SkyCargo",
            "DHL Logistics", "DB Schenker", "Kuehne+Nagel", "Bolloré Logistics"]


def seed_shipments(conn, po_ids):
    port_ids = fetch_ids(conn, "ports", "port_id")
    shipped_pos = random.sample(po_ids, min(1800, len(po_ids)))

    shipments = []
    for i, po_id in enumerate(shipped_pos):
        origin = random.choice(port_ids)
        dest = random.choice([p for p in port_ids if p != origin] or port_ids)
        dispatch = rand_date(dt.date(2022, 2, 1), dt.date(2025, 11, 30))
        transit = random.randint(5, 60)
        eta = dispatch + dt.timedelta(days=transit)
        delay = max(0, int(np.random.normal(2, 5)))
        actual = eta + dt.timedelta(days=delay) if random.random() < 0.85 else None
        mode = random.choices(["Sea", "Air", "Road", "Rail"],
                              weights=[0.55, 0.20, 0.15, 0.10], k=1)[0]
        weight = round(random.uniform(0.5, 500.0), 2)
        distance = round(transit * {"Sea": 600, "Air": 3000, "Road": 500, "Rail": 800}[mode], 1)

        shipments.append({
            "shipment_ref": f"SHP-{str(i + 1).zfill(5)}",
            "po_id": po_id,
            "transport_mode": mode,
            "carrier_name": random.choice(CARRIERS),
            "origin_port_id": origin,
            "destination_port_id": dest,
            "distance_km": distance,
            "weight_tonnes": weight,
            "dispatch_date": dispatch,
            "eta_date": eta,
            "actual_arrival": actual,
            "status": "Delivered" if actual else random.choice(["In Transit", "Customs", "At Port"]),
        })

    chunk = 500
    for i in range(0, len(shipments), chunk):
        conn.execute(text("""
            INSERT INTO shipments (shipment_ref, po_id, transport_mode, carrier_name,
                origin_port_id, destination_port_id, distance_km, weight_tonnes,
                dispatch_date, eta_date, actual_arrival, status)
            VALUES (:shipment_ref, :po_id, :transport_mode, :carrier_name,
                :origin_port_id, :destination_port_id, :distance_km, :weight_tonnes,
                :dispatch_date, :eta_date, :actual_arrival, :status)
        """), shipments[i:i + chunk])

    print(f"  ✓ {len(shipments)} shipments inserted")
    return fetch_ids(conn, "shipments", "shipment_id")


# ═════════════════════════════════════════════════════════════════════
#  7. QUALITY INSPECTIONS (1,500) + INCIDENTS (120)
# ═════════════════════════════════════════════════════════════════════
INSPECTORS = ["J. Okonkwo", "A. Smith", "M. Chen", "S. Patel",
              "K. Müller", "R. Santos", "T. Yamamoto", "L. van der Berg"]

INCIDENT_CATEGORIES = ["Defect", "Contamination", "Documentation", "Labelling", "Packaging", "Counterfeit"]
SEVERITIES = ["Minor", "Major", "Critical"]
CAPA_STATUSES = ["Open", "In Progress", "Implemented", "Verified", "Closed"]


def seed_quality(conn, shipment_ids, supplier_ids):
    # Inspections
    chosen = random.sample(shipment_ids, min(1500, len(shipment_ids)))
    inspections = []
    for ship_id in chosen:
        sample = random.randint(50, 2000)
        defect_pct = max(0, np.random.normal(3, 4))
        defects = min(sample, int(sample * defect_pct / 100))
        result = "Pass" if defect_pct < 5 else ("Conditional" if defect_pct < 10 else "Fail")
        inspections.append({
            "shipment_id": ship_id,
            "inspection_date": rand_date(dt.date(2022, 3, 1), dt.date(2025, 12, 15)),
            "inspector": random.choice(INSPECTORS),
            "sample_size": sample,
            "defects_found": defects,
            "result": result,
        })

    chunk = 500
    for i in range(0, len(inspections), chunk):
        conn.execute(text("""
            INSERT INTO quality_inspections (shipment_id, inspection_date,
                inspector, sample_size, defects_found, result)
            VALUES (:shipment_id, :inspection_date, :inspector,
                :sample_size, :defects_found, :result)
        """), inspections[i:i + chunk])

    # Incidents
    incidents = []
    for _ in range(120):
        incidents.append({
            "supplier_id": random.choice(supplier_ids),
            "incident_date": rand_date(),
            "severity": random.choices(SEVERITIES, weights=[0.5, 0.35, 0.15], k=1)[0],
            "category": random.choice(INCIDENT_CATEGORIES),
            "description": random.choice([
                "Dimensional out-of-spec on critical component",
                "Surface corrosion found post-shipment",
                "Material certification document expired",
                "Wrong specification delivered",
                "Packaging damaged during transit",
                "Coating failure on inspection",
                "Weld quality below acceptance criteria",
                "Labelling non-compliant with standard",
            ]),
            "root_cause": random.choice([None, "Supplier process deviation",
                                         "Material defect", "Handling damage",
                                         "Specification mismatch"]),
            "capa_status": random.choice(CAPA_STATUSES),
            "financial_impact_usd": round(random.uniform(500, 50000), 2),
        })

    conn.execute(text("""
        INSERT INTO quality_incidents (supplier_id, incident_date, severity,
            category, description, root_cause, capa_status, financial_impact_usd)
        VALUES (:supplier_id, :incident_date, :severity,
            :category, :description, :root_cause, :capa_status, :financial_impact_usd)
    """), incidents)

    print(f"  ✓ {len(inspections)} inspections, {len(incidents)} incidents inserted")


# ═════════════════════════════════════════════════════════════════════
#  8. INVOICES (~2,000)
# ═════════════════════════════════════════════════════════════════════
INVOICE_STATUSES = ["Pending", "Approved", "Paid", "Disputed", "Cancelled"]


def seed_invoices(conn, po_ids, supplier_ids):
    currency_ids = fetch_ids(conn, "currencies", "currency_id")
    invoices = []
    inv_counter = 0
    for po_id in random.sample(po_ids, min(2000, len(po_ids))):
        inv_counter += 1
        sid = random.choice(supplier_ids)
        cur = random.choice(currency_ids)
        inv_date = rand_date(dt.date(2022, 2, 1), END_DATE)
        amount = round(random.uniform(500, 250_000), 2)
        terms = random.choice([30, 45, 60, 90])
        due = inv_date + dt.timedelta(days=terms)
        paid = due + dt.timedelta(days=random.randint(-10, 30)) if random.random() < 0.85 else None
        discount = random.random() < 0.25
        amount_usd = round(amount * random.uniform(0.95, 1.05), 2)

        if paid:
            status = "Paid"
        else:
            status = random.choices(["Pending", "Approved", "Disputed"], weights=[0.5, 0.3, 0.2], k=1)[0]

        invoices.append({
            "invoice_number": f"INV-{inv_date.year}-{str(inv_counter).zfill(5)}",
            "po_id": po_id,
            "supplier_id": sid,
            "invoice_date": inv_date,
            "due_date": due,
            "amount": amount,
            "currency_id": cur,
            "amount_usd": amount_usd,
            "status": status,
            "payment_date": paid,
            "early_payment_discount_taken": discount and paid is not None and paid < due,
        })

    chunk = 500
    for i in range(0, len(invoices), chunk):
        conn.execute(text("""
            INSERT INTO invoices (invoice_number, po_id, supplier_id, invoice_date,
                due_date, amount, currency_id, amount_usd, status,
                payment_date, early_payment_discount_taken)
            VALUES (:invoice_number, :po_id, :supplier_id, :invoice_date,
                :due_date, :amount, :currency_id, :amount_usd, :status,
                :payment_date, :early_payment_discount_taken)
        """), invoices[i:i + chunk])

    print(f"  ✓ {len(invoices)} invoices inserted")


# ═════════════════════════════════════════════════════════════════════
#  9. FX RATES — GBM backward from anchor rates (~7,000 rows)
# ═════════════════════════════════════════════════════════════════════
def seed_fx_rates(conn):
    """Generate daily FX rates using Geometric Brownian Motion,
    anchored at today's known rates and walking backward."""

    anchor_rates = config.FX_ANCHOR_RATES
    vols = config.FX_VOLATILITIES
    # Build currency_code -> currency_id map
    code_to_id = fetch_map(conn, "currencies", "currency_code", "currency_id")

    rates = []
    for ccy, anchor in anchor_rates.items():
        ccy_id = code_to_id.get(ccy)
        if ccy_id is None:
            continue
        vol = vols.get(ccy, 0.10)
        daily_vol = vol / math.sqrt(252)
        dates = []
        d = START_DATE
        while d <= END_DATE:
            dates.append(d)
            d += dt.timedelta(days=1)

        # Forward GBM then rescale so last value = anchor
        gbm_path = [1.0]
        for _ in range(1, len(dates)):
            drift = -0.5 * daily_vol ** 2
            shock = daily_vol * np.random.normal()
            gbm_path.append(gbm_path[-1] * math.exp(drift + shock))

        scale = anchor / gbm_path[-1]
        for idx, day in enumerate(dates):
            rate = round(gbm_path[idx] * scale, 6)
            rates.append({
                "currency_id": ccy_id,
                "rate_date": day,
                "rate_to_usd": rate,
                "source": "GBM-Simulated",
            })

    chunk = 1000
    for i in range(0, len(rates), chunk):
        conn.execute(text("""
            INSERT INTO fx_rates (currency_id, rate_date, rate_to_usd, source)
            VALUES (:currency_id, :rate_date, :rate_to_usd, :source)
        """), rates[i:i + chunk])

    print(f"  ✓ {len(rates)} FX rate records inserted ({len(anchor_rates)} currencies)")


# ═════════════════════════════════════════════════════════════════════
#  10. COMMODITY PRICES (~2,000 rows)
# ═════════════════════════════════════════════════════════════════════
COMMODITIES = [
    ("Hot Rolled Coil Steel", "USD", 650),
    ("Cold Rolled Steel",     "USD", 800),
    ("Stainless Steel 304",   "USD", 3000),
    ("Copper Cathode",        "USD", 8500),
    ("Aluminium Ingot",       "USD", 2300),
    ("Crude Oil Brent",       "USD", 78),
    ("Natural Gas Henry Hub",  "USD", 3.5),
    ("Nickel LME",            "USD", 18000),
]


def seed_commodity_prices(conn):
    prices = []
    for name, ccy, base in COMMODITIES:
        d = START_DATE
        vol = 0.20 / math.sqrt(252)
        price = base
        while d <= END_DATE:
            price = price * math.exp(-0.5 * vol**2 + vol * np.random.normal())
            prices.append({
                "commodity_group": name,
                "price_date": d,
                "price_usd": round(price, 2),
                "unit": "tonne" if "Steel" in name or "Copper" in name or "Alum" in name or "Nickel" in name
                        else ("barrel" if "Oil" in name else "MMBtu"),
                "source": "Simulated-LME/ICE",
            })
            d += dt.timedelta(days=7)

    chunk = 500
    for i in range(0, len(prices), chunk):
        conn.execute(text("""
            INSERT INTO commodity_prices (commodity_group, price_date,
                price_usd, unit, source)
            VALUES (:commodity_group, :price_date, :price_usd, :unit, :source)
        """), prices[i:i + chunk])

    print(f"  ✓ {len(prices)} commodity price records inserted")


# ═════════════════════════════════════════════════════════════════════
#  11. COUNTRY RISK INDICES (annual, 15 countries × 4 years)
# ═════════════════════════════════════════════════════════════════════
def seed_country_risk(conn):
    country_ids = fetch_ids(conn, "countries", "country_id")
    records = []
    for cid in country_ids:
        for year in range(2022, 2026):
            records.append({
                "country_id": cid,
                "assessment_year": year,
                "political_stability_score": round(random.uniform(20, 90), 1),
                "regulatory_quality_score": round(random.uniform(25, 92), 1),
                "rule_of_law_score": round(random.uniform(20, 88), 1),
                "control_of_corruption_score": round(random.uniform(15, 85), 1),
                "ease_of_business_rank": random.randint(1, 190),
                "logistics_performance_index": round(random.uniform(2.0, 4.5), 2),
                "composite_country_risk": round(random.uniform(20, 85), 1),
            })

    conn.execute(text("""
        INSERT INTO country_risk_indices (country_id, assessment_year,
            political_stability_score, regulatory_quality_score,
            rule_of_law_score, control_of_corruption_score,
            ease_of_business_rank, logistics_performance_index,
            composite_country_risk)
        VALUES (:country_id, :assessment_year,
            :political_stability_score, :regulatory_quality_score,
            :rule_of_law_score, :control_of_corruption_score,
            :ease_of_business_rank, :logistics_performance_index,
            :composite_country_risk)
    """), records)
    print(f"  ✓ {len(records)} country risk records inserted")


# ═════════════════════════════════════════════════════════════════════
#  12. ESG ASSESSMENTS (100)
# ═════════════════════════════════════════════════════════════════════
def seed_esg(conn, supplier_ids):
    assessments = []
    chosen = random.sample(supplier_ids, min(50, len(supplier_ids)))
    for sid in chosen:
        for year in [2023, 2024]:
            # Environmental sub-scores
            carbon = round(random.uniform(20, 95), 1)
            waste = round(random.uniform(25, 90), 1)
            water = round(random.uniform(20, 92), 1)
            env_incidents = random.randint(0, 5)
            env_comp = round((carbon + waste + water) / 3, 1)
            # Social sub-scores
            labor = round(random.uniform(25, 95), 1)
            hs = round(random.uniform(30, 95), 1)
            community = round(random.uniform(20, 90), 1)
            slavery_risk = random.choices(["Low", "Medium", "High", "Critical"],
                                          weights=[0.5, 0.3, 0.15, 0.05], k=1)[0]
            soc_comp = round((labor + hs + community) / 3, 1)
            # Governance sub-scores
            ethics = round(random.uniform(30, 95), 1)
            transparency = round(random.uniform(25, 90), 1)
            board_div = round(random.uniform(15, 85), 1)
            gov_comp = round((ethics + transparency + board_div) / 3, 1)
            # Overall
            overall = round(0.35 * env_comp + 0.35 * soc_comp + 0.30 * gov_comp, 1)
            if overall >= 80: rating = "A"
            elif overall >= 65: rating = "B"
            elif overall >= 50: rating = "C"
            elif overall >= 35: rating = "D"
            else: rating = "F"

            assessments.append({
                "supplier_id": sid,
                "assessment_date": dt.date(year, random.randint(1, 12), 15),
                "assessor": random.choice(["EcoVadis", "Sedex", "Internal Audit", "CDP"]),
                "carbon_intensity_score": carbon,
                "waste_management_score": waste,
                "water_usage_score": water,
                "environmental_incidents": env_incidents,
                "env_composite": env_comp,
                "labor_practices_score": labor,
                "health_safety_score": hs,
                "community_impact_score": community,
                "modern_slavery_risk": slavery_risk,
                "social_composite": soc_comp,
                "ethics_compliance_score": ethics,
                "transparency_score": transparency,
                "board_diversity_score": board_div,
                "governance_composite": gov_comp,
                "esg_overall_score": overall,
                "esg_rating": rating,
            })

    conn.execute(text("""
        INSERT INTO esg_assessments (supplier_id, assessment_date, assessor,
            carbon_intensity_score, waste_management_score, water_usage_score,
            environmental_incidents, env_composite,
            labor_practices_score, health_safety_score, community_impact_score,
            modern_slavery_risk, social_composite,
            ethics_compliance_score, transparency_score, board_diversity_score,
            governance_composite, esg_overall_score, esg_rating)
        VALUES (:supplier_id, :assessment_date, :assessor,
            :carbon_intensity_score, :waste_management_score, :water_usage_score,
            :environmental_incidents, :env_composite,
            :labor_practices_score, :health_safety_score, :community_impact_score,
            :modern_slavery_risk, :social_composite,
            :ethics_compliance_score, :transparency_score, :board_diversity_score,
            :governance_composite, :esg_overall_score, :esg_rating)
    """), assessments)
    print(f"  ✓ {len(assessments)} ESG assessments inserted")


# ═════════════════════════════════════════════════════════════════════
#  13. CARBON ESTIMATES (1,800)
# ═════════════════════════════════════════════════════════════════════
def seed_carbon(conn, shipment_ids):
    ef = config.EMISSION_FACTORS
    # Fetch shipment details
    rows = conn.execute(text("""
        SELECT shipment_id, transport_mode, weight_tonnes, distance_km
        FROM shipments
    """)).fetchall()

    estimates = []
    for r in rows:
        mode = r[1]
        weight = float(r[2]) if r[2] else 10.0
        distance = float(r[3]) if r[3] else 5000.0
        factor = ef.get(mode, 0.016)
        co2e = round(weight * distance * factor, 2)

        estimates.append({
            "shipment_id": r[0],
            "transport_mode": mode,
            "distance_km": distance,
            "weight_tonnes": weight,
            "co2e_kg": co2e,
            "calculation_method": "GLEC Framework v3",
        })

    chunk = 500
    for i in range(0, len(estimates), chunk):
        conn.execute(text("""
            INSERT INTO carbon_estimates (shipment_id, transport_mode,
                distance_km, weight_tonnes, co2e_kg, calculation_method)
            VALUES (:shipment_id, :transport_mode, :distance_km,
                :weight_tonnes, :co2e_kg, :calculation_method)
        """), estimates[i:i + chunk])

    print(f"  ✓ {len(estimates)} carbon estimates inserted")


# ═════════════════════════════════════════════════════════════════════
#  14. SUPPLIER CERTIFICATIONS (~150)
# ═════════════════════════════════════════════════════════════════════
def seed_certifications(conn, supplier_ids):
    cert_ids = fetch_ids(conn, "certifications_catalog", "cert_id")
    certs = []
    for sid in supplier_ids:
        n = random.randint(0, 4)
        chosen = random.sample(cert_ids, min(n, len(cert_ids)))
        for cid in chosen:
            issued = rand_date(dt.date(2020, 1, 1), dt.date(2024, 6, 1))
            expires = issued + dt.timedelta(days=random.choice([1095, 1825]))
            is_verified = expires > dt.date.today()
            certs.append({
                "supplier_id": sid, "cert_id": cid,
                "issued_date": issued, "expiry_date": expires,
                "is_verified": is_verified,
            })

    if certs:
        conn.execute(text("""
            INSERT INTO supplier_certifications (supplier_id, cert_id,
                issued_date, expiry_date, is_verified)
            VALUES (:supplier_id, :cert_id, :issued_date,
                :expiry_date, :is_verified)
        """), certs)
    print(f"  ✓ {len(certs)} supplier certifications inserted")


# ═════════════════════════════════════════════════════════════════════
#  15. COMPLIANCE CHECKS + DUE DILIGENCE
# ═════════════════════════════════════════════════════════════════════
COMPLIANCE_STATUSES = ["Compliant", "Partially Compliant", "Non-Compliant", "Not Assessed"]
DD_STEP_VALS = ["Done", "Partial", "Not Done"]
DD_OVERALL = ["Complete", "In Progress", "Overdue", "Not Started"]


def seed_compliance(conn, supplier_ids):
    fw_ids = fetch_ids(conn, "compliance_frameworks", "framework_id")

    # Compliance checks
    checks = []
    for sid in random.sample(supplier_ids, min(40, len(supplier_ids))):
        for fid in random.sample(fw_ids, random.randint(1, 3)):
            checks.append({
                "supplier_id": sid, "framework_id": fid,
                "check_date": rand_date(dt.date(2023, 1, 1), END_DATE),
                "status": random.choices(
                    COMPLIANCE_STATUSES,
                    weights=[0.55, 0.20, 0.15, 0.10], k=1)[0],
                "gaps_identified": random.choice([None, "Minor gaps found",
                                                   "Documentation incomplete",
                                                   "Full compliance verified"]),
            })

    conn.execute(text("""
        INSERT INTO compliance_checks (supplier_id, framework_id, check_date,
            status, gaps_identified)
        VALUES (:supplier_id, :framework_id, :check_date,
            :status, :gaps_identified)
    """), checks)

    # Due diligence records (OECD 6-step)
    dd_records = []
    for sid in random.sample(supplier_ids, min(30, len(supplier_ids))):
        # Randomly complete 1-6 steps
        steps_done = random.randint(0, 6)
        step_vals = []
        for s in range(6):
            if s < steps_done:
                step_vals.append(random.choice(["Done", "Partial"]))
            else:
                step_vals.append("Not Done")

        if steps_done == 6:
            overall = "Complete"
        elif steps_done >= 3:
            overall = "In Progress"
        elif steps_done >= 1:
            overall = random.choice(["In Progress", "Overdue"])
        else:
            overall = "Not Started"

        dd_records.append({
            "supplier_id": sid,
            "dd_date": rand_date(dt.date(2023, 1, 1), END_DATE),
            "step_1_policy": step_vals[0],
            "step_2_identify": step_vals[1],
            "step_3_mitigate": step_vals[2],
            "step_4_verify": step_vals[3],
            "step_5_communicate": step_vals[4],
            "step_6_remediate": step_vals[5],
            "overall_status": overall,
            "findings": random.choice([
                None, "No material risks identified",
                "Potential conflict mineral sourcing",
                "Labour practice concerns — remediation plan agreed"]),
        })

    conn.execute(text("""
        INSERT INTO due_diligence_records (supplier_id, dd_date,
            step_1_policy, step_2_identify, step_3_mitigate,
            step_4_verify, step_5_communicate, step_6_remediate,
            overall_status, findings)
        VALUES (:supplier_id, :dd_date,
            :step_1_policy, :step_2_identify, :step_3_mitigate,
            :step_4_verify, :step_5_communicate, :step_6_remediate,
            :overall_status, :findings)
    """), dd_records)

    print(f"  ✓ {len(checks)} compliance checks, {len(dd_records)} DD records inserted")


# ═════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("AEGIS — Seed Data Generation")
    print("=" * 60)

    with ENGINE.begin() as conn:
        print("\n[1/14] Suppliers...")
        supplier_ids = seed_suppliers(conn)

        print("[2/14] Materials...")
        material_ids = seed_materials(conn)

        print("[3/14] Supplier-Material Catalog...")
        seed_catalog(conn, supplier_ids, material_ids)

        print("[4/14] Contracts...")
        contract_ids = seed_contracts(conn, supplier_ids)

        print("[5/14] Purchase Orders + Line Items...")
        po_ids = seed_purchase_orders(conn, supplier_ids, material_ids, contract_ids)

        print("[6/14] Shipments...")
        shipment_ids = seed_shipments(conn, po_ids)

        print("[7/14] Quality Inspections + Incidents...")
        seed_quality(conn, shipment_ids, supplier_ids)

        print("[8/14] Invoices...")
        seed_invoices(conn, po_ids, supplier_ids)

        print("[9/14] FX Rates (GBM)...")
        seed_fx_rates(conn)

        print("[10/14] Commodity Prices...")
        seed_commodity_prices(conn)

        print("[11/14] Country Risk Indices...")
        seed_country_risk(conn)

        print("[12/14] ESG Assessments...")
        seed_esg(conn, supplier_ids)

        print("[13/14] Carbon Estimates...")
        seed_carbon(conn, shipment_ids)

        print("[14/14] Certifications & Compliance...")
        seed_certifications(conn, supplier_ids)
        seed_compliance(conn, supplier_ids)

    print("\n" + "=" * 60)
    print("✓ AEGIS seed data generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
