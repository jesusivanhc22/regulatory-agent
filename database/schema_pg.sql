-- Schema PostgreSQL para Monitor Regulatorio ERP Farmacias
-- Compatible con Railway PostgreSQL plugin

CREATE TABLE IF NOT EXISTS publications (
    id SERIAL PRIMARY KEY,
    title TEXT,
    url TEXT UNIQUE,
    publication_date TEXT,
    effective_date TEXT,
    status TEXT DEFAULT 'DISCOVERED',
    source TEXT DEFAULT 'DOF',
    raw_html TEXT,
    full_text TEXT,
    content_type TEXT,
    pdf_path TEXT,
    pdf_hash TEXT,
    primary_domain TEXT,
    health_score INTEGER,
    fiscal_score INTEGER,
    retail_score INTEGER,
    border_region_score INTEGER,
    currency_score INTEGER,
    operational_obligation_score INTEGER,
    regulatory_compliance_score INTEGER DEFAULT 0,
    invoicing_score INTEGER,
    tax_reporting_score INTEGER,
    inventory_score INTEGER,
    accounting_score INTEGER,
    pos_score INTEGER,
    impacted_module TEXT,
    severity TEXT,
    impact_flag INTEGER,
    impact_reason TEXT,
    ai_summary TEXT,
    ai_actions TEXT,
    ai_deadline TEXT,
    ai_priority TEXT,
    analyzed_at TEXT,
    category TEXT,
    priority TEXT,
    score INTEGER DEFAULT 0,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    name TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
