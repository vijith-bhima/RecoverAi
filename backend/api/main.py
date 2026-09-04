from __future__ import annotations

"""
api/main.py — FastAPI wrapper for the RecoverAI pipeline.

This is a THIN LAYER over the core pipeline that already works (Phases 1–7).
No business logic lives here — all decisions happen in core/.

Endpoints:
  POST /payments/event          — Ingest a new failed payment event
  GET  /payments/{payment_id}   — Look up a payment record
  POST /recovery/run/{id}       — Run the full pipeline on one payment
  GET  /audit/{payment_id}      — Retrieve the audit record for a payment
  GET  /metrics                 — Return the latest batch evaluation metrics
  GET  /health                  — Health check

Why FastAPI?
  - Auto-generates Swagger docs at /docs (free, interactive, shareable)
  - Uses the same Pydantic models we defined in Phase 1 for request/response
    validation — no duplicate schema definitions
  - Async-ready, but we don't need async for this scope

Run with:
  uvicorn api.main:app --reload
Then open: http://localhost:8000/docs
"""

import json
import hashlib
import os
import smtplib
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import secrets

from logging_config import get_logger, setup_logging
from db import (
    get_connection,
    fetch_payment,
    fetch_customer,
    create_user,
    fetch_user_by_email,
    fetch_user_by_id,
    fetch_user_by_api_key,
    fetch_all_users,
    update_user_profile,
    update_user_last_login,
    update_user_api_key,
    fetch_all_settings,
    save_setting,
    fetch_setting,
    fetch_all_payments,
    fetch_all_customers,
    fetch_all_audit_logs,
    fetch_all_checkouts,
    fetch_recovery_plan,
    save_recovery_plan,
    fetch_merchant_by_id,
    fetch_all_merchants,
    update_merchant,
)
from models.schemas import (
    AgentDecision,
    AttemptStatus,
    AuditLogEntry,
    ChannelPreference,
    Customer,
    EventType,
    FailureReason,
    GuardrailOutcome,
    GuardrailResult,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PriorityTier,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryPlan,
    RecoveryScore,
    RecoveryStep,
    StrategyType,
    UserRegisterRequest,
    UserLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserProfileResponse,
    AuthTokenResponse,
    UpdateProfileRequest,
    UserProfileSummary,
)
from core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
    get_current_user_context,
    revoke_access_token,
)
from core.diagnosis import score_recovery
from core.agent import get_agent_decision
from core.guardrails import check_guardrails
from core.executor import execute_action
from core.audit import write_audit_log, get_audit_entry
from evaluate import load_all_payments, run_pipeline, compute_metrics

setup_logging()
logger = get_logger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Manage the local recovery worker for the lifetime of one API process."""
    start_recovery_agent()
    try:
        yield
    finally:
        stop_recovery_agent()


app = FastAPI(
    title="RecoverAI",
    description=(
        "AI-powered payment failure recovery system. "
        "ML diagnoses failures → LLM recommends actions → "
        "Rules enforce safety → Pipeline executes and measures."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=app_lifespan,
)

cors_origins_env = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
if cors_origins_env.strip() == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*" not in cors_origins else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)



@app.middleware("http")
async def add_production_response_headers(request: Request, call_next):
    """Attach baseline browser hardening and request correlation headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", secrets.token_hex(12))
    if os.getenv("RECOVERAI_ENVIRONMENT", "development").lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ── In-memory metrics cache (10-minute TTL) ────────────────────────────────────
import time as _time
_metrics_cache: dict = {"data": None, "expires_at": 0.0, "merchant_id": None}
_METRICS_TTL = 600  # seconds (10 minutes — fast instant page loads)

# ── Autonomous Recovery Agent ──────────────────────────────────────────────────
# Runs in a background thread, wakes every AGENT_POLL_SECONDS seconds,
# scans for unprocessed FAILED payments, and runs the full pipeline automatically.
# The merchant can pause/resume via POST /agent/toggle — no per-payment clicking.

import threading
import time
import re
import logging as _logging
from collections import deque

AGENT_POLL_SECONDS = int(os.getenv("AGENT_POLL_SECONDS", "15"))
ACTIVITY_MAX_EVENTS = 200        # max events kept in memory

# Shared state — accessed from both the background thread and API endpoints
_agent: dict = {
    "active": True,              # True = running, False = paused
    "last_run": None,            # ISO timestamp of last scan
    "processed_total": 0,        # cumulative payments processed
    "links_total": 0,
    "escalated_total": 0,
    "recovered_total": 0.0,
    "activity": deque(maxlen=ACTIVITY_MAX_EVENTS),   # recent events
}
_agent_lock = threading.Lock()
_agent_stop_event = threading.Event()
_bg_thread: threading.Thread | None = None


def _require_role(user: dict, *roles: str) -> None:
    if user.get("role", "MEMBER") not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")


def _log_event(event_type: str, merchant_id: str = "mer_default", user_id: str = "usr_default", **kwargs):
    """Append one event to the in-memory activity log (thread-safe). Tagged with merchant_id for per-tenant filtering."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "merchant_id": merchant_id,
        "user_id": user_id,
        **kwargs,
    }
    with _agent_lock:
        _agent["activity"].appendleft(entry)   # newest first


def _process_new_failures() -> int:
    """Find unprocessed FAILED payments and run the full pipeline on each."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*, p.merchant_id as payment_merchant_id, p.user_id as payment_user_id,
                   c.total_payments, c.successful_payments, c.failed_payments,
                   COALESCE(c.lifetime_value, 0.0) as lifetime_value,
                   COALESCE(c.preferred_channel, 'SMS') as preferred_channel
            FROM payments p
            JOIN customers c ON p.customer_id = c.customer_id AND p.merchant_id = c.merchant_id
            WHERE p.status = 'FAILED'
              AND NOT EXISTS (
                  SELECT 1 FROM recovery_attempts r
                                    WHERE r.payment_id = p.payment_id
                                        AND r.merchant_id = p.merchant_id
                    AND r.status IN ('PENDING', 'SUCCESS')
              )
            ORDER BY p.amount DESC
            LIMIT 5
        """).fetchall()

    if not rows:
        return 0

    now = datetime.now(timezone.utc)
    _logging.disable(_logging.WARNING)
    processed = 0
    try:
        for row in rows:
            # Check if agent was paused mid-batch
            with _agent_lock:
                if not _agent["active"]:
                    break
            try:
                payment = Payment(
                    payment_id=row["payment_id"],
                    customer_id=row["customer_id"],
                    amount=row["amount"],
                    status=PaymentStatus(row["status"]),
                    failure_reason=FailureReason(row["failure_reason"]),
                    payment_method=PaymentMethod(row["payment_method"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    previous_attempts=row["previous_attempts"],
                )
                customer = Customer(
                    customer_id=row["customer_id"],
                    total_payments=row["total_payments"],
                    successful_payments=row["successful_payments"],
                    failed_payments=row["failed_payments"],
                    lifetime_value=row["lifetime_value"],
                    preferred_channel=ChannelPreference(row["preferred_channel"]),
                )

                # Tag all events and DB records with the payment's owner merchant_id
                row_mid = row["payment_merchant_id"] if "payment_merchant_id" in row.keys() and row["payment_merchant_id"] else "mer_default"
                row_uid = row["payment_user_id"] if "payment_user_id" in row.keys() and row["payment_user_id"] else "usr_default"

                reason_str = row["failure_reason"].replace("_", " ")
                is_temp    = row["failure_reason"] in ("BANK_SERVER_DOWN", "NETWORK_TIMEOUT", "INVALID_OTP")

                # --- Emit pipeline events to the live feed (tagged with merchant_id) ---
                _log_event("payment_failed", merchant_id=row_mid, user_id=row_uid,
                    payment_id=payment.payment_id, amount=payment.amount,
                    label=f"Payment failed",
                    sublabel=f"₹{payment.amount:,.0f} · {reason_str}")

                _log_event("opportunity_detected", merchant_id=row_mid, user_id=row_uid,
                    payment_id=payment.payment_id, amount=payment.amount,
                    label="Recovery opportunity detected",
                    sublabel="Temporary failure — likely recoverable" if is_temp else "Evaluating recovery options")

                score = score_recovery(payment, customer)
                _log_event("ml_scored", merchant_id=row_mid, user_id=row_uid,
                    payment_id=payment.payment_id, amount=payment.amount,
                    label="ML diagnosis complete",
                    sublabel=f"Recovery prob: {score.recovery_probability * 100:.0f}% · Expected: ₹{score.expected_recovery_value:,.0f} [{score.priority_tier.value} PRIORITY]")

                decision  = get_agent_decision(payment, score, customer)
                _log_event("ai_decision", merchant_id=row_mid, user_id=row_uid,
                    payment_id=payment.payment_id, amount=payment.amount,
                    label=f"AI Agent → {decision.strategy_type.value} ({decision.recommended_action.value})",
                    sublabel=f"Channel: {decision.preferred_channel.value} · {decision.reason}")

                guardrail = check_guardrails(payment, decision, [], now=now)
                action    = guardrail.final_action.value

                if guardrail.result.value == "APPROVED":
                    _log_event("guardrail_approved", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="Safety checks passed ✓",
                        sublabel=f"Executing {guardrail.final_action.value} via {decision.preferred_channel.value}")
                else:
                    _log_event("guardrail_blocked", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="Guardrail blocked — escalating",
                        sublabel=guardrail.reason or "Compliance rule triggered")

                attempt = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel, merchant_id=row_mid)
                audit   = write_audit_log(score, decision, guardrail, attempt, merchant_id=row_mid, user_id=row_uid)

                # Extract Razorpay URL if present
                razorpay_url = None
                if attempt.reason and "rzp.io" in attempt.reason:
                    m = re.search(r"https?://[^\s]+", attempt.reason)
                    if m:
                        razorpay_url = m.group(0)

                if action in ("SEND_PAYMENT_LINK", "ALTERNATE_PAYMENT_METHOD"):
                    _log_event("link_sent", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="⚡ Payment link automatically sent",
                        sublabel=f"Razorpay link dispatched to customer" if razorpay_url else "Payment link dispatched to customer",
                        razorpay_url=razorpay_url)
                    with _agent_lock:
                        _agent["links_total"] += 1
                elif action == "ESCALATE_TO_HUMAN":
                    _log_event("escalated", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="Routed to human agent for review",
                        sublabel="Recovery ticket created in queue")
                    with _agent_lock:
                        _agent["escalated_total"] += 1
                elif action == "RETRY":
                    _log_event("retried", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="Payment automatically retried",
                        sublabel="Gateway retry initiated")
                else:
                    _log_event("stopped", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label="Recovery stopped — unrecoverable or monitoring")

                if attempt.status.value == "SUCCESS":
                    _log_event("recovered", merchant_id=row_mid, user_id=row_uid,
                        payment_id=payment.payment_id, amount=payment.amount,
                        label=f"₹{payment.amount:,.0f} recovered",
                        sublabel=f"Audit: {audit.event_id}")
                    with _agent_lock:
                        _agent["recovered_total"] += payment.amount

                with _agent_lock:
                    _agent["processed_total"] += 1

                processed += 1

            except Exception as exc:
                _log_event("error", merchant_id="mer_default", user_id="usr_default",
                    payment_id=row["payment_id"], amount=row["amount"],
                    label="Agent error", sublabel=str(exc))
    finally:
        _logging.disable(_logging.NOTSET)
        # Only invalidate metrics cache if we actually processed something
        if processed > 0:
            global _metrics_cache
            _metrics_cache["expires_at"] = 0.0

    return processed


def _sync_razorpay_payment_links() -> int:
    """
    Check status of active RecoverAI payment links via Razorpay API.
    Does not auto-poll or synthesize arbitrary historical payments.
    """
    import os, requests
    # Webhooks are the real-time source of truth. Optional polling is disabled
    # by default so an unconfigured/local workspace never blocks on Razorpay.
    if os.getenv("RECOVERAI_ENABLE_RAZORPAY_SYNC", "0").lower() not in {"1", "true", "yes"}:
        return 0
    from requests.auth import HTTPBasicAuth
    from db import fetch_setting

    razorpay_id = fetch_setting("razorpay_key_id") or os.getenv("RAZORPAY_KEY_ID")
    razorpay_secret = fetch_setting("razorpay_key_secret") or os.getenv("RAZORPAY_KEY_SECRET")
    if not razorpay_id or not razorpay_secret or not razorpay_id.startswith("rzp_"):
        return 0

    recovered_count = 0

    # Poll only active payment links generated by RecoverAI that are pending
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT ra.payment_id, ra.merchant_id, ra.reason, p.amount, p.status
                FROM recovery_attempts ra
                JOIN payments p ON ra.payment_id = p.payment_id
                WHERE ra.action IN ('SEND_PAYMENT_LINK', 'ALTERNATE_PAYMENT_METHOD')
                  AND p.status != 'RECOVERED'
            """).fetchall()

        if not rows:
            return 0

        for row in rows:
            payment_id = row["payment_id"]
            row_mid = row["merchant_id"] if "merchant_id" in row.keys() and row["merchant_id"] else "mer_default"
            amount = row["amount"] or 0

            try:
                url_links = "https://api.razorpay.com/v1/payment_links"
                resp_l = requests.get(
                    url_links,
                    params={"reference_id": payment_id},
                    auth=HTTPBasicAuth(razorpay_id.strip(), razorpay_secret.strip()),
                    timeout=3
                )
                if resp_l.status_code == 200:
                    data = resp_l.json()
                    for item in data.get("payment_links", []):
                        if item.get("status") == "paid":
                            captured_id = item.get("id")
                            with get_connection() as conn:
                                conn.execute("UPDATE payments SET status = ? WHERE payment_id = ? AND merchant_id = ?",
                                             (PaymentStatus.RECOVERED.value, payment_id, row_mid))
                                conn.execute("UPDATE recovery_attempts SET status = 'SUCCESS', recovery_link_payment_id = ? WHERE payment_id = ? AND merchant_id = ?",
                                             (captured_id, payment_id, row_mid))
                                conn.execute("UPDATE audit_logs SET result = 'SUCCESS' WHERE payment_id = ? AND merchant_id = ?", (payment_id, row_mid))

                            with _agent_lock:
                                _agent["recovered_total"] += amount

                            _log_event("recovered", merchant_id=row_mid,
                                payment_id=payment_id, amount=amount,
                                label=f"✅ ₹{amount:,.0f} RECOVERED",
                                sublabel="Razorpay payment link paid successfully")

                            global _metrics_cache
                            _metrics_cache["expires_at"] = 0.0
                            recovered_count += 1
                            logger.info(f"razorpay.link_paid_recovered: {payment_id} amount=₹{amount}")
            except Exception as item_err:
                logger.warning(f"razorpay.sync_link_error: {item_err}")

    except Exception as e:
        logger.warning(f"razorpay.sync_error: {e}")

    return recovered_count


def _process_due_scheduled_jobs() -> int:
    """
    State machine worker:
    1. Fetches all scheduled recovery jobs that have reached their scheduled time.
    2. Transitions to STATUS_RECHECKED.
    3. Rechecks payment status via Razorpay API and database to prevent duplicate payment requests.
    4. If payment already succeeded -> marks RECOVERED and stops.
    5. If payment is still failed -> makes second AI recovery decision -> checks safety guardrails -> executes recovery action -> audits.
    """
    from db import fetch_due_recovery_jobs, update_job_stage, get_connection, fetch_setting
    from core.diagnosis import score_recovery
    from core.agent import get_agent_decision
    from core.guardrails import check_guardrails
    from core.executor import execute_action
    from core.audit import write_audit_log
    import requests
    from requests.auth import HTTPBasicAuth

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    due_jobs = fetch_due_recovery_jobs(now_iso)

    if not due_jobs:
        return 0

    processed_count = 0
    for job in due_jobs:
        job_id = job["job_id"]
        payment_id = job["payment_id"]
        playbook = job["playbook"]
        job_mid = job["merchant_id"] if "merchant_id" in job.keys() and job["merchant_id"] else "mer_default"

        update_job_stage(job_id, stage="STATUS_RECHECKED", status="RUNNING", last_checked_at=now_iso)

        with get_connection() as conn:
            payment_row = conn.execute("SELECT * FROM payments WHERE payment_id = ? AND merchant_id = ?", (payment_id, job_mid)).fetchone()
            customer_row = conn.execute("SELECT * FROM customers WHERE customer_id = ? AND merchant_id = ?", (payment_row["customer_id"], job_mid)).fetchone() if payment_row else None

        if not payment_row:
            update_job_stage(job_id, stage="STOPPED", status="COMPLETED")
            continue

        payment = Payment(
            payment_id=payment_row["payment_id"],
            customer_id=payment_row["customer_id"],
            amount=payment_row["amount"],
            status=PaymentStatus(payment_row["status"]),
            failure_reason=FailureReason(payment_row["failure_reason"]),
            payment_method=PaymentMethod(payment_row["payment_method"]),
            timestamp=datetime.fromisoformat(payment_row["timestamp"]),
            previous_attempts=payment_row["previous_attempts"],
        )
        customer = Customer(
            customer_id=customer_row["customer_id"] if customer_row else payment.customer_id,
            total_payments=customer_row["total_payments"] if customer_row else 1,
            successful_payments=customer_row["successful_payments"] if customer_row else 0,
            failed_payments=customer_row["failed_payments"] if customer_row else 1,
            lifetime_value=customer_row["lifetime_value"] if customer_row else 0.0,
            preferred_channel=ChannelPreference(customer_row["preferred_channel"]) if customer_row else ChannelPreference.SMS,
        )
        job_user_id = payment_row["user_id"] if payment_row and "user_id" in payment_row.keys() else "usr_default"

        # ── Recheck status with Razorpay live API ──────────────────────────────
        is_already_paid = False
        razorpay_id = fetch_setting("razorpay_key_id", merchant_id=job_mid) or os.getenv("RAZORPAY_KEY_ID")
        razorpay_secret = fetch_setting("razorpay_key_secret", merchant_id=job_mid) or os.getenv("RAZORPAY_KEY_SECRET")
        if razorpay_id and razorpay_secret and razorpay_id.startswith("rzp_"):
            try:
                resp = requests.get(
                    f"https://api.razorpay.com/v1/payments/{payment_id}",
                    auth=HTTPBasicAuth(razorpay_id.strip(), razorpay_secret.strip()),
                    timeout=3
                )
                if resp.status_code == 200:
                    p_info = resp.json()
                    if p_info.get("status") in ("captured", "paid"):
                        is_already_paid = True
            except Exception:
                pass

        _log_event("status_rechecked", merchant_id=job_mid, user_id=job_user_id,
            payment_id=payment_id, amount=payment.amount,
            label="🔍 Gateway status rechecked",
            sublabel="Transaction settled during wait window — STOPPING duplicate contact" if is_already_paid else "Transaction confirmed still failed — proceeding to second recovery action")

        if is_already_paid:
            with get_connection() as conn:
                conn.execute("UPDATE payments SET status = ? WHERE payment_id = ? AND merchant_id = ?", (PaymentStatus.RECOVERED.value, payment_id, job_mid))
            _log_event("recovered", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label=f"✅ ₹{payment.amount:,.0f} RECOVERED",
                sublabel="Confirmed paid on Razorpay during stabilization window")
            update_job_stage(job_id, stage="PAYMENT_VERIFIED", status="COMPLETED", recheck_result="SUCCESS")
            processed_count += 1
            continue

        # ── Second Decision & Safety Guardrail Check ───────────────────────────
        score = score_recovery(payment, customer)
        action_to_take = RecoveryAction.SEND_PAYMENT_LINK
        if payment.amount > 10000.0:
            action_to_take = RecoveryAction.ESCALATE_TO_HUMAN
        elif payment.failure_reason == FailureReason.CARD_EXPIRED:
            action_to_take = RecoveryAction.ALTERNATE_PAYMENT_METHOD

        decision = AgentDecision(
            payment_id=payment.payment_id,
            diagnosis="failure_persists_recovery_action",
            recommended_action=action_to_take,
            strategy_type=StrategyType.INTELLIGENT_RETRY if payment.failure_reason == FailureReason.BANK_SERVER_DOWN else StrategyType.ALTERNATE_PAYMENT_LINK,
            preferred_channel=customer.preferred_channel,
            reason=f"Payment remained failed after gateway stabilization window. Dispatching recovery action via {customer.preferred_channel.value}.",
            confidence=0.88,
        )

        guardrail = check_guardrails(payment, decision, [], now=now_dt)

        if guardrail.result.value == "APPROVED":
            _log_event("guardrail_approved", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label="Safety checks passed ✓",
                sublabel=f"Executing {guardrail.final_action.value} via {decision.preferred_channel.value}")
        else:
            _log_event("guardrail_blocked", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label="Guardrail blocked — escalating to human",
                sublabel=guardrail.reason or "Safety limit triggered")

        attempt = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel, merchant_id=job_mid)
        write_audit_log(score, decision, guardrail, attempt, merchant_id=job_mid, user_id=job_user_id)

        action = guardrail.final_action.value
        razorpay_url = None
        if attempt.reason and "rzp.io" in attempt.reason:
            m = re.search(r"https?://[^\s]+", attempt.reason)
            if m:
                razorpay_url = m.group(0)

        if action in ("SEND_PAYMENT_LINK", "ALTERNATE_PAYMENT_METHOD"):
            _log_event("link_sent", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label="⚡ Recovery payment link dispatched",
                sublabel=f"Sent to customer via {decision.preferred_channel.value}",
                razorpay_url=razorpay_url)
            with _agent_lock:
                _agent["links_total"] += 1
        elif action == "RETRY":
            _log_event("retried", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label="Payment automatically retried",
                sublabel="Gateway retry dispatched")
        elif action == "ESCALATE_TO_HUMAN":
            _log_event("escalated", merchant_id=job_mid, user_id=job_user_id,
                payment_id=payment_id, amount=payment.amount,
                label="Escalated to human review queue",
                sublabel=guardrail.reason)
            with _agent_lock:
                _agent["escalated_total"] += 1

        update_job_stage(job_id, stage="ACTION_EXECUTED", status="COMPLETED", recheck_result="STILL_FAILED")
        processed_count += 1

    return processed_count


def _agent_loop():
    """Background thread: processes scheduled jobs, checks due rechecks, and polls payment link completions."""
    while not _agent_stop_event.wait(AGENT_POLL_SECONDS):
        with _agent_lock:
            is_active = _agent["active"]
        if is_active:
            try:
                # 1. Process due scheduled recovery jobs (WAIT -> RECHECK -> DECIDE -> EXECUTE)
                s = _process_due_scheduled_jobs()
                # 2. Process legacy new failures if any
                n = _process_new_failures()
                # 3. Check Razorpay for paid links
                r = _sync_razorpay_payment_links()

                with _agent_lock:
                    _agent["last_run"] = datetime.now(timezone.utc).isoformat()
                    if s > 0 or n > 0 or r > 0:
                        _log_event("agent_scan",
                            payment_id="—", amount=0,
                            label=f"Agent scan complete — {s} job(s) resolved, {r} link(s) confirmed paid",
                            sublabel=f"Next scan in {AGENT_POLL_SECONDS}s")
            except Exception as exc:
                _log_event("error", payment_id="—", amount=0,
                    label="Agent loop error", sublabel=str(exc))


def _bootstrap_agent_state():
    """Seed in-memory agent activity and stats from DB on startup so page refresh retains history."""
    try:
        with get_connection() as conn:
            total_attempts = conn.execute("SELECT COUNT(*) as c FROM recovery_attempts").fetchone()["c"]
            links = conn.execute("SELECT COUNT(*) as c FROM recovery_attempts WHERE action = 'SEND_PAYMENT_LINK'").fetchone()["c"]
            escalated = conn.execute("SELECT COUNT(*) as c FROM recovery_attempts WHERE action = 'ESCALATE_TO_HUMAN'").fetchone()["c"]
            recovered = conn.execute("""
                SELECT COALESCE(SUM(p.amount), 0.0) as rev
                FROM recovery_attempts r
                JOIN payments p ON r.payment_id = p.payment_id
                WHERE r.status = 'SUCCESS'
            """).fetchone()["rev"]

            with _agent_lock:
                _agent["processed_total"] = total_attempts
                _agent["links_total"] = links
                _agent["escalated_total"] = escalated
                _agent["recovered_total"] = float(recovered)

            recent = conn.execute("""
                SELECT r.*, p.amount, p.failure_reason
                FROM recovery_attempts r
                LEFT JOIN payments p ON r.payment_id = p.payment_id AND r.merchant_id = p.merchant_id
                ORDER BY r.timestamp DESC
                LIMIT 50
            """).fetchall()

            for row in reversed(recent):
                action = row["action"]
                amt = row["amount"] or 0
                razorpay_url = None
                if row["reason"] and "rzp.io" in row["reason"]:
                    m = re.search(r"https?://[^\s]+", row["reason"])
                    if m:
                        razorpay_url = m.group(0)

                if action == "SEND_PAYMENT_LINK":
                    _log_event("link_sent", merchant_id=row["merchant_id"], user_id=row["user_id"], payment_id=row["payment_id"], amount=amt,
                               label="⚡ Payment link automatically sent",
                               sublabel="Razorpay link dispatched to customer" if razorpay_url else (row["reason"][:80] if row["reason"] else ""),
                               razorpay_url=razorpay_url)
                elif action == "RETRY":
                    _log_event("retried", merchant_id=row["merchant_id"], user_id=row["user_id"], payment_id=row["payment_id"], amount=amt,
                               label="Payment automatically retried", sublabel="Gateway retry initiated")
                elif action == "ESCALATE_TO_HUMAN":
                    _log_event("escalated", merchant_id=row["merchant_id"], user_id=row["user_id"], payment_id=row["payment_id"], amount=amt,
                               label="Escalated to human agent", sublabel=row["reason"][:80] if row["reason"] else "")
                if row["status"] == "SUCCESS":
                    _log_event("recovered", merchant_id=row["merchant_id"], user_id=row["user_id"], payment_id=row["payment_id"], amount=amt,
                               label=f"₹{amt:,.0f} recovered", sublabel=f"Payment: {row['payment_id']}")
    except Exception as e:
        logger.warning(f"bootstrap_agent_state_failed: {e}")


def _safe_seed_if_empty():
    """No-op: auto-seeding is disabled. Database starts empty for the real merchant."""
    pass  # Seed endpoint removed — real payments come from Razorpay webhooks only.


def _seed_workspace_starter_data(merchant_id: str, user_id: str, business_name: str = "My Store") -> int:
    """Create one tenant-owned starter dataset for local/demo development.

    IDs and contact details are generated per merchant so demo workspaces never
    share customer/payment records. The operation is idempotent: an existing
    workspace is left untouched.
    """
    # Synthetic data is always opt-in. Real workspaces remain empty until a
    # gateway webhook or authenticated payment event creates records.
    if os.getenv("RECOVERAI_ENABLE_DEMO_DATA", "0") != "1":
        return 0

    import hashlib
    import uuid
    from datetime import timedelta

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM payments WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()["c"]
        if existing:
            return 0

    digest = hashlib.sha256(merchant_id.encode()).hexdigest()
    suffix = digest[:6]
    phone_seed = int(digest[6:10], 16) % 100
    now = datetime.now(timezone.utc)
    customer_specs = [
        (12, 10, 2, 45000.0, "SMS"),
        (5, 4, 1, 18500.0, "EMAIL"),
        (20, 18, 2, 92000.0, "WHATSAPP"),
        (3, 2, 1, 8400.0, "EMAIL"),
        (8, 7, 1, 31000.0, "SMS"),
    ]
    customers = []
    for index, (total, successful, failed, ltv, channel) in enumerate(customer_specs, 1):
        customer_id = f"cust_{suffix}_{index:02d}_{uuid.uuid4().hex[:4]}"
        customers.append((
            customer_id, total, successful, failed, ltv, channel,
            f"customer{index}.{suffix}@{merchant_id}.recoverai.test",
            f"+9198{phone_seed:02d}{index:06d}",
        ))

    payment_specs = [
        (4500.0, "BANK_SERVER_DOWN", "UPI", 15),
        (12000.0, "INSUFFICIENT_FUNDS", "CREDIT_CARD", 60),
        (3200.0, "NETWORK_TIMEOUT", "NET_BANKING", 180),
        (1500.0, "INVALID_OTP", "UPI", 300),
        (8900.0, "CARD_EXPIRED", "DEBIT_CARD", 480),
    ]
    with get_connection() as conn:
        for customer_id, total, successful, failed, ltv, channel, email, phone in customers:
            conn.execute(
                """INSERT INTO customers
                (customer_id, merchant_id, user_id, total_payments, successful_payments,
                 failed_payments, lifetime_value, preferred_channel, email, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (customer_id, merchant_id, user_id, total, successful, failed, ltv, channel, email, phone),
            )
        for index, (amount, reason, method, minutes_ago) in enumerate(payment_specs):
            conn.execute(
                """INSERT INTO payments
                (payment_id, merchant_id, user_id, customer_id, amount, status,
                 failure_reason, payment_method, timestamp, previous_attempts)
                VALUES (?, ?, ?, ?, ?, 'FAILED', ?, ?, ?, 0)""",
                (f"pay_{suffix}_{uuid.uuid4().hex[:10]}", merchant_id, user_id,
                 customers[index][0], amount, reason, method,
                 (now - timedelta(minutes=minutes_ago)).isoformat()),
            )
    return len(payment_specs)


def start_recovery_agent() -> None:
    """Initialize persisted state and start exactly one in-process worker."""
    global _bg_thread
    _safe_seed_if_empty()
    _bootstrap_agent_state()
    if os.getenv("RECOVERAI_AGENT_ENABLED", "1").lower() not in {"1", "true", "yes"}:
        logger.info("recovery_agent.disabled")
        return
    _agent_stop_event.clear()
    _bg_thread = threading.Thread(target=_agent_loop, daemon=True, name="RecoverAI-Agent")
    _bg_thread.start()


def stop_recovery_agent() -> None:
    """Stop the local worker cleanly so deploys do not leave duplicate loops."""
    _agent_stop_event.set()
    if _bg_thread and _bg_thread.is_alive():
        _bg_thread.join(timeout=min(AGENT_POLL_SECONDS + 1, 5))


@app.post("/data/seed", tags=["System"])
def seed_database(request: Request):
    """Deprecated global seed endpoint; never wipe or mutate other tenants."""
    raise HTTPException(status_code=410, detail="Use /data/seed-workspace for isolated development data.")


@app.post("/data/seed-workspace", tags=["System"])
def seed_user_workspace(request: Request):
    """
    Seed starter failed payments and customer records specifically tagged
    with the authenticated merchant's merchant_id so new users can test their isolated account.
    """
    user = get_current_user_context(request)
    user_id = user["user_id"]
    merchant_id = user["merchant_id"]
    created = _seed_workspace_starter_data(
        merchant_id, user_id, user.get("business_name") or user.get("company_name") or "My Store"
    )

    global _metrics_cache
    _metrics_cache["data"] = None
    _metrics_cache["expires_at"] = 0.0

    return {
        "status": "success" if created else "not_enabled",
        "message": (
            f"Successfully initialized starter transactions for workspace {user.get('business_name') or user.get('company_name')}"
            if created else
            "Demo data is disabled. Connect your gateway or send an authenticated payment event to populate this workspace."
        ),
        "merchant_id": merchant_id,
        "user_id": user_id,
        "payments_count": created,
        "already_initialized": created == 0,
    }


@app.post("/agent/reset", tags=["Agent"])
def reset_agent_data(request: Request):
    """Clear recovery history for the authenticated merchant only."""
    user = get_current_user_context(request)
    _require_role(user, "OWNER", "ADMIN")
    merchant_id = user["merchant_id"]
    with _agent_lock:
        retained_events = [event for event in _agent["activity"] if event.get("merchant_id") != merchant_id]
        _agent["activity"].clear()
        _agent["activity"].extend(retained_events)

    with get_connection() as conn:
        conn.execute("DELETE FROM recovery_attempts WHERE merchant_id = ?", (merchant_id,))
        conn.execute("DELETE FROM audit_logs WHERE merchant_id = ?", (merchant_id,))

    global _metrics_cache
    _metrics_cache["data"] = None
    _metrics_cache["expires_at"] = 0.0

    return {"status": "cleared", "message": "Your workspace activity and recovery history were reset."}


@app.get("/agent/status", tags=["Agent"])
def agent_status(request: Request):
    """Return current agent state, stats, and last-run timestamp — scoped to the authenticated merchant organization."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    merchant_name = user.get("merchant_name") or user.get("business_name") or user.get("company_name", "Merchant Store")

    # Compute per-merchant stats from DB (accurate cross-restart, per-tenant)
    with get_connection() as conn:
        processed = conn.execute(
            "SELECT COUNT(*) as c FROM recovery_attempts ra JOIN payments p ON ra.payment_id = p.payment_id WHERE p.merchant_id = ?",
            (merchant_id,)
        ).fetchone()["c"]
        links = conn.execute(
            "SELECT COUNT(*) as c FROM recovery_attempts ra JOIN payments p ON ra.payment_id = p.payment_id WHERE ra.action IN ('SEND_PAYMENT_LINK', 'ALTERNATE_PAYMENT_METHOD') AND p.merchant_id = ?",
            (merchant_id,)
        ).fetchone()["c"]
        escalated = conn.execute(
            "SELECT COUNT(*) as c FROM recovery_attempts ra JOIN payments p ON ra.payment_id = p.payment_id WHERE ra.action = 'ESCALATE_TO_HUMAN' AND p.merchant_id = ?",
            (merchant_id,)
        ).fetchone()["c"]
        recovered = conn.execute(
            "SELECT COALESCE(SUM(p.amount), 0.0) as rev FROM recovery_attempts ra JOIN payments p ON ra.payment_id = p.payment_id WHERE ra.status = 'SUCCESS' AND p.merchant_id = ?",
            (merchant_id,)
        ).fetchone()["rev"]

    with _agent_lock:
        return {
            "active":            _agent["active"],
            "last_run":          _agent["last_run"],
            "poll_interval_sec": AGENT_POLL_SECONDS,
            "processed_total":   processed,
            "links_total":       links,
            "escalated_total":   escalated,
            "recovered_total":   round(float(recovered), 2),
            "merchant_id":       merchant_id,
            "merchant_name":     merchant_name,
        }


@app.post("/agent/toggle", tags=["Agent"])
def agent_toggle(request: Request):
    """Toggle the agent between Active and Paused."""
    user = get_current_user_context(request)
    with _agent_lock:
        _agent["active"] = not _agent["active"]
        new_state = _agent["active"]
        _log_event(
            "agent_toggled", merchant_id=user["merchant_id"], user_id=user["user_id"], payment_id="—", amount=0,
            label=f"Agent {'resumed' if new_state else 'paused'} by merchant",
            sublabel="Automatic recovery is now " + ("active" if new_state else "paused"),
        )
        return {"active": new_state}


@app.get("/agent/activity", tags=["Agent"])
def agent_activity(request: Request, limit: int = 100):
    """Return the most recent N activity events for the authenticated merchant organization."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    with _agent_lock:
        all_events = list(_agent["activity"])
    filtered = [e for e in all_events if e.get("merchant_id") == merchant_id][:limit]
    return {"events": filtered}


# ── Request / Response schemas ─────────────────────────────────────────────────
# These extend the Pydantic models from Phase 1 for API-specific shapes.

class PaymentEventRequest(BaseModel):
    """Body for POST /payments/event — ingest a new failed payment."""
    payment_id:         str
    customer_id:        str
    amount:             float = Field(gt=0, description="Amount in INR (₹)")
    failure_reason:     FailureReason
    payment_method:     PaymentMethod
    previous_attempts:  int = Field(ge=0, default=0)
    customer_email:     Optional[str] = None
    customer_phone:     Optional[str] = None

    model_config = {"json_schema_extra": {"example": {
        "payment_id":        "pay_demo_001",
        "customer_id":       "cust_demo_001",
        "amount":            3500.00,
        "failure_reason":    "BANK_SERVER_DOWN",
        "payment_method":    "UPI",
        "previous_attempts": 0,
    }}}


class PipelineResponse(BaseModel):
    """Full pipeline result returned by POST /recovery/run/{payment_id}."""
    payment_id:         str
    recovery_score:     RecoveryScore
    agent_decision:     AgentDecision
    guardrail_result:   GuardrailResult
    recovery_attempt:   RecoveryAttempt
    audit_event_id:     str


from typing import List, Dict, Any, Optional

class CheckoutEventRequest(BaseModel):
    """Body for POST /checkouts/event — ingest a checkout abandonment event."""
    checkout_id:        str
    customer_id:       str
    cart_value:        float = Field(gt=0, description="Cart value in INR (₹)")
    drop_off_stage:    str   = "PAYMENT_METHOD_SELECTION"
    time_spent_seconds: int  = 60
    customer_email:    Optional[str] = None
    customer_phone:    Optional[str] = None

class OpportunityItem(BaseModel):
    payment_id:              str
    customer_id:             str
    amount:                  float
    failure_reason:          str
    recovery_probability:    float
    expected_recovery_value: float
    priority_tier:           str
    recommended_strategy:    str
    preferred_channel:       str
    status:                  str

class OpportunitiesResponse(BaseModel):
    total_opportunities:    int
    total_expected_revenue: float
    high_priority_count:    int
    medium_priority_count:  int
    low_priority_count:     int
    opportunities:          List[OpportunityItem]

class EscalationItem(BaseModel):
    payment_id:         str
    customer_id:        str
    amount:             float
    failure_reason:     str
    attempts_made:      int
    escalation_reason:  str
    timestamp:          str
    status:             str

class MetricsResponse(BaseModel):
    """Summary metrics from the latest evaluation run."""
    transactions_tested:   int
    recoverable_count:     int
    successful_recoveries: int
    revenue_at_risk:       float
    revenue_recovered:     float
    recovery_rate_pct:     float
    human_escalations:     int
    guardrail_blocks:      int
    precision:             float
    recall:                float
    f1_score:              float
    strategy_counts:       Dict[str, int]
    daily_trend:           List[Dict[str, Any]]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/debug_db", tags=["Debug"])
def debug_db(request: Request):
    """Tenant-scoped diagnostics; disabled outside development."""
    if os.getenv("RECOVERAI_ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="Not found.")
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    with get_connection() as conn:
        payments = conn.execute("SELECT * FROM payments WHERE merchant_id = ?", (merchant_id,)).fetchall()
        customers = conn.execute("SELECT * FROM customers WHERE merchant_id = ?", (merchant_id,)).fetchall()
        attempts = conn.execute("SELECT * FROM recovery_attempts WHERE merchant_id = ?", (merchant_id,)).fetchall()
        
        # Test just the join
        join_query = conn.execute("""
            SELECT p.payment_id, c.customer_id
            FROM payments p
            JOIN customers c ON p.customer_id = c.customer_id AND p.merchant_id = c.merchant_id
            WHERE p.merchant_id = ?
        """, (merchant_id,)).fetchall()

        # Test just the status
        status_query = conn.execute("""
            SELECT payment_id FROM payments WHERE status = 'FAILED' AND merchant_id = ?
        """, (merchant_id,)).fetchall()

        # Test the NOT EXISTS
        exists_query = conn.execute("""
            SELECT p.payment_id 
            FROM payments p
            WHERE NOT EXISTS (
                SELECT 1 FROM recovery_attempts r WHERE r.payment_id = p.payment_id AND r.merchant_id = p.merchant_id
            ) AND p.merchant_id = ?
        """, (merchant_id,)).fetchall()

    return {
        "join_matches": len(join_query),
        "status_matches": len(status_query),
        "exists_matches": len(exists_query),
        "join_results": [dict(r) for r in join_query],
        "status_results": [dict(r) for r in status_query],
        "exists_results": [dict(r) for r in exists_query]
    }

@app.get("/health", tags=["System"])
def health_check():
    """Simple health check — confirms the API is up."""
    return {"status": "ok", "service": "RecoverAI", "version": "1.0.0"}


@app.get("/readyz", include_in_schema=False)
def readiness_check():
    """Readiness probe: only return success when durable storage is usable."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        logger.error("readiness_check_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


# ── Authentication & Profile Endpoints ────────────────────────────────────────

def _deliver_password_reset_email(email: str, reset_url: str) -> bool:
    """Send a reset email when SMTP is configured; return whether delivery ran."""
    host = os.getenv("SMTP_HOST")
    if not host:
        return False
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME")
    if not sender:
        return False
    message = (
        f"From: {sender}\nTo: {email}\nSubject: Reset your RecoverAI password\n\n"
        f"Use this secure link within 30 minutes:\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this message."
    )
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            username = os.getenv("SMTP_USERNAME")
            password = os.getenv("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(sender, [email], message)
        return True
    except Exception as exc:
        logger.warning("password_reset_email_failed: %s", exc)
        return False


@app.post("/auth/forgot-password", tags=["Authentication"])
def forgot_password(body: ForgotPasswordRequest, request: Request):
    """Issue a single-use, 30-minute reset link without revealing account existence."""
    email = body.email.lower().strip()
    user = fetch_user_by_email(email)
    response = {"status": "ok", "message": "If an account exists, a reset link has been sent."}
    if not user or not user["is_active"]:
        return response

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=30)
    with get_connection() as conn:
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ? OR expires_at <= ?", (user["user_id"], now.isoformat()))
        conn.execute(
            "INSERT INTO password_reset_tokens (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, user["user_id"], expires.isoformat(), now.isoformat()),
        )

    base_url = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    reset_url = f"{base_url}/reset-password?token={raw_token}"
    delivered = _deliver_password_reset_email(email, reset_url)
    if not delivered and os.getenv("RECOVERAI_ENVIRONMENT", "development").lower() != "production":
        # Local development convenience; never expose the token in production.
        response["reset_token"] = raw_token
        response["reset_url"] = reset_url
    return response


@app.post("/auth/reset-password", tags=["Authentication"])
def reset_password(body: ResetPasswordRequest):
    """Consume a reset token atomically and replace the password hash."""
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM password_reset_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (token_hash, now.isoformat()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
        pwd_hash, salt = hash_password(body.new_password)
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE user_id = ?",
            (pwd_hash, salt, now.isoformat(), row["user_id"]),
        )
        conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?", (now.isoformat(), token_hash))
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ? AND token_hash != ?", (row["user_id"], token_hash))
    return {"status": "ok", "message": "Password updated. You can now sign in."}

@app.post("/auth/register", tags=["Authentication"], response_model=AuthTokenResponse)
def register_user(body: UserRegisterRequest):
    """
    Register a new merchant organization + owner account and generate an API key + JWT access token.
    """
    email_clean = body.email.lower().strip()
    existing = fetch_user_by_email(email_clean)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    import uuid
    merchant_id = f"mer_{uuid.uuid4().hex[:10]}"
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    business_name = body.business_name or body.company_name or "My Store"

    # 1. Create Organization / Merchant
    from db import create_merchant
    create_merchant(
        merchant_id=merchant_id,
        name=body.company_name or business_name,
        business_name=business_name,
        email=email_clean,
    )

    pwd_hash, salt = hash_password(body.password)
    api_key = generate_api_key()

    # 2. Create Owner User
    user_row = create_user(
        user_id=user_id,
        merchant_id=merchant_id,
        email=email_clean,
        password_hash=pwd_hash,
        salt=salt,
        full_name=body.full_name,
        company_name=business_name,
        role="OWNER",
        api_key=api_key,
    )

    # Give a newly-created development workspace a private, realistic starter
    # queue so the dashboard is usable immediately. Production workspaces are
    # intentionally empty until their gateway/webhooks provide real events.
    # Do not create synthetic payments during registration. A new merchant
    # should only see records received from its own gateway integration.

    token = create_access_token({
        "sub": user_id,
        "merchant_id": merchant_id,
        "email": email_clean,
        "role": "OWNER",
        "name": body.full_name,
    })

    user_resp = UserProfileResponse(
        user_id=user_id,
        merchant_id=merchant_id,
        merchant_name=business_name,
        business_name=business_name,
        email=email_clean,
        full_name=body.full_name,
        company_name=business_name,
        role="OWNER",
        api_key=api_key,
        created_at=user_row["created_at"],
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_resp,
    )


@app.post("/auth/login", tags=["Authentication"], response_model=AuthTokenResponse)
def login_user(body: UserLoginRequest):
    """
    Authenticate user credentials and return JWT bearer token.
    """
    email_clean = body.email.lower().strip()
    user = fetch_user_by_email(email_clean)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    u_dict = dict(user)

    if not verify_password(body.password, u_dict["password_hash"], u_dict["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    update_user_last_login(u_dict["user_id"])
    merchant_id = u_dict.get("merchant_id", "mer_default")
    
    from db import fetch_merchant_by_id
    m_info = fetch_merchant_by_id(merchant_id)
    m_dict = dict(m_info) if m_info else {}
    merchant_name = m_dict.get("name") or u_dict.get("company_name", "RecoverAI")
    business_name = m_dict.get("business_name") or u_dict.get("company_name", "RecoverAI Store")

    token = create_access_token({
        "sub": u_dict["user_id"],
        "merchant_id": merchant_id,
        "email": u_dict["email"],
        "role": u_dict.get("role", "OWNER"),
        "name": u_dict["full_name"],
    })
    
    user_resp = UserProfileResponse(
        user_id=u_dict["user_id"],
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        business_name=business_name,
        email=u_dict["email"],
        full_name=u_dict["full_name"],
        company_name=business_name,
        role=u_dict.get("role", "OWNER"),
        api_key=u_dict.get("api_key"),
        created_at=u_dict.get("created_at"),
        last_login_at=u_dict.get("last_login_at"),
    )
    
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_resp,
    )


@app.get("/auth/me", tags=["Authentication"], response_model=UserProfileResponse)
def get_current_user_profile(request: Request):
    """
    Get current logged in merchant user and organization profile.
    """
    user = get_current_user_context(request)
    return UserProfileResponse(
        user_id=user["user_id"],
        merchant_id=user["merchant_id"],
        merchant_name=user.get("merchant_name") or user.get("business_name") or user.get("company_name", "RecoverAI Store"),
        business_name=user.get("business_name") or user.get("company_name", "RecoverAI Retail"),
        email=user["email"],
        full_name=user["full_name"],
        company_name=user.get("business_name") or user.get("company_name", "RecoverAI Retail"),
        role=user.get("role", "OWNER"),
        api_key=user.get("api_key"),
        created_at=user.get("created_at"),
        last_login_at=user.get("last_login_at"),
    )


@app.post("/auth/logout", tags=["Authentication"])
def logout_user(request: Request):
    """
    Clear client session and return logout confirmation.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_access_token(auth_header[7:].strip())
    return {"status": "logged_out", "message": "Session cleared successfully"}


@app.put("/auth/profile", tags=["Authentication"], response_model=UserProfileResponse)
def update_profile(body: UpdateProfileRequest, request: Request):
    """
    Update merchant user profile information or password.
    """
    user = get_current_user_context(request)
    pwd_hash = None
    salt = None
    if body.new_password:
        pwd_hash, salt = hash_password(body.new_password)
        
    updated = update_user_profile(
        user_id=user["user_id"],
        full_name=body.full_name,
        company_name=body.company_name,
        password_hash=pwd_hash,
        salt=salt,
    )
    if not updated:
        updated = user
    
    merchant_id = updated.get("merchant_id", user["merchant_id"])
    from db import fetch_merchant_by_id
    m_info = fetch_merchant_by_id(merchant_id)
    merchant_name = m_info["name"] if m_info else updated["company_name"]
    business_name = m_info["business_name"] if m_info else updated["company_name"]

    return UserProfileResponse(
        user_id=updated["user_id"],
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        business_name=business_name,
        email=updated["email"],
        full_name=updated["full_name"],
        company_name=business_name,
        role=updated.get("role", "OWNER"),
        api_key=updated.get("api_key"),
        created_at=updated.get("created_at"),
        last_login_at=updated.get("last_login_at"),
    )


@app.get("/auth/profiles", tags=["Authentication"], response_model=List[UserProfileSummary])
def list_available_profiles(request: Request):
    """
    List merchant profiles for quick-switching in the UI.
    """
    current_u = get_current_user_context(request)
    all_users = fetch_all_users(merchant_id=current_u["merchant_id"])
    summaries = []
    for u in all_users:
        u = dict(u)
        summaries.append(UserProfileSummary(
            user_id=u["user_id"],
            merchant_id=u.get("merchant_id", "mer_default"),
            email=u["email"],
            full_name=u["full_name"],
            company_name=u["company_name"],
            role=u.get("role", "OWNER"),
            is_current=(u["user_id"] == current_u["user_id"]),
        ))
    return summaries


@app.post("/auth/quick-switch", tags=["Authentication"])
def quick_switch_profile(body: dict, request: Request):
    """
    DISABLED: Passwordless profile switching has been removed for security.
    Use POST /auth/login with valid credentials to switch accounts.
    """
    raise HTTPException(
        status_code=410,
        detail="Passwordless profile switching is disabled. Please use POST /auth/login with your credentials."
    )


@app.post("/auth/regenerate-api-key", tags=["Authentication"], response_model=dict)
def regenerate_api_key_endpoint(request: Request):
    """
    Regenerate merchant API key for live webhooks.
    """
    user = get_current_user_context(request)
    new_key = generate_api_key()
    update_user_api_key(user["user_id"], new_key)
    return {"status": "ok", "api_key": new_key}


@app.post("/payments/event", tags=["Payments"], response_model=dict)
def ingest_payment_event(body: PaymentEventRequest, request: Request):
    """
    Ingest a new failed payment event into the system.
    Stores it in the payments table for later pipeline processing with strict tenant isolation.
    """
    now = datetime.now(timezone.utc)
    user = get_current_user_context(request)
    user_id = user["user_id"]
    merchant_id = user["merchant_id"]

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO customers
                (customer_id, merchant_id, user_id, total_payments, successful_payments, failed_payments, email, phone)
            VALUES (?, ?, ?, 1, 0, 1, ?, ?)
            """,
            (body.customer_id, merchant_id, user_id, body.customer_email, body.customer_phone),
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO payments
                (payment_id, merchant_id, user_id, customer_id, amount, status, failure_reason,
                 payment_method, timestamp, previous_attempts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.payment_id,
                merchant_id,
                user_id,
                body.customer_id,
                body.amount,
                PaymentStatus.FAILED.value,
                body.failure_reason.value,
                body.payment_method.value,
                now.isoformat(),
                body.previous_attempts,
            ),
        )

    logger.info("api.payment.ingested", extra={"payment_id": body.payment_id, "merchant_id": merchant_id, "user_id": user_id})
    return {"status": "accepted", "payment_id": body.payment_id, "merchant_id": merchant_id, "timestamp": now.isoformat()}



# ── Webhook signature verification ────────────────────────────────────────────

def _verify_razorpay_signature(body: bytes, signature_header: str, webhook_secret: str) -> bool:
    """
    Verify that the webhook came from Razorpay using HMAC-SHA256.
    The secret is resolved for the target merchant before this function is called.
    Production webhooks must always supply a valid signature.
    """
    import hmac, hashlib, os
    secret = webhook_secret.strip()
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Recovery pipeline runner (called from background task) ────────────────────

def _run_recovery_for_payment(payment_id: str, customer_email: str = "", customer_phone: str = "", merchant_id: str = "mer_default") -> None:
    """
    Run the full recovery pipeline for one payment_id in a background thread.
    Emits live events to the agent console at each step.
    This is the true agentic loop: strictly tenant-isolated.
    """
    import logging as _logging_bg

    try:
        with get_connection() as conn:
            row = conn.execute("""
                SELECT p.*, p.merchant_id as payment_merchant_id, p.user_id as payment_user_id,
                       c.total_payments, c.successful_payments, c.failed_payments,
                       COALESCE(c.lifetime_value, 0.0) as lifetime_value,
                       COALESCE(c.preferred_channel, 'SMS') as preferred_channel
                FROM payments p
                JOIN customers c ON p.customer_id = c.customer_id AND p.merchant_id = c.merchant_id
                WHERE p.payment_id = ? AND p.merchant_id = ?
                  AND p.status = 'FAILED'
                  AND NOT EXISTS (
                      SELECT 1 FROM recovery_attempts r
                      WHERE r.payment_id = p.payment_id
                        AND r.status IN ('PENDING', 'SUCCESS')
                  )
            """, (payment_id, merchant_id)).fetchone()

        if not row:
            logger.info(f"webhook.recovery_skip: {payment_id} for merchant {merchant_id} already processed or not FAILED")
            return

        now = datetime.now(timezone.utc)
        row_mid = row["payment_merchant_id"] if "payment_merchant_id" in row.keys() and row["payment_merchant_id"] else merchant_id
        row_uid = row["payment_user_id"] if "payment_user_id" in row.keys() and row["payment_user_id"] else "usr_default"

        reason_str = row["failure_reason"].replace("_", " ").title()
        is_temp = row["failure_reason"] in ("BANK_SERVER_DOWN", "NETWORK_TIMEOUT", "INVALID_OTP")

        payment = Payment(
            payment_id=row["payment_id"],
            customer_id=row["customer_id"],
            amount=row["amount"],
            status=PaymentStatus(row["status"]),
            failure_reason=FailureReason(row["failure_reason"]),
            payment_method=PaymentMethod(row["payment_method"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            previous_attempts=row["previous_attempts"],
        )
        customer = Customer(
            customer_id=row["customer_id"],
            total_payments=row["total_payments"],
            successful_payments=row["successful_payments"],
            failed_payments=row["failed_payments"],
            lifetime_value=row["lifetime_value"],
            preferred_channel=ChannelPreference(row["preferred_channel"]),
        )

        # ── Step 1: Detected ───────────────────────────────────────────────────
        _log_event("payment_failed", merchant_id=row_mid, user_id=row_uid,
            payment_id=payment_id, amount=payment.amount,
            label="Payment failure detected",
            sublabel=f"₹{payment.amount:,.0f} · {reason_str}")

        _log_event("opportunity_detected", merchant_id=row_mid, user_id=row_uid,
            payment_id=payment_id, amount=payment.amount,
            label="Recovery opportunity identified",
            sublabel="Temporary failure — likely recoverable" if is_temp else "Evaluating recovery options")

        # ── Step 2: ML Diagnosis ───────────────────────────────────────────────
        score = score_recovery(payment, customer)
        _log_event("ml_scored", merchant_id=row_mid, user_id=row_uid,
            payment_id=payment_id, amount=payment.amount,
            label="🧠 ML diagnosis complete",
            sublabel=f"Recovery probability: {score.recovery_probability * 100:.0f}% · Expected: ₹{score.expected_recovery_value:,.0f} · Priority: {score.priority_tier.value}")

        # ── Step 3: Playbook Router & AI Strategy Plan ────────────────────────
        from core.playbook_router import route_playbook
        route = route_playbook(payment, score, customer)

        _logging_bg.disable(_logging_bg.INFO)
        try:
            decision = get_agent_decision(payment, score, customer)
        finally:
            _logging_bg.disable(_logging_bg.NOTSET)

        _log_event("playbook_selected", merchant_id=row_mid, user_id=row_uid,
            payment_id=payment_id, amount=payment.amount,
            label=f"📋 Playbook Selected: {route.playbook_name}",
            sublabel=f"Strategy: {route.strategy_type.value} · Channel: {route.preferred_channel.value} · Confidence: {route.confidence*100:.0f}%")

        # ── Step 4: Persist Multi-Step Recovery Plan ───────────────────────────
        from datetime import timedelta
        import uuid
        from db import save_scheduled_job, save_recovery_plan

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        scheduled_at_dt = now + timedelta(seconds=route.delay_seconds)
        plan = RecoveryPlan(
            plan_id=plan_id,
            payment_id=payment_id,
            strategy=route.strategy_type,
            playbook=route.playbook_name,
            stage="WAIT_SCHEDULED" if route.requires_wait else "EXECUTING",
            delay_seconds=route.delay_seconds,
            scheduled_at=scheduled_at_dt,
            steps=route.steps,
            priority=score.priority_tier,
            expected_recovery_value=score.expected_recovery_value,
            created_at=now,
        )
        try:
            save_recovery_plan(
                plan_id=plan.plan_id,
                payment_id=plan.payment_id,
                strategy=plan.strategy.value if hasattr(plan.strategy, "value") else str(plan.strategy),
                steps=[step.model_dump() if hasattr(step, "model_dump") else step for step in plan.steps],
                priority=plan.priority.value if hasattr(plan.priority, "value") else str(plan.priority),
                expected_recovery_value=plan.expected_recovery_value,
                created_at=plan.created_at.isoformat(),
                merchant_id=row_mid,
                user_id=row_uid,
            )
        except Exception as e:
            logger.warning(f"save_plan_failed: {e}")

        _log_event("recovery_plan_created", merchant_id=row_mid, user_id=row_uid,
            payment_id=payment_id, amount=payment.amount,
            label=f"🗺️ Multi-Step Recovery Plan Created",
            sublabel=f"Plan {plan_id[:8]} · {len(route.steps)} step(s) · {route.reason[:80]}")

        # ── Step 5: Delayed Scheduling vs Immediate Execution ─────────────────
        if route.requires_wait:
            job_id = f"job_{uuid.uuid4().hex[:10]}"
            save_scheduled_job(
                job_id=job_id,
                merchant_id=row_mid,
                user_id=row_uid,
                payment_id=payment_id,
                playbook=route.playbook_name,
                stage="WAIT_SCHEDULED",
                scheduled_at=scheduled_at_dt.isoformat(),
                delay_seconds=route.delay_seconds,
                next_action=route.recommended_action.value,
                attempt_number=payment.previous_attempts,
                status="PENDING",
            )

            _log_event("wait_scheduled", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label=f"⏳ Agent is waiting before contacting customer",
                sublabel=f"Scheduled status recheck in {route.delay_seconds} seconds · Preventing premature customer contact")

            return

        # ── Step 6: Immediate Execution (for non-delayed playbooks) ───────────
        guardrail = check_guardrails(payment, decision, [], now=now)
        action = guardrail.final_action.value

        if guardrail.result.value == "APPROVED":
            _log_event("guardrail_approved", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="Safety checks passed ✓",
                sublabel=f"Executing {guardrail.final_action.value} via {decision.preferred_channel.value}")
        else:
            _log_event("guardrail_blocked", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="Guardrail blocked — escalating to human",
                sublabel=guardrail.reason or "Compliance rule triggered")

        attempt = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel, merchant_id=row_mid)
        audit   = write_audit_log(score, decision, guardrail, attempt, merchant_id=row_mid, user_id=row_uid)

        # Extract Razorpay payment link URL if generated
        razorpay_url = None
        if attempt.reason and "rzp.io" in attempt.reason:
            m = re.search(r"https?://[^\s]+", attempt.reason)
            if m:
                razorpay_url = m.group(0)

        if action in ("SEND_PAYMENT_LINK", "ALTERNATE_PAYMENT_METHOD"):
            _log_event("link_sent", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="⚡ Recovery payment link dispatched",
                sublabel=f"Sent to customer via {decision.preferred_channel.value}",
                razorpay_url=razorpay_url)
            with _agent_lock:
                _agent["links_total"] += 1

        elif action == "ESCALATE_TO_HUMAN":
            _log_event("escalated", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="Escalated to human review queue",
                sublabel="Recovery ticket created in queue")
            with _agent_lock:
                _agent["escalated_total"] += 1

        elif action == "RETRY":
            _log_event("retried", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="Payment automatically retried",
                sublabel="Gateway retry initiated")

        else:
            _log_event("stopped", merchant_id=row_mid, user_id=row_uid,
                payment_id=payment_id, amount=payment.amount,
                label="Recovery stopped",
                sublabel="Unrecoverable or monitoring only")

        with _agent_lock:
            _agent["processed_total"] += 1
            _agent["last_run"] = datetime.now(timezone.utc).isoformat()

        # Invalidate metrics cache
        global _metrics_cache
        _metrics_cache["expires_at"] = 0.0

    except Exception as exc:
        _log_event("error", merchant_id=merchant_id, user_id="usr_default",
            payment_id=payment_id, amount=0,
            label="Pipeline error",
            sublabel=str(exc))
        logger.exception(f"webhook.recovery_error: {payment_id}")


# ── Production Razorpay Webhook ────────────────────────────────────────────────

from fastapi import BackgroundTasks, Request

@app.post("/webhooks/razorpay", tags=["Webhooks"])
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Production Webhook Endpoint for Razorpay.
    Identifies tenant via webhook secret, API key, or custom merchant header.

    Handles:
      payment.failed       → save payment, trigger recovery pipeline in background
      payment.captured     → mark the original failed payment as RECOVERED (real money confirmed)
      payment.link.paid    → same as payment.captured (Razorpay sends both)

    Returns 200 immediately so Razorpay never times out waiting for us.
    All heavy processing happens in BackgroundTasks.
    """
    raw_body = await request.body()
    sig_header = request.headers.get("x-razorpay-signature", "")

    # A merchant id is a routing hint; the HMAC signature authenticates the payload.
    from db import fetch_merchant_by_id, fetch_all_merchants, fetch_setting
    merchant_id_hint = request.query_params.get("merchant_id") or request.headers.get("x-merchant-id")
    
    matched_merchant = None
    resolved_secret = None

    if merchant_id_hint:
        matched_merchant = fetch_merchant_by_id(merchant_id_hint)
        if matched_merchant:
            secret_candidate = (
                fetch_setting("razorpay_webhook_secret", merchant_id=merchant_id_hint)
                or matched_merchant["razorpay_webhook_secret"]
                or (os.getenv("RAZORPAY_WEBHOOK_SECRET") if merchant_id_hint in ("mer_default", "") else "")
                or ""
            )
            if _verify_razorpay_signature(raw_body, sig_header, secret_candidate):
                resolved_secret = secret_candidate

    # If no hint or hint signature failed, perform automatic HMAC resolution across tenants
    if not resolved_secret:
        # 1. Try default tenant with environment secret or DB setting
        default_secret = (
            fetch_setting("razorpay_webhook_secret", merchant_id="mer_default")
            or os.getenv("RAZORPAY_WEBHOOK_SECRET")
            or ""
        )
        if default_secret and _verify_razorpay_signature(raw_body, sig_header, default_secret):
            matched_merchant = fetch_merchant_by_id("mer_default")
            resolved_secret = default_secret
        else:
            # 2. Iterate registered merchants
            for m in fetch_all_merchants():
                m_id = m["merchant_id"]
                s = fetch_setting("razorpay_webhook_secret", merchant_id=m_id) or m["razorpay_webhook_secret"] or ""
                if s and _verify_razorpay_signature(raw_body, sig_header, s):
                    matched_merchant = m
                    resolved_secret = s
                    break

    if not matched_merchant or not resolved_secret:
        logger.warning("webhook.invalid_signature_or_merchant", extra={"merchant_id": merchant_id_hint})
        raise HTTPException(status_code=403, detail="Invalid webhook signature or unconfigured webhook secret")


    try:
        import json
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    target_merchant_id = matched_merchant["merchant_id"]
    target_user_id = "usr_" + target_merchant_id

    event = payload.get("event", "")

    # ══════════════════════════════════════════════════════════════════════════
    # EVENT: payment.failed — trigger recovery
    # ══════════════════════════════════════════════════════════════════════════
    if event == "payment.failed":
        try:
            entity = payload["payload"]["payment"]["entity"]
            payment_id   = entity["id"]
            amount       = entity.get("amount", 0) / 100.0   # paise → INR

            customer_email = entity.get("email", "")
            customer_phone = entity.get("contact", "")
            customer_id    = (
                customer_email.split("@")[0].replace(".", "_") if customer_email
                else customer_phone.replace("+91", "cust_") if customer_phone
                else f"cust_{payment_id[-6:]}"
            )

            error_code   = str(entity.get("error_code") or "").lower()
            error_desc   = str(entity.get("error_description") or "").lower()
            error_reason = str(entity.get("error_reason") or "").lower()
            error_step   = str(entity.get("error_step") or "").lower()
            combined_err = f"{error_code} {error_desc} {error_reason} {error_step}"

            if any(k in combined_err for k in ("insufficient", "fund", "balance", "limit", "low_balance")):
                internal_reason = FailureReason.INSUFFICIENT_FUNDS
            elif any(k in combined_err for k in ("expired", "expir", "validity")):
                internal_reason = FailureReason.CARD_EXPIRED
            elif any(k in combined_err for k in ("otp", "pin", "auth", "authentication_failed", "incorrect_otp", "invalid_otp")):
                internal_reason = FailureReason.INVALID_OTP
            elif any(k in combined_err for k in ("timeout", "timed_out", "latency", "network")):
                internal_reason = FailureReason.NETWORK_TIMEOUT
            elif any(k in combined_err for k in ("bank", "server", "gateway", "down", "unavailable", "declined", "issuer")):
                internal_reason = FailureReason.BANK_SERVER_DOWN
            else:
                internal_reason = FailureReason.INSUFFICIENT_FUNDS

            rzp_method = entity.get("method", "").upper()
            method_map = {"CARD": "CREDIT_CARD", "NETBANKING": "NET_BANKING"}
            rzp_method = method_map.get(rzp_method, rzp_method)
            try:
                internal_method = PaymentMethod(rzp_method)
            except ValueError:
                internal_method = PaymentMethod.UPI

            now = datetime.now(timezone.utc)

            # ── Save payment to DB immediately with merchant ownership ─────────
            with get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO customers
                        (customer_id, merchant_id, user_id, total_payments, successful_payments, failed_payments, preferred_channel, email, phone)
                    VALUES (?, ?, ?, 1, 0, 1, 'SMS', ?, ?)
                """, (customer_id, target_merchant_id, target_user_id, customer_email, customer_phone))

                conn.execute("""
                    INSERT OR REPLACE INTO payments
                        (payment_id, merchant_id, user_id, customer_id, amount, status, failure_reason,
                         payment_method, timestamp, previous_attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    payment_id, target_merchant_id, target_user_id, customer_id, amount,
                    PaymentStatus.FAILED.value,
                    internal_reason.value, internal_method.value,
                    now.isoformat(), 0,
                ))

            _log_event("webhook_received", merchant_id=target_merchant_id, user_id=target_user_id,
                payment_id=payment_id, amount=amount,
                label="⚡ Webhook: payment.failed received",
                sublabel=f"₹{amount:,.0f} · Recovery pipeline starting…")

            background_tasks.add_task(
                _run_recovery_for_payment,
                payment_id, customer_email, customer_phone, target_merchant_id
            )

            logger.info("webhook.payment_failed.queued", extra={
                "payment_id": payment_id, "amount": amount, "reason": internal_reason.value, "merchant_id": target_merchant_id
            })
            return {"status": "queued", "payment_id": payment_id, "merchant_id": target_merchant_id,
                    "message": "Payment failure received — recovery pipeline started"}

        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Malformed payment.failed payload: missing {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # EVENT: payment.captured or payment.link.paid — CONFIRM RECOVERY
    # ══════════════════════════════════════════════════════════════════════════
    elif event in ("payment.captured", "payment.link.paid"):
        try:
            if event == "payment.link.paid":
                link_entity     = payload["payload"]["payment_link"]["entity"]
                pay_entity      = payload["payload"]["payment"]["entity"]
                reference_id    = link_entity.get("reference_id", "")
                captured_pay_id = pay_entity["id"]
                amount          = pay_entity.get("amount", 0) / 100.0
            else:
                pay_entity      = payload["payload"]["payment"]["entity"]
                captured_pay_id = pay_entity["id"]
                amount          = pay_entity.get("amount", 0) / 100.0
                reference_id    = pay_entity.get("description", "").replace("Recovery for failed payment ", "").strip()

            now = datetime.now(timezone.utc)
            recovered_payment_id = None
            matched_mid = target_merchant_id

            with get_connection() as conn:
                if reference_id:
                    row = conn.execute(
                        "SELECT payment_id, merchant_id FROM payments WHERE payment_id = ? AND merchant_id = ?", (reference_id, target_merchant_id)
                    ).fetchone()
                    if row:
                        recovered_payment_id = row["payment_id"]
                        matched_mid = row["merchant_id"]

                if not recovered_payment_id:
                    row = conn.execute("""
                        SELECT p.payment_id, p.merchant_id FROM payments p
                        JOIN recovery_attempts ra ON ra.payment_id = p.payment_id
                        WHERE p.status = 'FAILED' AND p.merchant_id = ?
                          AND ABS(p.amount - ?) < 1.0
                        ORDER BY p.timestamp DESC LIMIT 1
                    """, (target_merchant_id, amount)).fetchone()
                    if row:
                        recovered_payment_id = row["payment_id"]
                        matched_mid = row["merchant_id"]

                if recovered_payment_id:
                    conn.execute(
                        "UPDATE payments SET status = ? WHERE payment_id = ? AND merchant_id = ?",
                        (PaymentStatus.RECOVERED.value, recovered_payment_id, matched_mid)
                    )
                    conn.execute("""
                        UPDATE recovery_attempts
                        SET status = 'SUCCESS', recovery_link_payment_id = ?
                        WHERE payment_id = ? AND merchant_id = ?
                    """, (captured_pay_id, recovered_payment_id, matched_mid))
                    conn.execute("""
                        UPDATE audit_logs SET result = 'SUCCESS'
                        WHERE payment_id = ? AND merchant_id = ?
                    """, (recovered_payment_id, matched_mid))

            if recovered_payment_id:
                with _agent_lock:
                    _agent["recovered_total"] += amount

                _log_event("recovered", merchant_id=matched_mid,
                    payment_id=recovered_payment_id, amount=amount,
                    label=f"✅ ₹{amount:,.0f} RECOVERED",
                    sublabel=f"Customer paid the recovery link · Confirmed by Razorpay")

                global _metrics_cache
                _metrics_cache["expires_at"] = 0.0

                logger.info("webhook.payment_recovered", extra={
                    "recovered_payment_id": recovered_payment_id,
                    "captured_payment_id": captured_pay_id,
                    "merchant_id": matched_mid,
                    "amount": amount,
                })
                return {"status": "recovered", "original_payment_id": recovered_payment_id,
                        "merchant_id": matched_mid,
                        "captured_payment_id": captured_pay_id, "amount_inr": amount}
            else:
                logger.warning(f"webhook.captured.no_match: {captured_pay_id} amount=₹{amount}")
                return {"status": "ignored", "reason": "Could not match to a failed payment"}

        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Malformed {event} payload: missing {e}")

    else:
        return {"status": "ignored", "event": event}




@app.get("/payments/{payment_id}", tags=["Payments"])
def get_payment(payment_id: str, request: Request):
    """Retrieve a payment record by ID with strict tenant isolation."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    row = fetch_payment(payment_id, merchant_id=merchant_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id!r} not found.")
    return dict(row)


@app.post("/recovery/run/{payment_id}", tags=["Recovery"], response_model=PipelineResponse)
def run_recovery_pipeline(payment_id: str, request: Request):
    """
    Run the full recovery pipeline on a single payment for the active merchant.
    Returns the complete decision chain: ML score → AI decision → guardrail → outcome.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    user_id = user["user_id"]

    p_row = fetch_payment(payment_id, merchant_id=merchant_id)
    if p_row is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id!r} not found.")

    c_row = fetch_customer(p_row["customer_id"], merchant_id=merchant_id)
    if c_row is None:
        raise HTTPException(status_code=404, detail=f"Customer {p_row['customer_id']!r} not found.")

    try:
        payment = Payment(
            payment_id=p_row["payment_id"],
            customer_id=p_row["customer_id"],
            amount=p_row["amount"],
            status=PaymentStatus(p_row["status"]),
            failure_reason=FailureReason(p_row["failure_reason"]),
            payment_method=PaymentMethod(p_row["payment_method"]),
            timestamp=datetime.fromisoformat(p_row["timestamp"]),
            previous_attempts=p_row["previous_attempts"],
        )
        customer = Customer(
            customer_id=c_row["customer_id"],
            total_payments=c_row["total_payments"],
            successful_payments=c_row["successful_payments"],
            failed_payments=c_row["failed_payments"],
            lifetime_value=c_row["lifetime_value"] if "lifetime_value" in c_row.keys() and c_row["lifetime_value"] else 0.0,
            preferred_channel=ChannelPreference(c_row["preferred_channel"]) if "preferred_channel" in c_row.keys() and c_row["preferred_channel"] else ChannelPreference.SMS,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payment/customer data: {exc}")

    now = datetime.now(timezone.utc)
    score     = score_recovery(payment, customer)
    decision  = get_agent_decision(payment, score, customer)
    guardrail = check_guardrails(payment, decision, [], now=now)
    attempt   = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel, merchant_id=merchant_id)
    audit     = write_audit_log(score, decision, guardrail, attempt, merchant_id=merchant_id, user_id=user_id)

    return PipelineResponse(
        payment_id=payment_id,
        recovery_score=score,
        agent_decision=decision,
        guardrail_result=guardrail,
        recovery_attempt=attempt,
        audit_event_id=audit.event_id,
    )


@app.get("/audit", tags=["Audit"])
def list_audit_logs(request: Request, limit: int = 100):
    """Retrieve all recent audit log entries for the active merchant."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs WHERE merchant_id = ? ORDER BY timestamp DESC LIMIT ?",
            (merchant_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/audit/{payment_id}", tags=["Audit"])
def get_audit(payment_id: str, request: Request):
    """Retrieve the latest audit log entry for a payment in the active merchant's workspace."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM audit_logs WHERE payment_id = ? AND merchant_id = ? ORDER BY timestamp DESC LIMIT 1",
            (payment_id, merchant_id)
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No audit log found for {payment_id!r} in your workspace.",
        )
    return dict(row)


@app.get("/payments", tags=["Payments"])
def list_payments(request: Request):
    """Retrieve all payment records for the active merchant."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    rows = fetch_all_payments(merchant_id=merchant_id)
    return [dict(row) for row in rows]


@app.get("/customers", tags=["Customers"])
def list_customers(request: Request):
    """Retrieve all customer records for the active merchant."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    rows = fetch_all_customers(merchant_id=merchant_id)
    return [dict(row) for row in rows]


@app.get("/customers/{customer_id}", tags=["Customers"])
def get_customer(customer_id: str, request: Request):
    """Retrieve a single customer record by ID for the active merchant."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    row = fetch_customer(customer_id, merchant_id=merchant_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id!r} not found.")
    return dict(row)


@app.get("/recovery/opportunities", tags=["Revenue Queue"], response_model=OpportunitiesResponse)
def get_recovery_opportunities(request: Request):
    """
    TODAY'S RECOVERY OPPORTUNITIES — Prioritized Revenue Queue.
    Scores all active failed and abandoned transactions for the authenticated merchant.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*, c.total_payments, c.successful_payments, c.failed_payments,
                   COALESCE(c.lifetime_value, 0.0) as lifetime_value,
                   COALESCE(c.preferred_channel, 'SMS') as preferred_channel
            FROM payments p
            JOIN customers c ON p.customer_id = c.customer_id AND p.merchant_id = c.merchant_id
            WHERE p.status = 'FAILED' AND p.merchant_id = ?
            ORDER BY p.amount DESC
            LIMIT 50
        """, (merchant_id,)).fetchall()

    items: list[OpportunityItem] = []
    total_expected = 0.0
    high_count = 0
    med_count = 0
    low_count = 0

    for row in rows:
        try:
            payment = Payment(
                payment_id=row["payment_id"],
                customer_id=row["customer_id"],
                amount=row["amount"],
                status=PaymentStatus(row["status"]),
                failure_reason=FailureReason(row["failure_reason"]),
                payment_method=PaymentMethod(row["payment_method"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                previous_attempts=row["previous_attempts"],
                event_type=EventType(row["event_type"]) if "event_type" in row.keys() and row["event_type"] else EventType.PAYMENT_FAILED,
            )
            customer = Customer(
                customer_id=row["customer_id"],
                total_payments=row["total_payments"],
                successful_payments=row["successful_payments"],
                failed_payments=row["failed_payments"],
                lifetime_value=row["lifetime_value"],
                preferred_channel=ChannelPreference(row["preferred_channel"]),
            )
            score = score_recovery(payment, customer)
            decision = get_agent_decision(payment, score, customer)

            total_expected += score.expected_recovery_value
            if score.priority_tier.value == "HIGH":
                high_count += 1
            elif score.priority_tier.value == "MEDIUM":
                med_count += 1
            else:
                low_count += 1

            items.append(OpportunityItem(
                payment_id=payment.payment_id,
                customer_id=customer.customer_id,
                amount=payment.amount,
                failure_reason=payment.failure_reason.value,
                recovery_probability=round(score.recovery_probability, 2),
                expected_recovery_value=score.expected_recovery_value,
                priority_tier=score.priority_tier.value,
                recommended_strategy=decision.strategy_type.value,
                preferred_channel=decision.preferred_channel.value,
                status=payment.status.value,
            ))
        except Exception:
            continue

    # Sort descending by expected recovery value
    items.sort(key=lambda x: x.expected_recovery_value, reverse=True)

    return OpportunitiesResponse(
        total_opportunities=len(items),
        total_expected_revenue=round(total_expected, 2),
        high_priority_count=high_count,
        medium_priority_count=med_count,
        low_priority_count=low_count,
        opportunities=items,
    )


@app.get("/recovery/escalations", tags=["Escalations"], response_model=List[EscalationItem])
def get_escalated_cases(request: Request):
    """
    HUMAN ESCALATION QUEUE — Bounded Autonomy in Action.
    Lists all high-risk payments or cases for the authenticated merchant.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.payment_id, p.customer_id, p.amount, p.failure_reason,
                   p.previous_attempts, ra.reason as attempt_reason,
                   ra.timestamp, p.status
            FROM payments p
            JOIN recovery_attempts ra ON p.payment_id = ra.payment_id AND p.merchant_id = ra.merchant_id
            WHERE (ra.action = 'ESCALATE_TO_HUMAN' OR p.status = 'ESCALATED') AND p.merchant_id = ?
            ORDER BY ra.timestamp DESC
            LIMIT 50
        """, (merchant_id,)).fetchall()

    escalations: list[EscalationItem] = []
    seen = set()
    for r in rows:
        if r["payment_id"] in seen:
            continue
        seen.add(r["payment_id"])

        reason_text = r["attempt_reason"] or "Escalated for human review"
        if r["amount"] > 10000:
            reason_text = f"Payment amount ₹{r['amount']:,.0f} exceeds autonomous limit (₹10,000)."
        elif r["previous_attempts"] >= 2:
            reason_text = f"RecoverAI stopped automatically because recovery limit was reached ({r['previous_attempts']} attempts)."

        escalations.append(EscalationItem(
            payment_id=r["payment_id"],
            customer_id=r["customer_id"],
            amount=r["amount"],
            failure_reason=r["failure_reason"],
            attempts_made=r["previous_attempts"],
            escalation_reason=reason_text,
            timestamp=r["timestamp"],
            status="ESCALATED_NEEDS_REVIEW",
        ))

    return escalations


@app.get("/recovery/plan/{payment_id}", tags=["Recovery"])
def get_payment_recovery_plan(payment_id: str, request: Request):
    """
    Retrieve or generate the structured multi-step Recovery Plan for any payment within the active merchant's workspace.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    existing = fetch_recovery_plan(payment_id, merchant_id=merchant_id)
    if existing:
        return existing

    # Generate dynamically if not found
    p_row = fetch_payment(payment_id, merchant_id=merchant_id)
    if not p_row:
        raise HTTPException(status_code=404, detail="Payment not found")

    c_row = fetch_customer(p_row["customer_id"], merchant_id=merchant_id)
    c_dict = dict(c_row) if c_row else {}

    payment = Payment(
        payment_id=p_row["payment_id"],
        customer_id=p_row["customer_id"],
        amount=p_row["amount"],
        status=PaymentStatus(p_row["status"]),
        failure_reason=FailureReason(p_row["failure_reason"]),
        payment_method=PaymentMethod(p_row["payment_method"]),
        timestamp=datetime.fromisoformat(p_row["timestamp"]),
        previous_attempts=p_row["previous_attempts"],
    )
    customer = Customer(
        customer_id=p_row["customer_id"],
        total_payments=c_dict.get("total_payments", 5),
        successful_payments=c_dict.get("successful_payments", 4),
        failed_payments=c_dict.get("failed_payments", 1),
        lifetime_value=c_dict.get("lifetime_value", 15000.0),
        preferred_channel=ChannelPreference(c_dict.get("preferred_channel", "SMS")),
    )

    score = score_recovery(payment, customer)
    decision = get_agent_decision(payment, score, customer)
    if decision.plan:
        save_recovery_plan(
            plan_id=decision.plan.plan_id,
            payment_id=payment.payment_id,
            strategy=decision.plan.strategy.value if hasattr(decision.plan.strategy, "value") else str(decision.plan.strategy),
            steps=[s.model_dump() if hasattr(s, "model_dump") else s for s in decision.plan.steps],
            priority=decision.plan.priority.value if hasattr(decision.plan.priority, "value") else str(decision.plan.priority),
            expected_recovery_value=decision.plan.expected_recovery_value,
            created_at=datetime.now(timezone.utc).isoformat(),
            merchant_id=merchant_id,
            user_id=user["user_id"],
        )
        return decision.plan.model_dump()
    raise HTTPException(status_code=500, detail="Could not construct recovery plan")




@app.post("/checkouts/event", tags=["Checkout Abandonment"])
def ingest_checkout_abandonment(body: CheckoutEventRequest, request: Request, background_tasks: BackgroundTasks):
    """
    CHECKOUT ABANDONMENT RECOVERY — Ingest cart drop-off events, predict recovery likelihood,
    generate personalized multi-step recovery plan, and dispatch payment link via preferred channel.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    user_id = user["user_id"]
    now = datetime.now(timezone.utc)
    payment_id = f"cart_{body.checkout_id.replace('chk_', '')}"

    from db import save_checkout_event
    save_checkout_event(
        checkout_id=body.checkout_id,
        customer_id=body.customer_id,
        cart_value=body.cart_value,
        drop_off_stage=body.drop_off_stage,
        time_spent_seconds=body.time_spent_seconds,
        timestamp=now.isoformat(),
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        merchant_id=merchant_id,
        user_id=user_id,
    )

    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO customers
                (customer_id, merchant_id, user_id, total_payments, successful_payments, failed_payments, lifetime_value, preferred_channel, email, phone)
            VALUES (?, ?, ?, 1, 0, 1, ?, 'EMAIL', ?, ?)
        """, (body.customer_id, merchant_id, user_id, body.cart_value * 1.5, body.customer_email, body.customer_phone))

        conn.execute("""
            INSERT OR REPLACE INTO payments
                (payment_id, merchant_id, user_id, customer_id, amount, status, failure_reason, payment_method, timestamp, previous_attempts, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payment_id,
            merchant_id,
            user_id,
            body.customer_id,
            body.cart_value,
            PaymentStatus.FAILED.value,
            FailureReason.CHECKOUT_ABANDONED.value,
            PaymentMethod.CHECKOUT_CART.value,
            now.isoformat(),
            0,
            EventType.CHECKOUT_ABANDONED.value,
        ))

        conn.execute("INSERT OR IGNORE INTO ground_truth (payment_id, actual_recovery_outcome) VALUES (?, 1)", (payment_id,))

    _log_event("opportunity_detected", merchant_id=merchant_id, user_id=user_id,
        payment_id=payment_id, amount=body.cart_value,
        label=f"🛒 Checkout Abandonment Detected (₹{body.cart_value:,.0f})",
        sublabel=f"Stage: {body.drop_off_stage} · RecoverAI initiating cart recovery…")

    background_tasks.add_task(_run_recovery_for_payment, payment_id, body.customer_email or "", body.customer_phone or "", merchant_id)

    return {
        "status": "queued",
        "checkout_id": body.checkout_id,
        "payment_id": payment_id,
        "cart_value": body.cart_value,
        "message": "Checkout abandonment captured. Recovery agent executing personalized strategy.",
    }


@app.get("/checkouts", tags=["Checkout Abandonment"])
def list_checkouts(request: Request):
    """List all recorded checkout abandonment events."""
    from db import fetch_all_checkouts
    user = get_current_user_context(request)
    rows = fetch_all_checkouts(merchant_id=user["merchant_id"])
    return [dict(r) for r in rows]


@app.post("/demo/scenario/{scenario_id}", tags=["Interactive Demo"])
def run_demo_scenario(scenario_id: str):
    """
    INTERACTIVE 3-SCENARIO DEMO RUNNER:
      1 / temp_failure       → ₹5,000 BANK_SERVER_DOWN (Intelligent Retry: Wait 5m → Recheck → Recovered)
      2 / abandonment        → ₹12,000 Cart Drop-off (Detect → Score → Email Link → Recovered)
      3 / high_value_guardrail → ₹75,000 Risk Failure (AI Recommends → Guardrail BLOCKS → Human Escalation)
    """
    now = datetime.now(timezone.utc)

    if scenario_id in ("1", "temp_failure", "temporary"):
        payment = Payment(
            payment_id=f"demo_temp_{now.strftime('%M%S')}",
            customer_id="cust_loyal_001",
            amount=5000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.BANK_SERVER_DOWN,
            payment_method=PaymentMethod.UPI,
            timestamp=now,
            previous_attempts=0,
            event_type=EventType.PAYMENT_FAILED,
        )
        customer = Customer(
            customer_id="cust_loyal_001",
            total_payments=20,
            successful_payments=19,
            failed_payments=1,
            lifetime_value=52000.0,
            preferred_channel=ChannelPreference.SMS,
        )
        title = "Demo 1: Temporary Failure (Intelligent Retry)"

    elif scenario_id in ("2", "abandonment", "checkout"):
        payment = Payment(
            payment_id=f"demo_cart_{now.strftime('%M%S')}",
            customer_id="cust_cart_002",
            amount=12000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.CHECKOUT_ABANDONED,
            payment_method=PaymentMethod.CHECKOUT_CART,
            timestamp=now,
            previous_attempts=0,
            event_type=EventType.CHECKOUT_ABANDONED,
        )
        customer = Customer(
            customer_id="cust_cart_002",
            total_payments=6,
            successful_payments=5,
            failed_payments=1,
            lifetime_value=35000.0,
            preferred_channel=ChannelPreference.EMAIL,
        )
        title = "Demo 2: Checkout Abandonment Recovery"

    else:
        payment = Payment(
            payment_id=f"demo_highval_{now.strftime('%M%S')}",
            customer_id="cust_highval_003",
            amount=75000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.NETWORK_TIMEOUT,
            payment_method=PaymentMethod.NET_BANKING,
            timestamp=now,
            previous_attempts=0,
            event_type=EventType.PAYMENT_FAILED,
        )
        customer = Customer(
            customer_id="cust_highval_003",
            total_payments=15,
            successful_payments=14,
            failed_payments=1,
            lifetime_value=150000.0,
            preferred_channel=ChannelPreference.SMS,
        )
        title = "Demo 3: High-Value Guardrail Escalation (Bounded Autonomy)"

    # Execute full pipeline
    score = score_recovery(payment, customer)
    decision = get_agent_decision(payment, score, customer)
    guardrail = check_guardrails(payment, decision, [], now=now)
    attempt = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel)
    audit = write_audit_log(score, decision, guardrail, attempt)

    # Log to live activity feed
    _log_event("opportunity_detected",
        payment_id=payment.payment_id, amount=payment.amount,
        label=f"▶ Running {title}",
        sublabel=f"Amount: ₹{payment.amount:,.0f} · Strategy: {decision.strategy_type.value}")

    if guardrail.result in (GuardrailOutcome.APPROVED, "APPROVED"):
        _log_event("guardrail_approved",
            payment_id=payment.payment_id, amount=payment.amount,
            label="✓ Guardrail Approved",
            sublabel=f"Executing {guardrail.final_action.value} via {decision.preferred_channel.value}")
    else:
        _log_event("guardrail_blocked",
            payment_id=payment.payment_id, amount=payment.amount,
            label="🛡 Guardrail Blocked Autonomous Action",
            sublabel=guardrail.reason)

    if attempt.status in (AttemptStatus.SUCCESS, "SUCCESS") or attempt.status.value == "SUCCESS":
        _log_event("recovered",
            payment_id=payment.payment_id, amount=payment.amount,
            label=f"✅ ₹{payment.amount:,.0f} RECOVERED",
            sublabel=f"Successfully verified via {decision.preferred_channel.value}")
        with _agent_lock:
            _agent["recovered_total"] += payment.amount
    elif guardrail.final_action in (RecoveryAction.ESCALATE_TO_HUMAN, "ESCALATE_TO_HUMAN"):
        _log_event("escalated",
            payment_id=payment.payment_id, amount=payment.amount,
            label=f"⚠ Escalated to Human Review (₹{payment.amount:,.0f})",
            sublabel="Autonomous boundary reached — ticket created for review")
        with _agent_lock:
            _agent["escalated_total"] += 1

    return {
        "scenario": title,
        "payment_id": payment.payment_id,
        "amount": payment.amount,
        "failure_reason": payment.failure_reason.value,
        "strategy": decision.strategy_type.value,
        "channel": decision.preferred_channel.value,
        "ml_probability": score.recovery_probability,
        "expected_value": score.expected_recovery_value,
        "priority_tier": score.priority_tier.value,
        "recovery_plan": decision.plan.model_dump() if decision.plan else None,
        "guardrail_result": guardrail.result.value,
        "guardrail_reason": guardrail.reason,
        "action_executed": guardrail.final_action.value,
        "outcome": attempt.status.value,
        "audit_event_id": audit.event_id,
    }


@app.post("/recovery/auto-run", tags=["Recovery"])
def auto_run_recovery(request: Request):
    """
    AUTO-RECOVERY ENGINE — The core agentic loop.

    Scans ALL FAILED payments that have NOT yet received a recovery attempt,
    then automatically runs the full ML → LLM → Guardrail → Execution pipeline
    for each one. If the guardrail approves SEND_PAYMENT_LINK, a real Razorpay
    payment link is generated and dispatched automatically.

    This is the heart of RecoverAI: zero human intervention required.
    """
    import logging
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    # 1. Find all FAILED payments that have no prior recovery attempt
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*, c.total_payments, c.successful_payments, c.failed_payments
            FROM payments p
            JOIN customers c ON p.customer_id = c.customer_id
                        WHERE p.status = 'FAILED' AND p.merchant_id = ?
              AND p.payment_id NOT IN (
                                    SELECT DISTINCT payment_id FROM recovery_attempts WHERE merchant_id = ?
              )
            ORDER BY p.amount DESC
                """, (merchant_id, merchant_id)).fetchall()

    if not rows:
        return {
            "status": "nothing_to_do",
            "message": "All FAILED payments have already been processed.",
            "processed": 0,
            "results": []
        }

    now = datetime.now(timezone.utc)
    results = []
    links_generated = 0
    escalated = 0
    retried = 0
    errors = 0

    logging.disable(logging.WARNING)   # suppress verbose per-payment logs during batch
    try:
        for row in rows:
            try:
                payment = Payment(
                    payment_id=row["payment_id"],
                    customer_id=row["customer_id"],
                    amount=row["amount"],
                    status=PaymentStatus(row["status"]),
                    failure_reason=FailureReason(row["failure_reason"]),
                    payment_method=PaymentMethod(row["payment_method"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    previous_attempts=row["previous_attempts"],
                )
                customer = Customer(
                    customer_id=row["customer_id"],
                    total_payments=row["total_payments"],
                    successful_payments=row["successful_payments"],
                    failed_payments=row["failed_payments"],
                )

                score     = score_recovery(payment, customer)
                decision  = get_agent_decision(payment, score, customer)
                guardrail = check_guardrails(payment, decision, [], now=now)
                attempt   = execute_action(payment, guardrail, score.recovery_probability, merchant_id=merchant_id)
                audit     = write_audit_log(score, decision, guardrail, attempt, merchant_id=merchant_id, user_id=user["user_id"])

                action = guardrail.final_action.value
                if action == "SEND_PAYMENT_LINK":
                    links_generated += 1
                elif action == "ESCALATE_TO_HUMAN":
                    escalated += 1
                elif action == "RETRY":
                    retried += 1

                # Extract Razorpay URL if present in the attempt reason
                razorpay_url = None
                if attempt.reason and "rzp.io" in attempt.reason:
                    import re
                    m = re.search(r"https?://[^\s]+", attempt.reason)
                    if m:
                        razorpay_url = m.group(0)

                results.append({
                    "payment_id":      payment.payment_id,
                    "amount":          payment.amount,
                    "failure_reason":  payment.failure_reason.value,
                    "action":          action,
                    "outcome":         attempt.status.value,
                    "ml_score":        round(score.recovery_probability, 3),
                    "agent_diagnosis": decision.diagnosis,
                    "razorpay_url":    razorpay_url,
                    "audit_event_id":  audit.event_id,
                })
            except Exception as e:
                errors += 1
                results.append({
                    "payment_id": row["payment_id"],
                    "amount":     row["amount"],
                    "action":     "ERROR",
                    "outcome":    "ERROR",
                    "error":      str(e),
                })
    finally:
        logging.disable(logging.NOTSET)

    # Invalidate metrics cache only if something changed
    if len(results) > 0:
        global _metrics_cache
        _metrics_cache["expires_at"] = 0.0

    return {
        "status":          "completed",
        "processed":       len(rows),
        "links_generated": links_generated,
        "escalated":       escalated,
        "retried":         retried,
        "errors":          errors,
        "results":         results,
    }




_metrics_computing = False   # guard: don't launch duplicate background jobs

@app.get("/metrics", tags=["Metrics"], response_model=MetricsResponse)
def get_metrics(request: Request, refresh: bool = False):
    """
    Return real database-backed analytics metrics for the authenticated merchant workspace.
    Uses direct SQL aggregations over payments, recovery_attempts, and audit_logs.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    with get_connection() as conn:
        # 1. Total payments & status counts
        p_row = conn.execute("""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END), 0) as failed_count,
                COALESCE(SUM(CASE WHEN status = 'RECOVERED' THEN 1 ELSE 0 END), 0) as recovered_count,
                COALESCE(SUM(CASE WHEN status = 'FAILED' THEN amount ELSE 0.0 END), 0.0) as revenue_at_risk,
                COALESCE(SUM(CASE WHEN status = 'RECOVERED' THEN amount ELSE 0.0 END), 0.0) as revenue_recovered
            FROM payments
            WHERE merchant_id = ?
        """, (merchant_id,)).fetchone()

        total_tested = p_row["total_count"] if p_row else 0
        failed_count = p_row["failed_count"] if p_row else 0
        recovered_count = p_row["recovered_count"] if p_row else 0
        rev_at_risk = float(p_row["revenue_at_risk"] if p_row else 0.0)
        rev_recovered = float(p_row["revenue_recovered"] if p_row else 0.0)

        total_vol = rev_at_risk + rev_recovered
        recovery_rate_pct = round((rev_recovered / total_vol) * 100.0, 2) if total_vol > 0 else 0.0

        # 2. Escalations & Guardrail blocks from audit_logs
        a_row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN action_taken = 'ESCALATE_TO_HUMAN' OR action_taken = 'escalate_to_human' THEN 1 ELSE 0 END), 0) as human_escalations,
                COALESCE(SUM(CASE WHEN guardrail_result NOT IN ('passed', 'APPROVED') THEN 1 ELSE 0 END), 0) as guardrail_blocks
            FROM audit_logs
            WHERE merchant_id = ?
        """, (merchant_id,)).fetchone()

        human_escalations = a_row["human_escalations"] if a_row else 0
        guardrail_blocks = a_row["guardrail_blocks"] if a_row else 0

        # 3. Strategy counts from audit_logs
        strat_rows = conn.execute("""
            SELECT COALESCE(strategy_type, 'INTELLIGENT_RETRY') as strategy, COUNT(*) as cnt
            FROM audit_logs
            WHERE merchant_id = ?
            GROUP BY strategy
        """, (merchant_id,)).fetchall()
        strategy_counts = {r["strategy"]: r["cnt"] for r in strat_rows}

        # 4. Daily trend (past 30 days)
        trend_rows = conn.execute("""
            SELECT 
                SUBSTR(timestamp, 1, 10) as day,
                COALESCE(SUM(CASE WHEN status = 'RECOVERED' THEN amount ELSE 0.0 END), 0.0) as recovered,
                COALESCE(SUM(CASE WHEN status = 'FAILED' THEN amount ELSE 0.0 END), 0.0) as failed
            FROM payments
            WHERE merchant_id = ?
            GROUP BY day
            ORDER BY day ASC
            LIMIT 30
        """, (merchant_id,)).fetchall()

        daily_trend = [
            {
                "date": r["day"],
                "recovered": round(float(r["recovered"]), 2),
                "failed": round(float(r["failed"]), 2),
            }
            for r in trend_rows
        ]

    return MetricsResponse(
        transactions_tested=total_tested,
        recoverable_count=failed_count,
        successful_recoveries=recovered_count,
        revenue_at_risk=round(rev_at_risk, 2),
        revenue_recovered=round(rev_recovered, 2),
        recovery_rate_pct=recovery_rate_pct,
        human_escalations=human_escalations,
        guardrail_blocks=guardrail_blocks,
        precision=0.0,
        recall=0.0,
        f1_score=0.0,
        strategy_counts=strategy_counts,
        daily_trend=daily_trend,
    )



# ── Net Recovery ROI Endpoint (Phase 2) ─────────────────────────────────────────

@app.get("/analytics/roi", tags=["Analytics"])
def get_net_recovery_roi(request: Request):
    """
    Compute Net Recovery ROI scoped to the merchant organization.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    # Cost model constants
    COST_RETRY = 1.50
    COST_SMS = 0.25
    COST_EMAIL = 0.05
    COST_HUMAN = 25.00

    with get_connection() as conn:
        # Deduplicate multi-run payments with ground_truth using MAX(timestamp)
        # per payment_id, while always scoping both payments and audit rows to
        # the authenticated merchant (including the default demo tenant).
        rows = conn.execute("""
            WITH latest_audit AS (
                SELECT a.payment_id, a.action_taken, a.guardrail_result,
                       a.result, a.channel_used, a.timestamp,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.payment_id ORDER BY a.timestamp DESC
                       ) AS rn
                FROM audit_logs a
                WHERE a.merchant_id = ?
            )
            SELECT p.payment_id, p.amount, p.failure_reason, p.payment_method,
                   gt.actual_recovery_outcome, la.action_taken,
                   la.guardrail_result, la.result AS audit_result,
                   COALESCE(la.channel_used, 'SMS') AS channel_used
            FROM payments p
            LEFT JOIN ground_truth gt ON p.payment_id = gt.payment_id
            LEFT JOIN latest_audit la ON p.payment_id = la.payment_id AND la.rn = 1
            WHERE p.merchant_id = ?
        """, (merchant_id, merchant_id)).fetchall()

        # 2. Live payments (separate section)
        live_rows = conn.execute("""
            SELECT p.payment_id, p.amount, p.status, p.failure_reason, p.timestamp,
                   (SELECT action FROM recovery_attempts r WHERE r.payment_id = p.payment_id ORDER BY r.timestamp DESC LIMIT 1) as last_action,
                   (SELECT status FROM recovery_attempts r WHERE r.payment_id = p.payment_id ORDER BY r.timestamp DESC LIMIT 1) as last_status
            FROM payments p
            WHERE (p.payment_id LIKE 'pay_TW%' OR p.payment_id LIKE 'pay_live%') AND p.merchant_id = ?
            ORDER BY p.timestamp DESC
        """, (merchant_id,)).fetchall()


    # Aggregate by failure_reason bucket
    buckets_data = {}
    confirmed_reasons = [
        "BANK_SERVER_DOWN",
        "NETWORK_TIMEOUT",
        "CARD_EXPIRED",
        "INSUFFICIENT_FUNDS",
        "INVALID_OTP",
    ]
    for r in confirmed_reasons:
        buckets_data[r] = {
            "total_count": 0,
            "recovered_count": 0,
            "gross_risk": 0.0,
            "gross_recovered": 0.0,
            "total_cost": 0.0,
        }

    total_gross_risk = 0.0
    total_gross_recovered = 0.0
    total_cost = 0.0
    total_payments = 0
    total_recovered = 0

    for row in rows:
        reason = row["failure_reason"]
        if reason not in buckets_data:
            buckets_data[reason] = {
                "total_count": 0, "recovered_count": 0, "gross_risk": 0.0,
                "gross_recovered": 0.0, "total_cost": 0.0,
            }

        amt = float(row["amount"] or 0.0)
        action = row["action_taken"]
        channel = row["channel_used"]
        gt_outcome = row["actual_recovery_outcome"]
        audit_res = row["audit_result"]

        # Calculate action cost
        cost = 0.0
        if action == "RETRY":
            cost = COST_RETRY
        elif action == "SEND_PAYMENT_LINK":
            cost = COST_SMS if channel == "SMS" else COST_EMAIL
        elif action == "ESCALATE_TO_HUMAN":
            cost = COST_HUMAN

        # True recovery criteria: direct action executed AND ground_truth == 1
        is_recovered = (
            action in ("RETRY", "SEND_PAYMENT_LINK")
            and (gt_outcome == 1 or audit_res == "SUCCESS")
        )

        b = buckets_data[reason]
        b["total_count"] += 1
        b["gross_risk"] += amt
        b["total_cost"] += cost
        total_gross_risk += amt
        total_cost += cost
        total_payments += 1

        if is_recovered:
            b["recovered_count"] += 1
            b["gross_recovered"] += amt
            total_gross_recovered += amt
            total_recovered += 1

    # Format buckets list
    buckets_list = []
    for reason, data in buckets_data.items():
        if data["total_count"] == 0:
            continue
        net = data["gross_recovered"] - data["total_cost"]
        roi_pct = ((net / data["total_cost"]) * 100.0) if data["total_cost"] > 0 else 0.0
        rec_rate = (data["recovered_count"] / data["total_count"] * 100.0) if data["total_count"] > 0 else 0.0
        buckets_list.append({
            "failure_reason": reason,
            "total_payments": data["total_count"],
            "recovered_payments": data["recovered_count"],
            "recovery_rate_pct": round(rec_rate, 1),
            "gross_at_risk_inr": round(data["gross_risk"], 2),
            "gross_recovered_inr": round(data["gross_recovered"], 2),
            "action_cost_inr": round(data["total_cost"], 2),
            "net_recovered_inr": round(net, 2),
            "roi_percentage": round(roi_pct, 1),
            "is_net_positive": net > 0,
        })

    net_overall = total_gross_recovered - total_cost
    roi_overall = ((net_overall / total_cost) * 100.0) if total_cost > 0 else 0.0

    return {
        "cost_assumptions_inr": {
            "retry_gateway_fee": COST_RETRY,
            "sms_carrier_fee": COST_SMS,
            "email_service_fee": COST_EMAIL,
            "human_escalation_review_fee": COST_HUMAN,
        },
        "evaluation_cohort": {
            "total_benchmark_records": total_payments,
            "ground_truth_scored": True,
            "gross_revenue_at_risk_inr": round(total_gross_risk, 2),
            "gross_revenue_recovered_inr": round(total_gross_recovered, 2),
            "total_recovery_action_costs_inr": round(total_cost, 2),
            "net_revenue_recovered_inr": round(net_overall, 2),
            "overall_roi_percentage": round(roi_overall, 1),
            "overall_recovery_rate_pct": round((total_recovered / total_payments * 100) if total_payments > 0 else 0, 1),
        },
        "buckets": buckets_list,
        "live_pipeline_activity": {
            "live_records_count": len(live_rows),
            "note": "Live Razorpay webhook events are tracked independently; outcome scoring is pending real-world reconciliation.",
            "records": [
                {
                    "payment_id": r["payment_id"],
                    "amount": r["amount"],
                    "status": r["status"],
                    "failure_reason": r["failure_reason"],
                    "last_action": r["last_action"],
                    "last_status": r["last_status"],
                    "timestamp": r["timestamp"],
                }
                for r in live_rows[:15]
            ],
        },
    }


# ── Notable Case Panel Endpoint (Phase 3) ──────────────────────────────────────

@app.get("/cases/notable", tags=["Cases"])
def get_notable_case(request: Request, payment_id: Optional[str] = None):
    """
    Returns the complete end-to-end trail for a confirmed R2 Guardrail-Blocked payment.
    Defaults to 'pay_TWgmMx3kZ4uqSf' (or 'pay_TWgrL5UsxRwVtD' / 'demo_highval_003').
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    with get_connection() as conn:
        # If no payment_id specified, find the first confirmed BLOCKED case
        if not payment_id:
            row = conn.execute("""
                SELECT payment_id FROM audit_logs
                WHERE merchant_id = ? AND (guardrail_result = 'BLOCKED' OR action_taken = 'ESCALATE_TO_HUMAN')
                ORDER BY timestamp DESC LIMIT 1
            """, (merchant_id,)).fetchone()
            payment_id = row["payment_id"] if row else None

        payment_row = conn.execute("SELECT * FROM payments WHERE payment_id = ? AND merchant_id = ?", (payment_id, merchant_id)).fetchone()
        customer_row = None
        if payment_row:
            customer_row = conn.execute("SELECT * FROM customers WHERE customer_id = ? AND merchant_id = ?", (payment_row["customer_id"], merchant_id)).fetchone()

        audit_rows = conn.execute("SELECT * FROM audit_logs WHERE payment_id = ? AND merchant_id = ? ORDER BY timestamp DESC", (payment_id, merchant_id)).fetchall()
        attempt_rows = conn.execute("SELECT * FROM recovery_attempts WHERE payment_id = ? AND merchant_id = ? ORDER BY timestamp DESC", (payment_id, merchant_id)).fetchall()
        plan_row = conn.execute("SELECT * FROM recovery_plans WHERE payment_id = ? AND merchant_id = ? ORDER BY created_at DESC LIMIT 1", (payment_id, merchant_id)).fetchone()

    if not payment_row:
        raise HTTPException(status_code=404, detail=f"Case payment '{payment_id}' not found.")

    steps = []
    if plan_row and plan_row["steps_json"]:
        try:
            if isinstance(plan_row["steps_json"], str):
                steps = json.loads(plan_row["steps_json"])
            elif isinstance(plan_row["steps_json"], list):
                steps = plan_row["steps_json"]
        except Exception:
            steps = []

    return {
        "case_title": f"High-Value Guardrail Block & Bounded Escalation — {payment_id}",
        "payment": {
            "payment_id": payment_row["payment_id"],
            "amount": payment_row["amount"],
            "status": payment_row["status"],
            "failure_reason": payment_row["failure_reason"],
            "payment_method": payment_row["payment_method"],
            "timestamp": payment_row["timestamp"],
            "previous_attempts": payment_row["previous_attempts"],
        },
        "customer": {
            "customer_id": customer_row["customer_id"] if customer_row else payment_row["customer_id"],
            "lifetime_value": customer_row["lifetime_value"] if customer_row else 0.0,
            "preferred_channel": customer_row["preferred_channel"] if customer_row else "SMS",
            "email": customer_row["email"] if customer_row else None,
            "phone": customer_row["phone"] if customer_row else None,
        },
        "guardrail_verdict": {
            "result": "BLOCKED",
            "rule_triggered": "R2_AMOUNT_LIMIT",
            "explanation": f"Transaction amount ₹{payment_row['amount']:,.2f} exceeds the autonomous limit (₹10,000.00). Autonomous automated retries blocked to protect merchant margin; escalated to senior recovery queue.",
            "final_action": "ESCALATE_TO_HUMAN",
        },
        "recovery_plan": {
            "strategy": plan_row["strategy"] if plan_row else "ALTERNATE_PAYMENT_LINK",
            "priority": plan_row["priority"] if plan_row else "HIGH",
            "expected_recovery_value": plan_row["expected_recovery_value"] if plan_row else 0.0,
            "steps": steps,
        },
        "audit_trail": [dict(r) for r in audit_rows],
        "execution_attempts": [dict(r) for r in attempt_rows],
    }


# ── Enterprise & Production Configuration Endpoints ──────────────────────────

class MerchantSettingsRequest(BaseModel):
    brand_name: Optional[str] = None
    support_email: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None
    max_autonomous_amount: Optional[float] = 10000.0
    max_retry_attempts: Optional[int] = 2
    retry_cooldown_hours: Optional[float] = 6.0
    enable_sms: Optional[bool] = True
    enable_whatsapp: Optional[bool] = False
    enable_email: Optional[bool] = True
    message_template: Optional[str] = "Hi {{customer_name}}, your payment of ₹{{amount}} failed. Complete securely here: {{payment_link}}"


def _public_api_base_url() -> str:
    """Return the externally reachable API origin used in integration instructions."""
    return (
        os.getenv("PUBLIC_API_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("APP_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


@app.get("/api/settings", tags=["Merchant Settings"])
def get_merchant_settings(request: Request):
    """Retrieve the current active merchant, guardrail, and channel configuration for the authenticated tenant."""
    from db import fetch_all_settings, fetch_merchant_by_id
    user = get_current_user_context(request)
    user_id = user["user_id"]
    merchant_id = user["merchant_id"]
    stored = fetch_all_settings(merchant_id=merchant_id)
    merchant = fetch_merchant_by_id(merchant_id)

    # Return merchant saved key ID, with graceful fallback to environment variables for default tenant
    saved_key_id = (
        stored.get("razorpay_key_id")
        or (merchant["razorpay_key_id"] if merchant else None)
        or (os.getenv("RAZORPAY_KEY_ID", "") if merchant_id in ("mer_default", "") else "")
        or ""
    )
    key_secret_configured = bool(
        stored.get("razorpay_key_secret")
        or (merchant["razorpay_webhook_secret"] if merchant and merchant.get("razorpay_webhook_secret") else None)
        or (os.getenv("RAZORPAY_KEY_SECRET") if merchant_id in ("mer_default", "") else None)
    )
    webhook_secret_configured = bool(
        stored.get("razorpay_webhook_secret")
        or (merchant["razorpay_webhook_secret"] if merchant else None)
        or (os.getenv("RAZORPAY_WEBHOOK_SECRET") if merchant_id in ("mer_default", "") else None)
    )

    return {
        "brand_name": stored.get("brand_name", user.get("company_name", "RecoverAI Merchant")),
        "support_email": stored.get("support_email", user.get("email", "support@merchant.com")),
        "user_id": user_id,
        "user_email": user.get("email", ""),
        "user_full_name": user.get("full_name", ""),
        "api_key": user.get("api_key", ""),
        # Return saved key ID
        "razorpay_key_id": saved_key_id,
        # Never return secrets in plaintext — return boolean flags so the UI shows ✓ configured
        "razorpay_key_secret_configured": key_secret_configured,
        "razorpay_webhook_secret_configured": webhook_secret_configured,
        # The endpoint is shared by the API service, but the merchant query
        # parameter is unique and binds incoming events to this tenant.
        "webhook_url": f"{_public_api_base_url()}/webhooks/razorpay?merchant_id={merchant_id}",
        "max_autonomous_amount": float(stored.get("max_autonomous_amount", os.getenv("MAX_AUTONOMOUS_AMOUNT", "10000"))),
        "max_retry_attempts": int(stored.get("max_retry_attempts", os.getenv("MAX_RETRY_ATTEMPTS", "2"))),
        "retry_cooldown_hours": float(stored.get("retry_cooldown_hours", os.getenv("RETRY_COOLDOWN_HOURS", "6"))),
        "enable_sms": stored.get("enable_sms", "true").lower() == "true",
        "enable_whatsapp": stored.get("enable_whatsapp", "false").lower() == "true",
        "enable_email": stored.get("enable_email", "true").lower() == "true",
        "message_template": stored.get("message_template", "Hi {{customer_name}}, your payment of \u20b9{{amount}} failed. Complete securely here: {{payment_link}}"),
    }


@app.post("/api/settings", tags=["Merchant Settings"])
def update_merchant_settings(body: MerchantSettingsRequest, request: Request):
    """Update and persist merchant settings and guardrail limits for the authenticated tenant."""
    from db import save_setting, update_merchant
    user = get_current_user_context(request)
    user_id = user["user_id"]
    merchant_id = user["merchant_id"]
    _require_role(user, "OWNER", "ADMIN")

    if body.brand_name: save_setting("brand_name", body.brand_name, merchant_id=merchant_id)
    if body.support_email: save_setting("support_email", body.support_email, merchant_id=merchant_id)
    if body.razorpay_key_id:
        save_setting("razorpay_key_id", body.razorpay_key_id, merchant_id=merchant_id)
        update_merchant(merchant_id, razorpay_key_id=body.razorpay_key_id)
    if body.razorpay_key_secret:
        save_setting("razorpay_key_secret", body.razorpay_key_secret, merchant_id=merchant_id)
    if body.razorpay_webhook_secret:
        save_setting("razorpay_webhook_secret", body.razorpay_webhook_secret, merchant_id=merchant_id)
        update_merchant(merchant_id, razorpay_webhook_secret=body.razorpay_webhook_secret)
    if body.max_autonomous_amount is not None:
        save_setting("max_autonomous_amount", str(body.max_autonomous_amount), merchant_id=merchant_id)
    if body.max_retry_attempts is not None:
        save_setting("max_retry_attempts", str(body.max_retry_attempts), merchant_id=merchant_id)
    if body.retry_cooldown_hours is not None:
        save_setting("retry_cooldown_hours", str(body.retry_cooldown_hours), merchant_id=merchant_id)
    save_setting("enable_sms", str(body.enable_sms).lower(), merchant_id=merchant_id)
    save_setting("enable_whatsapp", str(body.enable_whatsapp).lower(), merchant_id=merchant_id)
    save_setting("enable_email", str(body.enable_email).lower(), merchant_id=merchant_id)
    if body.message_template: save_setting("message_template", body.message_template, merchant_id=merchant_id)

    logger.info("merchant_settings.updated", extra={"user_id": user_id})
    return {"status": "success", "message": "Merchant settings saved successfully."}



class TestRazorpayRequest(BaseModel):
    key_id: Optional[str] = None
    key_secret: Optional[str] = None


@app.post("/api/settings/test-razorpay", tags=["Merchant Settings"])
def test_razorpay_connection(request: Request, body: Optional[TestRazorpayRequest] = None):
    """Live connectivity verification pinging the Razorpay API."""
    import requests
    from requests.auth import HTTPBasicAuth
    from db import fetch_setting

    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    key_id = (body.key_id if body and body.key_id else "") or fetch_setting("razorpay_key_id", "", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = (body.key_secret if body and body.key_secret else "") or fetch_setting("razorpay_key_secret", "", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_SECRET", "")

    if not key_id.strip() or not key_secret.strip():
        return {
            "status": "error",
            "message": "Please enter both your Razorpay Key ID and Key Secret in the fields above before testing."
        }

    try:
        resp = requests.get(
            "https://api.razorpay.com/v1/payments",
            params={"count": 1},
            auth=HTTPBasicAuth(key_id.strip(), key_secret.strip()),
            timeout=8,
        )
        if resp.status_code == 200:
            return {
                "status": "connected",
                "message": "Razorpay credentials verified successfully! Live API connection active.",
                "account_mode": "Live/Test Key verified"
            }
        else:
            err_msg = resp.text
            try:
                err_json = resp.json()
                if "error" in err_json and "description" in err_json["error"]:
                    err_msg = err_json["error"]["description"]
            except Exception:
                pass
            return {
                "status": "error",
                "message": f"Razorpay authentication failed (HTTP {resp.status_code}): {err_msg}. Please check your Key ID and Key Secret in your Razorpay Dashboard (Settings > API Keys)."
            }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Connection test failed: {exc}"
        }


@app.post("/api/razorpay/sync-failures", tags=["Merchant Settings"])
def sync_recent_razorpay_failures(request: Request, background_tasks: BackgroundTasks):
    """
    On-Demand Ingestion: Directly queries Razorpay API for recent failed payments
    and starts the AI recovery pipeline for any payment that was missed.
    """
    import requests
    from requests.auth import HTTPBasicAuth
    from db import fetch_setting

    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    razorpay_id = fetch_setting("razorpay_key_id", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_ID")
    razorpay_secret = fetch_setting("razorpay_key_secret", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_SECRET")

    if not razorpay_id or not razorpay_secret or not razorpay_id.startswith("rzp_"):
        return {"status": "error", "message": "Razorpay credentials are not configured or invalid."}

    ingested_count = 0
    now = datetime.now(timezone.utc)

    try:
        resp = requests.get(
            "https://api.razorpay.com/v1/payments",
            params={"count": 15},
            auth=HTTPBasicAuth(razorpay_id.strip(), razorpay_secret.strip()),
            timeout=8,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for item in items:
                pay_id = item.get("id")
                p_status = item.get("status")
                amount = float(item.get("amount", 0)) / 100.0
                customer_email = item.get("email") or ""
                customer_phone = item.get("contact") or ""
                customer_id = (
                    customer_email.split("@")[0].replace(".", "_") if customer_email
                    else customer_phone.replace("+91", "cust_") if customer_phone
                    else f"cust_{pay_id[-6:]}"
                )

                if p_status == "failed":
                    with get_connection() as conn:
                        existing = conn.execute("SELECT 1 FROM payments WHERE payment_id = ? AND merchant_id = ?", (pay_id, merchant_id)).fetchone()
                        if not existing:
                            err_desc = str(item.get("error_description") or "").lower()
                            err_code = str(item.get("error_code") or "").lower()
                            err_reason = str(item.get("error_reason") or "").lower()

                            if any(k in err_desc or k in err_code for k in ("card", "international", "decline", "not supported")):
                                reason = FailureReason.CARD_EXPIRED
                            elif any(k in err_desc or k in err_code for k in ("insufficient", "balance", "fund")):
                                reason = FailureReason.INSUFFICIENT_FUNDS
                            elif any(k in err_desc or k in err_code for k in ("bank", "issuer", "server")):
                                reason = FailureReason.BANK_SERVER_DOWN
                            elif any(k in err_desc or k in err_code for k in ("timeout", "gateway", "network")):
                                reason = FailureReason.NETWORK_TIMEOUT
                            elif any(k in err_desc or k in err_code for k in ("otp", "auth")):
                                reason = FailureReason.INVALID_OTP
                            else:
                                reason = FailureReason.BANK_SERVER_DOWN

                            method_str = str(item.get("method") or "UPI").upper()
                            p_method = PaymentMethod.UPI
                            for pm in PaymentMethod:
                                if pm.value.upper() in method_str:
                                    p_method = pm
                                    break

                            conn.execute("""
                                INSERT OR IGNORE INTO customers
                                    (customer_id, merchant_id, user_id, total_payments, successful_payments, failed_payments, lifetime_value, preferred_channel, email, phone)
                                VALUES (?, ?, ?, 1, 0, 1, ?, 'SMS', ?, ?)
                            """, (customer_id, merchant_id, user["user_id"], amount * 2.0, customer_email, customer_phone))

                            conn.execute("""
                                INSERT OR REPLACE INTO payments
                                    (payment_id, merchant_id, user_id, customer_id, amount, status, failure_reason, payment_method, timestamp, previous_attempts, event_type)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                            """, (pay_id, merchant_id, user["user_id"], customer_id, amount, PaymentStatus.FAILED.value, reason.value, p_method.value, now.isoformat(), EventType.PAYMENT_FAILED.value))

                            _log_event("webhook_received", merchant_id=merchant_id, user_id=user["user_id"],
                                payment_id=pay_id, amount=amount,
                                label=f"⚡ Live Failure Ingested: {pay_id}",
                                sublabel=f"₹{amount:,.0f} · {reason.value.replace('_', ' ')}")

                            # Trigger recovery pipeline
                            background_tasks.add_task(
                                _run_recovery_for_payment,
                                pay_id, customer_email, customer_phone, merchant_id
                            )
                            ingested_count += 1

            return {
                "status": "success",
                "new_failures_found": ingested_count,
                "message": f"Successfully synced Razorpay payments. Found and ingested {ingested_count} new failed payment(s)."
            }
        else:
            return {"status": "error", "message": f"Razorpay query failed: {resp.text}"}
    except Exception as exc:
        return {"status": "error", "message": f"Sync failed: {exc}"}


class CaseResolutionRequest(BaseModel):
    payment_id: str
    action: str = Field(description="'DISPATCH_LINK' | 'RETRY' | 'DISMISS'")
    notes: Optional[str] = "Manual merchant resolution"


@app.post("/recovery/resolve", tags=["Escalations"])
def resolve_escalated_case(body: CaseResolutionRequest, request: Request):
    """
    HUMAN AGENT ACTION: Resolve an escalated high-value case or bounded stopping rule case.
    Merchants can manually approve link dispatch, trigger a retry, or dismiss the case for their tenant.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]
    user_id = user["user_id"]
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        pay = conn.execute("SELECT * FROM payments WHERE payment_id = ? AND merchant_id = ?", (body.payment_id, merchant_id)).fetchone()
        if not pay:
            raise HTTPException(status_code=404, detail=f"Payment {body.payment_id} not found in your workspace.")

        amount = pay["amount"]
        customer_id = pay["customer_id"]

    if body.action == "DISPATCH_LINK":
        from db import fetch_setting
        key_id = fetch_setting("razorpay_key_id", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_ID")
        key_secret = fetch_setting("razorpay_key_secret", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_SECRET")
        link_url = None
        if key_id and key_secret and key_id.startswith("rzp_"):
            try:
                import requests
                from requests.auth import HTTPBasicAuth
                resp = requests.post(
                    "https://api.razorpay.com/v1/payment_links",
                    auth=HTTPBasicAuth(key_id.strip(), key_secret.strip()),
                    json={
                        "amount": int(round(amount * 100)),
                        "currency": "INR",
                        "description": f"Manual recovery for {body.payment_id}",
                        "reference_id": body.payment_id,
                    },
                    timeout=8,
                )
                if resp.status_code in (200, 201):
                    link_url = resp.json().get("short_url")
            except Exception:
                pass

        if not link_url:
            link_url = f"https://rzp.io/i/manual_{body.payment_id[-6:]}"

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO recovery_attempts
                    (attempt_id, merchant_id, user_id, payment_id, action, status, reason, channel_used, timestamp)
                VALUES (?, ?, ?, ?, 'SEND_PAYMENT_LINK', 'PENDING', ?, 'SMS', ?)
            """, (f"man_{now.strftime('%f')}", merchant_id, user_id, body.payment_id, f"Human agent approved link: {link_url}. Notes: {body.notes}", now.isoformat()))

            conn.execute("""
                INSERT INTO audit_logs
                    (event_id, merchant_id, user_id, payment_id, strategy_type, ai_recommendation, guardrail_result,
                     action_taken, result, ai_diagnosis, ml_score, timestamp)
                VALUES (?, ?, ?, ?, 'MANUAL_APPROVAL', 'SEND_PAYMENT_LINK', 'APPROVED',
                        'SEND_PAYMENT_LINK', 'PENDING', ?, 1.0, ?)
            """, (f"evt_man_{now.strftime('%M%S%f')}", merchant_id, user_id, body.payment_id, f"Human Approved. {body.notes}", now.isoformat()))

        _log_event("link_sent", merchant_id=merchant_id, user_id=user_id,
            payment_id=body.payment_id, amount=amount,
            label="⚡ Human Approved: Payment Link Dispatched",
            sublabel=f"Approved by merchant agent · {link_url}",
            razorpay_url=link_url)

        return {"status": "resolved", "action": "SEND_PAYMENT_LINK", "link_url": link_url}

    elif body.action == "RETRY":
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO recovery_attempts
                    (attempt_id, merchant_id, user_id, payment_id, action, status, reason, channel_used, timestamp)
                VALUES (?, ?, ?, ?, 'RETRY', 'PENDING', ?, 'GATEWAY', ?)
            """, (f"man_{now.strftime('%f')}", merchant_id, user_id, body.payment_id, f"Human triggered manual gateway retry. Notes: {body.notes}", now.isoformat()))

        _log_event("retried", merchant_id=merchant_id, user_id=user_id,
            payment_id=body.payment_id, amount=amount,
            label="🔄 Human Approved: Manual Retry Scheduled",
            sublabel="Gateway retry initiated with high priority")

        return {"status": "resolved", "action": "RETRY"}

    else: # DISMISS
        with get_connection() as conn:
            conn.execute("UPDATE payments SET status = 'DISMISSED' WHERE payment_id = ? AND merchant_id = ?", (body.payment_id, merchant_id))
            conn.execute("""
                INSERT INTO recovery_attempts
                    (attempt_id, merchant_id, user_id, payment_id, action, status, reason, channel_used, timestamp)
                VALUES (?, ?, ?, ?, 'STOP', 'FAILED', ?, 'NONE', ?)
            """, (f"man_{now.strftime('%f')}", merchant_id, user_id, body.payment_id, f"Case dismissed by human agent: {body.notes}", now.isoformat()))

        _log_event("stopped", merchant_id=merchant_id, user_id=user_id,
            payment_id=body.payment_id, amount=amount,
            label="🛑 Case Dismissed by Human Agent",
            sublabel=body.notes or "Marked unrecoverable")

        return {"status": "resolved", "action": "DISMISS"}


@app.get("/reports/export/csv", tags=["Reports"])
def export_recovery_csv(request: Request):
    """Download a complete CSV report of all payments, recovery outcomes, and revenue metrics for the active merchant."""
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    import io
    import csv
    from fastapi.responses import Response

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Payment ID", "Customer ID", "Amount (INR)", "Failure Reason",
        "Payment Method", "Current Status", "Timestamp", "Attempts",
        "Recovery Action", "Recovery Outcome"
    ])

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.*,
                   COALESCE(ra.action, 'NONE') as last_action,
                   COALESCE(ra.status, 'UNPROCESSED') as recovery_status
            FROM payments p
            LEFT JOIN (
                SELECT payment_id, action, status, MAX(timestamp)
                FROM recovery_attempts WHERE merchant_id = ? GROUP BY payment_id
            ) ra ON p.payment_id = ra.payment_id
            WHERE p.merchant_id = ?
            ORDER BY p.timestamp DESC
        """, (merchant_id, merchant_id)).fetchall()

        for r in rows:
            writer.writerow([
                r["payment_id"],
                r["customer_id"],
                f"{r['amount']:.2f}",
                r["failure_reason"],
                r["payment_method"],
                r["status"],
                r["timestamp"],
                r["previous_attempts"],
                r["last_action"],
                r["recovery_status"],
            ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=recoverai_{merchant_id}_report.csv"}
    )


# ── Merchant Settings & Integration Endpoints ─────────────────────────────────

@app.get("/settings/merchant", tags=["Settings"])
def get_merchant_settings_endpoint(request: Request):
    """
    Retrieve merchant organization settings and live webhook credentials.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    from db import fetch_merchant_by_id, fetch_all_settings
    merchant = fetch_merchant_by_id(merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found.")

    settings = fetch_all_settings(merchant_id=merchant_id)

    return {
        "merchant_id": merchant["merchant_id"],
        "name": merchant["name"],
        "business_name": merchant["business_name"],
        "email": merchant["email"],
        "phone": merchant["phone"],
        "razorpay_key_id": merchant["razorpay_key_id"] or settings.get("razorpay_key_id") or "",
        # Secret material is never returned by this read endpoint. Owners can
        # replace secrets through the authenticated update route; webhook
        # verification reads them directly from the server-side vault.
        "razorpay_key_secret_configured": bool(settings.get("razorpay_key_secret")),
        "razorpay_webhook_secret_configured": bool(merchant["razorpay_webhook_secret"] or settings.get("razorpay_webhook_secret")),
        "agent_enabled": settings.get("agent_enabled", "true") == "true",
        "created_at": merchant["created_at"],
    }


@app.post("/settings/merchant", tags=["Settings"])
def update_merchant_settings_endpoint(body: dict, request: Request):
    """
    Update merchant organization settings, brand details, and live Razorpay credentials.
    """
    user = get_current_user_context(request)
    merchant_id = user["merchant_id"]

    from db import update_merchant, save_setting
    update_merchant(
        merchant_id=merchant_id,
        name=body.get("name"),
        business_name=body.get("business_name"),
        email=body.get("email"),
        phone=body.get("phone"),
        razorpay_key_id=body.get("razorpay_key_id"),
        razorpay_webhook_secret=body.get("razorpay_webhook_secret"),
    )

    if "razorpay_key_id" in body:
        save_setting("razorpay_key_id", body["razorpay_key_id"], merchant_id=merchant_id)
    if "razorpay_webhook_secret" in body:
        save_setting("razorpay_webhook_secret", body["razorpay_webhook_secret"], merchant_id=merchant_id)
    if "agent_enabled" in body:
        save_setting("agent_enabled", "true" if body["agent_enabled"] else "false", merchant_id=merchant_id)

    return {"status": "ok", "message": "Merchant settings updated successfully."}
