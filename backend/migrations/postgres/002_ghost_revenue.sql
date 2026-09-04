-- Ghost Revenue Hunter: PostgreSQL production migration
-- Safe to run repeatedly. This lane only records reconciliation incidents;
-- it does not create orders, payment links, retries, or charges.

CREATE TABLE IF NOT EXISTS ghost_revenue_incidents (
    incident_id          TEXT PRIMARY KEY,
    merchant_id          TEXT NOT NULL DEFAULT 'mer_default',
    razorpay_payment_id  TEXT NOT NULL,
    amount               DOUBLE PRECISION NOT NULL CHECK (amount > 0),
    issue_type           TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'OPEN',
    recommended_action   TEXT NOT NULL,
    evidence_json        TEXT NOT NULL DEFAULT '{}',
    created_at           TEXT NOT NULL,
    resolved_at          TEXT,
    resolution_note      TEXT,
    UNIQUE (merchant_id, razorpay_payment_id, issue_type),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);

CREATE TABLE IF NOT EXISTS ghost_revenue_events (
    event_id             TEXT PRIMARY KEY,
    incident_id          TEXT NOT NULL,
    merchant_id          TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    detail_json          TEXT NOT NULL DEFAULT '{}',
    created_at           TEXT NOT NULL,
    UNIQUE (incident_id, event_type),
    FOREIGN KEY (incident_id) REFERENCES ghost_revenue_incidents(incident_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);

CREATE INDEX IF NOT EXISTS idx_ghost_incidents_merchant
    ON ghost_revenue_incidents(merchant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ghost_events_incident
    ON ghost_revenue_events(incident_id, merchant_id, created_at DESC);