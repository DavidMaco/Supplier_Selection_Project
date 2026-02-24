-- ═══════════════════════════════════════════════════════════════════
-- AEGIS — 03: Transaction Tables
-- Purchase Orders, PO Line Items, Shipments, Shipment Milestones,
-- Quality Inspections, Quality Incidents, Invoices
-- ═══════════════════════════════════════════════════════════════════

USE aegis_procurement;

-- ─────────────────────────────────────────────────────────
-- PURCHASE ORDERS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id               INT AUTO_INCREMENT PRIMARY KEY,
    po_number           VARCHAR(50)   NOT NULL UNIQUE,
    supplier_id         INT           NOT NULL,
    contract_id         INT,
    order_date          DATE          NOT NULL,
    required_date       DATE          NOT NULL,
    currency_id         INT           NOT NULL,
    incoterm_id         INT,
    origin_port_id      INT,
    destination_port_id INT,
    total_amount        DECIMAL(18,2) NOT NULL,
    total_usd_value     DECIMAL(18,2),
    fx_rate_at_order    DECIMAL(18,6),
    freight_cost_usd    DECIMAL(15,2) DEFAULT 0,
    insurance_cost_usd  DECIMAL(15,2) DEFAULT 0,
    customs_duty_usd    DECIMAL(15,2) DEFAULT 0,
    landed_cost_usd     DECIMAL(18,2),
    status              ENUM('Draft','Approved','Shipped','In Transit',
                             'Customs','Delivered','Closed','Cancelled') DEFAULT 'Approved',
    is_maverick         BOOLEAN DEFAULT FALSE,
    created_by          VARCHAR(100) DEFAULT 'system',
    approved_by         VARCHAR(100),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_po_supplier  FOREIGN KEY (supplier_id)         REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_po_contract  FOREIGN KEY (contract_id)         REFERENCES contracts(contract_id),
    CONSTRAINT fk_po_currency  FOREIGN KEY (currency_id)         REFERENCES currencies(currency_id),
    CONSTRAINT fk_po_incoterm  FOREIGN KEY (incoterm_id)         REFERENCES incoterms(incoterm_id),
    CONSTRAINT fk_po_orig_port FOREIGN KEY (origin_port_id)      REFERENCES ports(port_id),
    CONSTRAINT fk_po_dest_port FOREIGN KEY (destination_port_id) REFERENCES ports(port_id),
    INDEX idx_po_supplier   (supplier_id),
    INDEX idx_po_order_date (order_date),
    INDEX idx_po_status     (status)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- PO LINE ITEMS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS po_line_items (
    line_id               INT AUTO_INCREMENT PRIMARY KEY,
    po_id                 INT           NOT NULL,
    material_id           INT           NOT NULL,
    quantity              DECIMAL(15,2) NOT NULL CHECK (quantity > 0),
    unit_price            DECIMAL(15,4) NOT NULL CHECK (unit_price > 0),
    line_total            DECIMAL(18,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    line_total_usd        DECIMAL(18,2),
    standard_cost_at_order DECIMAL(15,2),

    CONSTRAINT fk_li_po       FOREIGN KEY (po_id)       REFERENCES purchase_orders(po_id),
    CONSTRAINT fk_li_material FOREIGN KEY (material_id) REFERENCES materials(material_id),
    INDEX idx_li_po       (po_id),
    INDEX idx_li_material (material_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- SHIPMENTS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id         INT AUTO_INCREMENT PRIMARY KEY,
    shipment_ref        VARCHAR(50) NOT NULL UNIQUE,
    po_id               INT NOT NULL,
    transport_mode      ENUM('Sea','Air','Rail','Road','Multimodal') NOT NULL,
    carrier_name        VARCHAR(200),
    origin_port_id      INT,
    destination_port_id INT,
    distance_km         DECIMAL(10,1),
    weight_tonnes       DECIMAL(10,3),
    dispatch_date       DATE,
    eta_date            DATE,
    actual_arrival      DATE,
    customs_clearance_date DATE,
    final_delivery_date DATE,
    status              ENUM('Pending','In Transit','At Port','Customs',
                             'Delivered','Exception') DEFAULT 'Pending',
    delay_days          INT GENERATED ALWAYS AS (
                            CASE WHEN final_delivery_date IS NOT NULL AND eta_date IS NOT NULL
                                 THEN DATEDIFF(final_delivery_date, eta_date)
                                 ELSE NULL END
                        ) STORED,

    CONSTRAINT fk_sh_po        FOREIGN KEY (po_id)               REFERENCES purchase_orders(po_id),
    CONSTRAINT fk_sh_orig_port FOREIGN KEY (origin_port_id)      REFERENCES ports(port_id),
    CONSTRAINT fk_sh_dest_port FOREIGN KEY (destination_port_id) REFERENCES ports(port_id),
    INDEX idx_sh_po     (po_id),
    INDEX idx_sh_status (status),
    INDEX idx_sh_eta    (eta_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- SHIPMENT MILESTONES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipment_milestones (
    milestone_id   INT AUTO_INCREMENT PRIMARY KEY,
    shipment_id    INT NOT NULL,
    milestone_type ENUM('Order Placed','Dispatched','Port Arrival Origin',
                        'Loaded','Port Arrival Dest','Customs Entry',
                        'Customs Cleared','Final Delivery','Exception') NOT NULL,
    milestone_date DATETIME NOT NULL,
    location       VARCHAR(200),
    notes          TEXT,

    CONSTRAINT fk_sm_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
    INDEX idx_sm_shipment (shipment_id)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- QUALITY INSPECTIONS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_inspections (
    inspection_id    INT AUTO_INCREMENT PRIMARY KEY,
    shipment_id      INT NOT NULL,
    inspection_date  DATE NOT NULL,
    inspector        VARCHAR(200),
    sample_size      INT NOT NULL CHECK (sample_size > 0),
    defects_found    INT DEFAULT 0 CHECK (defects_found >= 0),
    defect_rate_pct  DECIMAL(5,2) GENERATED ALWAYS AS (
                        CASE WHEN sample_size > 0 THEN (defects_found / sample_size) * 100
                             ELSE 0 END
                     ) STORED,
    result           ENUM('Pass','Conditional','Fail') NOT NULL,
    disposition      ENUM('Accept','Rework','Return','Scrap') DEFAULT 'Accept',

    CONSTRAINT fk_qi_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
    INDEX idx_qi_shipment (shipment_id),
    INDEX idx_qi_date     (inspection_date)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- QUALITY INCIDENTS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_incidents (
    incident_id          INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id          INT NOT NULL,
    material_id          INT,
    po_id                INT,
    incident_date        DATE NOT NULL,
    severity             ENUM('Minor','Major','Critical','Recall') NOT NULL,
    category             ENUM('Defect','Contamination','Documentation',
                              'Labelling','Packaging','Counterfeit') NOT NULL,
    description          TEXT NOT NULL,
    root_cause           TEXT,
    capa_status          ENUM('Open','In Progress','Implemented',
                              'Verified','Closed') DEFAULT 'Open',
    capa_due_date        DATE,
    financial_impact_usd DECIMAL(15,2) DEFAULT 0,

    CONSTRAINT fk_qinc_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_qinc_material FOREIGN KEY (material_id) REFERENCES materials(material_id),
    CONSTRAINT fk_qinc_po       FOREIGN KEY (po_id)       REFERENCES purchase_orders(po_id),
    INDEX idx_qinc_supplier (supplier_id),
    INDEX idx_qinc_date     (incident_date),
    INDEX idx_qinc_severity (severity)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────────────────
-- INVOICES
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id                    INT AUTO_INCREMENT PRIMARY KEY,
    invoice_number                VARCHAR(50) NOT NULL UNIQUE,
    po_id                         INT NOT NULL,
    supplier_id                   INT NOT NULL,
    invoice_date                  DATE NOT NULL,
    due_date                      DATE NOT NULL,
    amount                        DECIMAL(18,2) NOT NULL,
    currency_id                   INT NOT NULL,
    amount_usd                    DECIMAL(18,2),
    status                        ENUM('Pending','Approved','Paid',
                                       'Disputed','Cancelled') DEFAULT 'Pending',
    payment_date                  DATE,
    days_to_pay                   INT GENERATED ALWAYS AS (
                                       CASE WHEN payment_date IS NOT NULL
                                            THEN DATEDIFF(payment_date, invoice_date)
                                            ELSE NULL END
                                  ) STORED,
    early_payment_discount_taken  BOOLEAN DEFAULT FALSE,

    CONSTRAINT fk_inv_po       FOREIGN KEY (po_id)       REFERENCES purchase_orders(po_id),
    CONSTRAINT fk_inv_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_inv_currency FOREIGN KEY (currency_id) REFERENCES currencies(currency_id),
    INDEX idx_inv_supplier (supplier_id),
    INDEX idx_inv_status   (status),
    INDEX idx_inv_due      (due_date)
) ENGINE=InnoDB;
