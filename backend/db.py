"""
db.py — Shared database helper functions for RecoverAI 2.0.

Provides SQLite connection management, table schemas, migrations,
multi-tenant user authentication, and unified persistence for payments,
customers, checkouts, recovery plans, recovery attempts, audit logs,
and merchant workspace profiles.
"""

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, List, Optional, Dict, Any

from dotenv import load_dotenv

from logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# DATABASE_URL accepts either a SQLite path or a PostgreSQL connection URL.
DATABASE_URL: str = os.getenv("DATABASE_URL", "recoverai.db")
DATABASE_PATH = DATABASE_URL  # Backwards-compatible name used by log messages.
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


class PostgresRow(dict):
    """Mapping row with SQLite-compatible positional access."""
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def _postgres_sql(sql: str) -> str:
    """Translate the small SQLite SQL dialect used by the application."""
    is_ignore = bool(re.search(r"INSERT\s+OR\s+IGNORE", sql, flags=re.IGNORECASE))
    replace = re.search(r"INSERT\s+OR\s+REPLACE\s+INTO\s+([\w.]+)\s*\(([^)]+)\)", sql, flags=re.IGNORECASE | re.DOTALL)
    if replace:
        table, columns = replace.groups()
        assignments = ", ".join(f"{column.strip()} = EXCLUDED.{column.strip()}" for column in columns.split(","))
        sql = sql[:replace.start()] + f"INSERT INTO {table} ({columns})" + sql[replace.end():]
        sql = sql.rstrip().rstrip(";") + f" ON CONFLICT DO UPDATE SET {assignments}"
    elif is_ignore:
        sql = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=re.IGNORECASE)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return re.sub(r":([A-Za-z_]\w*)", r"%(\1)s", sql).replace("?", "%s")


class PostgresCursor:
    def __init__(self, cursor): self._cursor = cursor
    def fetchone(self):
        row = self._cursor.fetchone()
        return PostgresRow(row) if row is not None else None
    def fetchall(self): return [PostgresRow(row) for row in self._cursor.fetchall()]


class PostgresConnection:
    """Minimal sqlite3-compatible facade over a psycopg connection."""
    def __init__(self, connection): self._connection = connection
    def execute(self, sql: str, params=None): return PostgresCursor(self._connection.execute(_postgres_sql(sql), params))
    def executemany(self, sql: str, params):
        cursor = self._connection.cursor()
        cursor.executemany(_postgres_sql(sql), params)
        return PostgresCursor(cursor)
    def commit(self): self._connection.commit()
    def rollback(self): self._connection.rollback()
    def close(self): self._connection.close()


# ── Connection helper ─────────────────────────────────────────────────────────

@contextmanager
def get_connection() -> Generator[Any, None, None]:
    """Open a SQLite or PostgreSQL connection and commit atomically on success."""
    if IS_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL DATABASE_URL requires psycopg; install backend requirements first.") from exc
        conn = PostgresConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    else:
        conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema creation ───────────────────────────────────────────────────────────

CREATE_MERCHANTS = """
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id              TEXT PRIMARY KEY,
    name                     TEXT NOT NULL,
    email                    TEXT,
    phone                    TEXT,
    business_name            TEXT NOT NULL,
    razorpay_key_id          TEXT,
    razorpay_webhook_secret  TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id          TEXT PRIMARY KEY,
    merchant_id      TEXT NOT NULL DEFAULT 'mer_default',
    email            TEXT UNIQUE NOT NULL,
    password_hash    TEXT NOT NULL,
    salt             TEXT NOT NULL,
    full_name        TEXT NOT NULL,
    company_name     TEXT NOT NULL DEFAULT 'My Store',
    role             TEXT NOT NULL DEFAULT 'OWNER',
    api_key          TEXT UNIQUE,
    is_active        INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    last_login_at    TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_PASSWORD_RESETS = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

CREATE_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id          TEXT PRIMARY KEY,
    merchant_id          TEXT NOT NULL DEFAULT 'mer_default',
    user_id              TEXT NOT NULL DEFAULT 'usr_default',
    total_payments       INTEGER NOT NULL DEFAULT 0,
    successful_payments  INTEGER NOT NULL DEFAULT 0,
    failed_payments      INTEGER NOT NULL DEFAULT 0,
    lifetime_value       REAL NOT NULL DEFAULT 0.0,
    preferred_channel    TEXT NOT NULL DEFAULT 'SMS',
    email                TEXT,
    phone                TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payments (
    payment_id          TEXT PRIMARY KEY,
    merchant_id         TEXT NOT NULL DEFAULT 'mer_default',
    user_id             TEXT NOT NULL DEFAULT 'usr_default',
    customer_id         TEXT NOT NULL,
    amount              REAL NOT NULL CHECK (amount > 0),
    status              TEXT NOT NULL,
    failure_reason      TEXT NOT NULL,
    payment_method      TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    previous_attempts   INTEGER NOT NULL DEFAULT 0,
    event_type          TEXT NOT NULL DEFAULT 'PAYMENT_FAILED',

    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_CHECKOUTS = """
CREATE TABLE IF NOT EXISTS checkouts (
    checkout_id         TEXT PRIMARY KEY,
    merchant_id         TEXT NOT NULL DEFAULT 'mer_default',
    user_id             TEXT NOT NULL DEFAULT 'usr_default',
    customer_id         TEXT NOT NULL,
    cart_value          REAL NOT NULL,
    drop_off_stage      TEXT NOT NULL,
    time_spent_seconds  INTEGER NOT NULL DEFAULT 60,
    timestamp           TEXT NOT NULL,
    customer_email      TEXT,
    customer_phone      TEXT,
    status              TEXT NOT NULL DEFAULT 'ABANDONED',

    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_RECOVERY_PLANS = """
CREATE TABLE IF NOT EXISTS recovery_plans (
    plan_id                 TEXT PRIMARY KEY,
    merchant_id             TEXT NOT NULL DEFAULT 'mer_default',
    user_id                 TEXT NOT NULL DEFAULT 'usr_default',
    payment_id              TEXT NOT NULL,
    strategy                TEXT NOT NULL,
    steps_json              TEXT NOT NULL,
    priority                TEXT NOT NULL,
    expected_recovery_value REAL NOT NULL,
    created_at              TEXT NOT NULL,

    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_RECOVERY_ATTEMPTS = """
CREATE TABLE IF NOT EXISTS recovery_attempts (
    attempt_id              TEXT PRIMARY KEY,
    merchant_id             TEXT NOT NULL DEFAULT 'mer_default',
    user_id                 TEXT NOT NULL DEFAULT 'usr_default',
    payment_id              TEXT NOT NULL,
    action                  TEXT NOT NULL,
    status                  TEXT NOT NULL,
    reason                  TEXT NOT NULL,
    timestamp               TEXT NOT NULL,
    recovery_link_payment_id TEXT,
    channel_used            TEXT DEFAULT 'SMS',

    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_AUDIT_LOGS = """
CREATE TABLE IF NOT EXISTS audit_logs (
    event_id            TEXT PRIMARY KEY,
    merchant_id         TEXT NOT NULL DEFAULT 'mer_default',
    user_id             TEXT NOT NULL DEFAULT 'usr_default',
    payment_id          TEXT NOT NULL,
    ml_score            REAL NOT NULL,
    expected_value      REAL DEFAULT 0.0,
    priority_tier       TEXT DEFAULT 'MEDIUM',
    ai_diagnosis        TEXT NOT NULL,
    ai_recommendation   TEXT NOT NULL,
    strategy_type       TEXT DEFAULT 'INTELLIGENT_RETRY',
    channel_used        TEXT DEFAULT 'SMS',
    guardrail_result    TEXT NOT NULL,
    action_taken        TEXT NOT NULL,
    result              TEXT NOT NULL,
    timestamp           TEXT NOT NULL,

    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_GROUND_TRUTH = """
CREATE TABLE IF NOT EXISTS ground_truth (
    payment_id                TEXT PRIMARY KEY,
    actual_recovery_outcome   INTEGER NOT NULL,   -- 0 = False, 1 = True

    FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
);
"""

CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS merchant_settings (
    key                  TEXT NOT NULL,
    merchant_id          TEXT NOT NULL DEFAULT 'mer_default',
    user_id              TEXT NOT NULL DEFAULT 'usr_default',
    value                TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (merchant_id, key)
);
"""

CREATE_SCHEDULED_RECOVERY_JOBS = """
CREATE TABLE IF NOT EXISTS scheduled_recovery_jobs (
    job_id            TEXT PRIMARY KEY,
    merchant_id       TEXT NOT NULL DEFAULT 'mer_default',
    user_id           TEXT NOT NULL DEFAULT 'usr_default',
    payment_id        TEXT NOT NULL,
    playbook          TEXT NOT NULL,
    stage             TEXT NOT NULL,
    scheduled_at      TEXT NOT NULL,
    delay_seconds     INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    last_checked_at   TEXT,
    recheck_result    TEXT,
    next_action       TEXT NOT NULL,
    attempt_number    INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'PENDING',

    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_merchants_name       ON merchants(name);",
    "CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_reset_tokens(user_id, expires_at);",
    "CREATE INDEX IF NOT EXISTS idx_users_email          ON users(email);",
    "CREATE INDEX IF NOT EXISTS idx_users_merchant       ON users(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_users_apikey         ON users(api_key);",
    "CREATE INDEX IF NOT EXISTS idx_payments_merchant    ON payments(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_mer_pay     ON payments(merchant_id, payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_customer    ON payments(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_user        ON payments(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_reason      ON payments(failure_reason);",
    "CREATE INDEX IF NOT EXISTS idx_customers_merchant   ON customers(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_customers_mer_cust   ON customers(merchant_id, customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_merchant    ON recovery_attempts(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_payment     ON recovery_attempts(payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_user        ON recovery_attempts(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_merchant       ON audit_logs(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_mer_pay        ON audit_logs(merchant_id, payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_payment        ON audit_logs(payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_user           ON audit_logs(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_plans_merchant       ON recovery_plans(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_plans_payment        ON recovery_plans(payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_checkouts_merchant   ON checkouts(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_checkouts_customer   ON checkouts(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_checkouts_user       ON checkouts(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_merchant        ON scheduled_recovery_jobs(merchant_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_payment         ON scheduled_recovery_jobs(payment_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_user            ON scheduled_recovery_jobs(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status_sched    ON scheduled_recovery_jobs(status, scheduled_at);",
    "CREATE INDEX IF NOT EXISTS idx_settings_merchant    ON merchant_settings(merchant_id);",
]


def init_db() -> None:
    """
    Create all tables and indexes. Safe to call multiple times.
    """
    with get_connection() as conn:
        conn.execute(CREATE_MERCHANTS)
        conn.execute(CREATE_USERS)
        conn.execute(CREATE_PASSWORD_RESETS)
        conn.execute(CREATE_CUSTOMERS)
        conn.execute(CREATE_PAYMENTS)
        conn.execute(CREATE_CHECKOUTS)
        conn.execute(CREATE_RECOVERY_PLANS)
        conn.execute(CREATE_RECOVERY_ATTEMPTS)
        conn.execute(CREATE_AUDIT_LOGS)
        conn.execute(CREATE_GROUND_TRUTH)
        conn.execute(CREATE_SETTINGS)
        conn.execute(CREATE_SCHEDULED_RECOVERY_JOBS)

    if not IS_POSTGRES:
        _safe_migrate()

    with get_connection() as conn:
        for idx_sql in CREATE_INDEXES:
            try:
                conn.execute(idx_sql)
            except Exception as e:
                logger.debug(f"Index creation notice: {e}")

    _seed_default_merchants_and_users()
    logger.info("db.initialized", extra={"database": DATABASE_PATH})



def _safe_migrate() -> None:
    """Add new columns to existing tables safely."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        # 1. Ensure merchants table exists
        conn.execute(CREATE_MERCHANTS)

        # 2. Seed default development merchant
        conn.execute(
            """
            INSERT OR IGNORE INTO merchants (merchant_id, name, email, phone, business_name, created_at, updated_at)
            VALUES ('mer_default', 'RecoverAI Demo Store', 'demo@recoverai.io', '+919876543210', 'RecoverAI Retail', ?, ?)
            """,
            (now, now)
        )

        # 3. Multi-tenant merchant_id & user_id column additions across all tables
        for tbl in ["payments", "customers", "checkouts", "recovery_plans", "recovery_attempts", "audit_logs", "scheduled_recovery_jobs"]:
            try:
                cols = [row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                if "merchant_id" not in cols:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN merchant_id TEXT DEFAULT 'mer_default'")
                if "user_id" not in cols:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id TEXT DEFAULT 'usr_default'")
                # Backfill nulls
                conn.execute(f"UPDATE {tbl} SET merchant_id = 'mer_default' WHERE merchant_id IS NULL OR merchant_id = ''")
            except Exception as e:
                logger.debug(f"Migration check on {tbl}: {e}")

        # users table columns
        user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "merchant_id" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN merchant_id TEXT DEFAULT 'mer_default'")
            conn.execute("UPDATE users SET merchant_id = 'mer_default' WHERE merchant_id IS NULL OR merchant_id = ''")
        if "is_active" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

        # Repair ownership for the original development accounts when an older
        # migration backfilled every user to mer_default.
        conn.execute(
            "UPDATE users SET merchant_id = 'mer_saas' WHERE user_id = 'usr_saas' AND email = 'sarah@saaspay.io' AND EXISTS (SELECT 1 FROM merchants WHERE merchant_id = 'mer_saas')"
        )
        conn.execute(
            "UPDATE users SET merchant_id = 'mer_enterprise' WHERE user_id = 'usr_enterprise' AND email = 'alex@quickretail.com' AND EXISTS (SELECT 1 FROM merchants WHERE merchant_id = 'mer_enterprise')"
        )

        # recovery_attempts columns
        att_cols = [row[1] for row in conn.execute("PRAGMA table_info(recovery_attempts)").fetchall()]
        if "recovery_link_payment_id" not in att_cols:
            conn.execute("ALTER TABLE recovery_attempts ADD COLUMN recovery_link_payment_id TEXT")
        if "channel_used" not in att_cols:
            conn.execute("ALTER TABLE recovery_attempts ADD COLUMN channel_used TEXT DEFAULT 'SMS'")

        # customers columns
        cust_cols = [row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()]
        if "lifetime_value" not in cust_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN lifetime_value REAL DEFAULT 0.0")
        if "preferred_channel" not in cust_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN preferred_channel TEXT DEFAULT 'SMS'")
        if "email" not in cust_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN email TEXT")
        if "phone" not in cust_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN phone TEXT")

        # payments columns
        pay_cols = [row[1] for row in conn.execute("PRAGMA table_info(payments)").fetchall()]
        if "event_type" not in pay_cols:
            conn.execute("ALTER TABLE payments ADD COLUMN event_type TEXT DEFAULT 'PAYMENT_FAILED'")

        # audit_logs columns
        audit_cols = [row[1] for row in conn.execute("PRAGMA table_info(audit_logs)").fetchall()]
        if "expected_value" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN expected_value REAL DEFAULT 0.0")
        if "priority_tier" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN priority_tier TEXT DEFAULT 'MEDIUM'")
        if "strategy_type" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN strategy_type TEXT DEFAULT 'INTELLIGENT_RETRY'")
        if "channel_used" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN channel_used TEXT DEFAULT 'SMS'")

        # merchant_settings table check and compound primary key migration
        try:
            pk_info = conn.execute("PRAGMA table_info(merchant_settings)").fetchall()
            pk_cols = [r[1] for r in pk_info if r[5] > 0]
            sett_cols = [r[1] for r in pk_info]
            if "merchant_id" not in sett_cols:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS merchant_settings_v3 (
                        key                  TEXT NOT NULL,
                        merchant_id          TEXT NOT NULL DEFAULT 'mer_default',
                        user_id              TEXT NOT NULL DEFAULT 'usr_default',
                        value                TEXT NOT NULL,
                        updated_at           TEXT NOT NULL,
                        PRIMARY KEY (merchant_id, key)
                    )
                    """
                )
                conn.execute("INSERT OR IGNORE INTO merchant_settings_v3 (key, merchant_id, user_id, value, updated_at) SELECT key, 'mer_default', COALESCE(user_id, 'usr_default'), value, updated_at FROM merchant_settings")
                conn.execute("DROP TABLE merchant_settings")
                conn.execute("ALTER TABLE merchant_settings_v3 RENAME TO merchant_settings")
        except Exception as e:
            logger.debug(f"merchant_settings migration notice: {e}")


def _seed_default_merchants_and_users() -> None:
    """Seed initial default/demo merchant workspace users if missing."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        from core.auth import hash_password
    except ImportError:
        def hash_password(pwd, salt=None):
            import hashlib, secrets
            s = salt or secrets.token_hex(16)
            h = hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), bytes.fromhex(s), 100_000, dklen=32).hex()
            return h, s

    demo_merchants = [
        {
            "merchant_id": "mer_default",
            "name": "RecoverAI Demo Store",
            "email": "demo@recoverai.io",
            "phone": "+919876543210",
            "business_name": "RecoverAI Retail",
            # Demo workspaces start unconfigured. Merchants must enter their
            # own Razorpay credentials; never ship shared gateway secrets.
            "key_id": None,
            "secret": None,
        },
        {
            "merchant_id": "mer_saas",
            "name": "CloudSaaS Inc",
            "email": "sarah@saaspay.io",
            "phone": "+919811122233",
            "business_name": "CloudSaaS Analytics",
            "key_id": None,
            "secret": None,
        },
        {
            "merchant_id": "mer_enterprise",
            "name": "QuickCommerce Ltd",
            "email": "alex@quickretail.com",
            "phone": "+919944455566",
            "business_name": "QuickCommerce Express",
            "key_id": None,
            "secret": None,
        },
    ]

    demo_users = [
        {
            "user_id": "usr_default",
            "merchant_id": "mer_default",
            "email": "demo@recoverai.io",
            "password": "password123",
            "full_name": "Rohit Kumar",
            "company_name": "RecoverAI Retail",
            "role": "OWNER",
            "api_key": "rec_live_demo_merchant_key",
        },
        {
            "user_id": "usr_saas",
            "merchant_id": "mer_saas",
            "email": "sarah@saaspay.io",
            "password": "password123",
            "full_name": "Sarah Chen",
            "company_name": "CloudSaaS Analytics",
            "role": "OWNER",
            "api_key": "rec_live_saas_merchant_key",
        },
        {
            "user_id": "usr_enterprise",
            "merchant_id": "mer_enterprise",
            "email": "alex@quickretail.com",
            "password": "password123",
            "full_name": "Alex Morgan",
            "company_name": "QuickCommerce Express",
            "role": "OWNER",
            "api_key": "rec_live_enterprise_key",
        },
    ]

    with get_connection() as conn:
        # Remove credentials from older demo database versions, but only when
        # they exactly match the known seeded values. Never overwrite a value
        # a merchant has supplied themselves.
        legacy_credentials = {
            "mer_default": ("rzp_test_demo_merchant", "whsec_demo_default"),
            "mer_saas": ("rzp_test_saas", "whsec_saas_secret"),
            "mer_enterprise": ("rzp_test_enterprise", "whsec_enterprise_secret"),
        }
        for merchant_id, (legacy_key, legacy_secret) in legacy_credentials.items():
            conn.execute(
                """
                UPDATE merchants
                SET razorpay_key_id = CASE WHEN razorpay_key_id = ? THEN NULL ELSE razorpay_key_id END,
                    razorpay_webhook_secret = CASE WHEN razorpay_webhook_secret = ? THEN NULL ELSE razorpay_webhook_secret END
                WHERE merchant_id = ?
                """,
                (legacy_key, legacy_secret, merchant_id),
            )
        for m in demo_merchants:
            conn.execute(
                """
                INSERT OR IGNORE INTO merchants (merchant_id, name, email, phone, business_name, razorpay_key_id, razorpay_webhook_secret, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (m["merchant_id"], m["name"], m["email"], m["phone"], m["business_name"], m["key_id"], m["secret"], now, now),
            )

        for u in demo_users:
            existing = conn.execute("SELECT user_id FROM users WHERE email = ? OR user_id = ?", (u["email"], u["user_id"])).fetchone()
            if not existing:
                h, s = hash_password(u["password"])
                conn.execute(
                    """
                    INSERT INTO users (user_id, merchant_id, email, password_hash, salt, full_name, company_name, role, api_key, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (u["user_id"], u["merchant_id"], u["email"], h, s, u["full_name"], u["company_name"], u["role"], u["api_key"], now, now),
                )


def drop_all_tables() -> None:
    """Wipe all tables (used for tests/data generation reset)."""
    tables = [
        "audit_logs",
        "recovery_plans",
        "recovery_attempts",
        "password_reset_tokens",
        "ground_truth",
        "checkouts",
        "payments",
        "customers",
        "merchant_settings",
        "scheduled_recovery_jobs",
        "users",
        "merchants",
    ]
    with get_connection() as conn:
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    logger.warning("db.tables_dropped", extra={"database": DATABASE_PATH})


# ── Merchant CRUD Helpers ─────────────────────────────────────────────────────

def create_merchant(
    merchant_id: str,
    name: str,
    business_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    razorpay_key_id: Optional[str] = None,
    razorpay_webhook_secret: Optional[str] = None,
) -> sqlite3.Row:
    """Create a new merchant organization record."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO merchants (merchant_id, name, business_name, email, phone, razorpay_key_id, razorpay_webhook_secret, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (merchant_id, name.strip(), business_name.strip(), email, phone, razorpay_key_id, razorpay_webhook_secret, now, now),
        )
    return fetch_merchant_by_id(merchant_id)


def fetch_merchant_by_id(merchant_id: str) -> sqlite3.Row | None:
    """Fetch merchant organization by merchant_id."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM merchants WHERE merchant_id = ?", (merchant_id,)).fetchone()


def fetch_merchant_by_webhook_secret(secret: str) -> sqlite3.Row | None:
    """Look up merchant by configured webhook secret."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM merchants WHERE razorpay_webhook_secret = ?", (secret,)).fetchone()


def fetch_all_merchants() -> list[sqlite3.Row]:
    """List all registered merchants."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM merchants ORDER BY created_at ASC").fetchall()



def fetch_merchant_by_api_key(api_key: str) -> sqlite3.Row | None:
    """Look up merchant by an active user API key."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT m.* FROM merchants m
            JOIN users u ON m.merchant_id = u.merchant_id
            WHERE u.api_key = ? AND u.is_active = 1
            LIMIT 1
            """,
            (api_key,)
        ).fetchone()
        return row


def update_merchant(
    merchant_id: str,
    name: Optional[str] = None,
    business_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    razorpay_key_id: Optional[str] = None,
    razorpay_webhook_secret: Optional[str] = None,
) -> sqlite3.Row | None:
    """Update merchant organization profile details."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE merchants
            SET name = COALESCE(?, name),
                business_name = COALESCE(?, business_name),
                email = COALESCE(?, email),
                phone = COALESCE(?, phone),
                razorpay_key_id = COALESCE(?, razorpay_key_id),
                razorpay_webhook_secret = COALESCE(?, razorpay_webhook_secret),
                updated_at = ?
            WHERE merchant_id = ?
            """,
            (name, business_name, email, phone, razorpay_key_id, razorpay_webhook_secret, now, merchant_id),
        )
    return fetch_merchant_by_id(merchant_id)


# ── User CRUD Helpers ─────────────────────────────────────────────────────────

def create_user(
    user_id: str,
    email: str,
    password_hash: str,
    salt: str,
    full_name: str,
    merchant_id: str = "mer_default",
    company_name: str = "My Store",
    role: str = "OWNER",
    api_key: Optional[str] = None,
) -> sqlite3.Row:
    """Create a new merchant user profile associated with a merchant."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, merchant_id, email, password_hash, salt, full_name, company_name, role, api_key, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (user_id, merchant_id, email.lower().strip(), password_hash, salt, full_name.strip(), company_name.strip(), role, api_key, now, now),
        )
    return fetch_user_by_id(user_id)


def fetch_user_by_email(email: str) -> sqlite3.Row | None:
    """Fetch user by normalized email."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()


def fetch_user_by_id(user_id: str) -> sqlite3.Row | None:
    """Fetch user by unique user_id."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def fetch_user_by_api_key(api_key: str) -> sqlite3.Row | None:
    """Fetch user by API key."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone()


def fetch_all_users(merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """List registered users for a merchant organization."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                "SELECT user_id, merchant_id, email, full_name, company_name, role, api_key, is_active, created_at, last_login_at FROM users WHERE merchant_id = ? ORDER BY created_at ASC",
                (merchant_id,)
            ).fetchall()
        return conn.execute("SELECT user_id, merchant_id, email, full_name, company_name, role, api_key, is_active, created_at, last_login_at FROM users ORDER BY created_at ASC").fetchall()


def update_user_profile(
    user_id: str,
    full_name: Optional[str] = None,
    company_name: Optional[str] = None,
    password_hash: Optional[str] = None,
    salt: Optional[str] = None,
) -> sqlite3.Row | None:
    """Update user profile fields."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if password_hash and salt:
            conn.execute(
                """
                UPDATE users
                SET full_name = COALESCE(?, full_name),
                    company_name = COALESCE(?, company_name),
                    password_hash = ?,
                    salt = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (full_name, company_name, password_hash, salt, now, user_id),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET full_name = COALESCE(?, full_name),
                    company_name = COALESCE(?, company_name),
                    updated_at = ?
                WHERE user_id = ?
                """,
                (full_name, company_name, now, user_id),
            )
    return fetch_user_by_id(user_id)


def update_user_last_login(user_id: str) -> None:
    """Update user last login timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE user_id = ?", (now, user_id))


def update_user_api_key(user_id: str, new_api_key: str) -> sqlite3.Row | None:
    """Regenerate merchant API key."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE users SET api_key = ?, updated_at = ? WHERE user_id = ?", (new_api_key, now, user_id))
    return fetch_user_by_id(user_id)


# ── Query Helpers (Strict Tenant Scoping via merchant_id) ─────────────────────

def fetch_payment(payment_id: str, merchant_id: Optional[str] = None) -> sqlite3.Row | None:
    """
    Fetch a single payment. When merchant_id is provided, enforce strict tenant isolation.
    Returns None if payment does not exist or does not belong to the merchant.
    """
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                "SELECT * FROM payments WHERE payment_id = ? AND merchant_id = ?", (payment_id, merchant_id)
            ).fetchone()
        return conn.execute(
            "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
        ).fetchone()


def fetch_customer(customer_id: str, merchant_id: Optional[str] = None) -> sqlite3.Row | None:
    """Fetch customer record strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                "SELECT * FROM customers WHERE customer_id = ? AND merchant_id = ?", (customer_id, merchant_id)
            ).fetchone()
        return conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()


def fetch_all_payments(merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve payments strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute("SELECT * FROM payments WHERE merchant_id = ? ORDER BY timestamp DESC", (merchant_id,)).fetchall()
        return conn.execute("SELECT * FROM payments ORDER BY timestamp DESC").fetchall()


def fetch_all_customers(merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve customers strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute("SELECT * FROM customers WHERE merchant_id = ?", (merchant_id,)).fetchall()
        return conn.execute("SELECT * FROM customers").fetchall()


def fetch_all_audit_logs(merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve audit logs strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute("SELECT * FROM audit_logs WHERE merchant_id = ? ORDER BY timestamp DESC", (merchant_id,)).fetchall()
        return conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC").fetchall()


def fetch_ground_truth(payment_id: str) -> bool | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT actual_recovery_outcome FROM ground_truth WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()
    if row is None:
        return None
    return bool(row["actual_recovery_outcome"])


def fetch_all_ground_truth() -> dict[str, bool]:
    with get_connection() as conn:
        rows = conn.execute("SELECT payment_id, actual_recovery_outcome FROM ground_truth").fetchall()
        return {r["payment_id"]: bool(r["actual_recovery_outcome"]) for r in rows}


def fetch_recent_recovery_attempts(payment_id: str, merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve recovery attempts for a payment scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                "SELECT * FROM recovery_attempts WHERE payment_id = ? AND merchant_id = ? ORDER BY timestamp DESC",
                (payment_id, merchant_id),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM recovery_attempts WHERE payment_id = ? ORDER BY timestamp DESC",
            (payment_id,),
        ).fetchall()


def save_recovery_plan(
    plan_id: str,
    payment_id: str,
    strategy: str,
    steps: list,
    priority: str,
    expected_recovery_value: float,
    created_at: str,
    merchant_id: str = "mer_default",
    user_id: str = "usr_default",
) -> None:
    """Save or update a structured Recovery Plan with merchant ownership."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO recovery_plans
                (plan_id, merchant_id, user_id, payment_id, strategy, steps_json, priority, expected_recovery_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                merchant_id,
                user_id,
                payment_id,
                strategy,
                json.dumps(steps),
                priority,
                expected_recovery_value,
                created_at,
            ),
        )


def fetch_recovery_plan(payment_id: str, merchant_id: Optional[str] = None) -> dict | None:
    """Fetch the latest recovery plan for a payment strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            row = conn.execute(
                "SELECT * FROM recovery_plans WHERE payment_id = ? AND merchant_id = ? ORDER BY created_at DESC LIMIT 1",
                (payment_id, merchant_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM recovery_plans WHERE payment_id = ? ORDER BY created_at DESC LIMIT 1",
                (payment_id,),
            ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["steps"] = json.loads(d["steps_json"])
    except Exception:
        d["steps"] = []
    return d


def save_checkout_event(
    checkout_id: str,
    customer_id: str,
    cart_value: float,
    drop_off_stage: str,
    time_spent_seconds: int,
    timestamp: str,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    merchant_id: str = "mer_default",
    user_id: str = "usr_default",
) -> None:
    """Store a checkout abandonment event with merchant ownership."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO checkouts
                (checkout_id, merchant_id, user_id, customer_id, cart_value, drop_off_stage, time_spent_seconds, timestamp, customer_email, customer_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkout_id,
                merchant_id,
                user_id,
                customer_id,
                cart_value,
                drop_off_stage,
                time_spent_seconds,
                timestamp,
                customer_email,
                customer_phone,
            ),
        )


def fetch_all_checkouts(merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve checkouts strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute("SELECT * FROM checkouts WHERE merchant_id = ? ORDER BY timestamp DESC", (merchant_id,)).fetchall()
        return conn.execute("SELECT * FROM checkouts ORDER BY timestamp DESC").fetchall()


def fetch_setting(key: str, default: str = "", merchant_id: str = "mer_default") -> str:
    """Retrieve a configuration value for a specific merchant tenant."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM merchant_settings WHERE key = ? AND merchant_id = ?", (key, merchant_id)
        ).fetchone()
        return row["value"] if row else default


def save_setting(key: str, value: str, merchant_id: str = "mer_default") -> None:
    """Store or update a configuration value for a specific merchant tenant."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO merchant_settings (key, merchant_id, user_id, value, updated_at) VALUES (?, ?, ?, ?, ?)",
            (key, merchant_id, "usr_" + merchant_id, str(value), now)
        )


def fetch_all_settings(merchant_id: str = "mer_default") -> dict[str, str]:
    """Retrieve all merchant settings for a specific merchant tenant."""
    with get_connection() as conn:
        # Never merge the default/demo merchant's settings into another
        # workspace. A new tenant must start with its own empty integration
        # credentials and receive only application-level defaults from the API.
        rows = conn.execute(
            "SELECT key, value FROM merchant_settings WHERE merchant_id = ?", (merchant_id,)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}


def save_scheduled_job(
    job_id: str,
    payment_id: str,
    playbook: str,
    stage: str,
    scheduled_at: str,
    delay_seconds: int,
    next_action: str,
    attempt_number: int = 0,
    status: str = "PENDING",
    merchant_id: str = "mer_default",
    user_id: str = "usr_default",
) -> None:
    """Store a scheduled recovery job with merchant ownership."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scheduled_recovery_jobs
                (job_id, merchant_id, user_id, payment_id, playbook, stage, scheduled_at, delay_seconds,
                 created_at, next_action, attempt_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                merchant_id,
                user_id,
                payment_id,
                playbook,
                stage,
                scheduled_at,
                delay_seconds,
                now,
                next_action,
                attempt_number,
                status,
            ),
        )


def fetch_due_recovery_jobs(now_iso: Optional[str] = None, merchant_id: Optional[str] = None) -> list[sqlite3.Row]:
    """Retrieve all pending recovery jobs that have reached scheduled execution time."""
    if not now_iso:
        now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                """
                SELECT * FROM scheduled_recovery_jobs
                WHERE status = 'PENDING' AND scheduled_at <= ? AND merchant_id = ?
                ORDER BY scheduled_at ASC
                LIMIT 10
                """,
                (now_iso, merchant_id),
            ).fetchall()
        return conn.execute(
            """
            SELECT * FROM scheduled_recovery_jobs
            WHERE status = 'PENDING' AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
            LIMIT 10
            """,
            (now_iso,),
        ).fetchall()


def update_job_stage(
    job_id: str,
    stage: str,
    status: str,
    recheck_result: Optional[str] = None,
    last_checked_at: Optional[str] = None,
) -> None:
    """Update execution stage and status of a scheduled job."""
    if not last_checked_at:
        last_checked_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scheduled_recovery_jobs
            SET stage = ?, status = ?, recheck_result = COALESCE(?, recheck_result),
                last_checked_at = ?
            WHERE job_id = ?
            """,
            (stage, status, recheck_result, last_checked_at, job_id),
        )


def fetch_scheduled_job(payment_id: str, merchant_id: Optional[str] = None) -> sqlite3.Row | None:
    """Fetch the latest recovery job for a payment strictly scoped to merchant_id."""
    with get_connection() as conn:
        if merchant_id:
            return conn.execute(
                "SELECT * FROM scheduled_recovery_jobs WHERE payment_id = ? AND merchant_id = ? ORDER BY created_at DESC LIMIT 1",
                (payment_id, merchant_id),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM scheduled_recovery_jobs WHERE payment_id = ? ORDER BY created_at DESC LIMIT 1",
            (payment_id,),
        ).fetchone()


# Ensure DB schema and migrations are initialized on module load
try:
    init_db()
except Exception as e:
    logger.error(f"Failed to auto-initialize database schema: {e}")
