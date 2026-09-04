-- RecoverAI PostgreSQL baseline migration
-- Apply once to a new PostgreSQL database before starting the API.
-- The application may also initialise this schema automatically on an empty DB.

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, phone TEXT,
    business_name TEXT NOT NULL, razorpay_key_id TEXT, razorpay_webhook_secret TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default',
    email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL,
    full_name TEXT NOT NULL, company_name TEXT NOT NULL DEFAULT 'My Store',
    role TEXT NOT NULL DEFAULT 'OWNER', api_key TEXT UNIQUE, is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_login_at TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL,
    used_at TEXT, created_at TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    total_payments INTEGER NOT NULL DEFAULT 0, successful_payments INTEGER NOT NULL DEFAULT 0,
    failed_payments INTEGER NOT NULL DEFAULT 0, lifetime_value DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    preferred_channel TEXT NOT NULL DEFAULT 'SMS', email TEXT, phone TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    customer_id TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL CHECK (amount > 0), status TEXT NOT NULL,
    failure_reason TEXT NOT NULL, payment_method TEXT NOT NULL, timestamp TEXT NOT NULL,
    previous_attempts INTEGER NOT NULL DEFAULT 0, event_type TEXT NOT NULL DEFAULT 'PAYMENT_FAILED',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id), FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS checkouts (
    checkout_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    customer_id TEXT NOT NULL, cart_value DOUBLE PRECISION NOT NULL, drop_off_stage TEXT NOT NULL,
    time_spent_seconds INTEGER NOT NULL DEFAULT 60, timestamp TEXT NOT NULL, customer_email TEXT, customer_phone TEXT,
    status TEXT NOT NULL DEFAULT 'ABANDONED', FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS recovery_plans (
    plan_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    payment_id TEXT NOT NULL, strategy TEXT NOT NULL, steps_json TEXT NOT NULL, priority TEXT NOT NULL,
    expected_recovery_value DOUBLE PRECISION NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id), FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS recovery_attempts (
    attempt_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    payment_id TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL,
    recovery_link_payment_id TEXT, channel_used TEXT DEFAULT 'SMS',
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id), FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS audit_logs (
    event_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    payment_id TEXT NOT NULL, ml_score DOUBLE PRECISION NOT NULL, expected_value DOUBLE PRECISION DEFAULT 0.0,
    priority_tier TEXT DEFAULT 'MEDIUM', ai_diagnosis TEXT NOT NULL, ai_recommendation TEXT NOT NULL,
    strategy_type TEXT DEFAULT 'INTELLIGENT_RETRY', channel_used TEXT DEFAULT 'SMS', guardrail_result TEXT NOT NULL,
    action_taken TEXT NOT NULL, result TEXT NOT NULL, timestamp TEXT NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id), FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE TABLE IF NOT EXISTS ground_truth (
    payment_id TEXT PRIMARY KEY, actual_recovery_outcome INTEGER NOT NULL,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
);
CREATE TABLE IF NOT EXISTS merchant_settings (
    key TEXT NOT NULL, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    value TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (merchant_id, key)
);
CREATE TABLE IF NOT EXISTS scheduled_recovery_jobs (
    job_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL DEFAULT 'mer_default', user_id TEXT NOT NULL DEFAULT 'usr_default',
    payment_id TEXT NOT NULL, playbook TEXT NOT NULL, stage TEXT NOT NULL, scheduled_at TEXT NOT NULL,
    delay_seconds INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_checked_at TEXT, recheck_result TEXT,
    next_action TEXT NOT NULL, attempt_number INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'PENDING',
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id), FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE INDEX IF NOT EXISTS idx_payments_merchant ON payments(merchant_id);
CREATE INDEX IF NOT EXISTS idx_payments_mer_pay ON payments(merchant_id, payment_id);
CREATE INDEX IF NOT EXISTS idx_customers_merchant ON customers(merchant_id);
CREATE INDEX IF NOT EXISTS idx_attempts_merchant ON recovery_attempts(merchant_id);
CREATE INDEX IF NOT EXISTS idx_attempts_payment ON recovery_attempts(payment_id);
CREATE INDEX IF NOT EXISTS idx_audit_merchant ON audit_logs(merchant_id);
CREATE INDEX IF NOT EXISTS idx_audit_mer_pay ON audit_logs(merchant_id, payment_id);
CREATE INDEX IF NOT EXISTS idx_plans_merchant ON recovery_plans(merchant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_sched ON scheduled_recovery_jobs(status, scheduled_at);