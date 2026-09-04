-- Tenant-scoped one-active-link guard for RecoverAI recovery dispatch.
CREATE TABLE IF NOT EXISTS recovery_links (
    recovery_link_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    payment_id TEXT NOT NULL,
    status TEXT NOT NULL,
    razorpay_link_id TEXT,
    short_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (merchant_id, payment_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE INDEX IF NOT EXISTS idx_recovery_links_mer_pay
    ON recovery_links(merchant_id, payment_id);