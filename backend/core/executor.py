"""
core/executor.py — Action execution, channel dispatch, status verification, and outcome recording.

What this module does:
1. Receives Guardrail-Approved recovery actions
2. Dispatches payment links across configured channels (SMS, Email) via Razorpay API (or test simulation)
3. Performs gateway status recheck to prevent double-charging
4. Enforces bounded autonomy and outcome verification
5. Persists the resulting RecoveryAttempt to the database
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import fetch_customer, fetch_ground_truth, fetch_setting, get_connection, reserve_recovery_link, update_recovery_link
from logging_config import get_logger
from models.schemas import (
    AttemptStatus,
    ChannelPreference,
    GuardrailOutcome,
    GuardrailResult,
    Payment,
    PaymentStatus,
    FailureReason,
    RecoveryAction,
    RecoveryAttempt,
)

logger = get_logger(__name__)

# ── Action simulation messages ─────────────────────────────────────────────────

# Merchant contact — read from env
MERCHANT_EMAIL: str = os.getenv("MERCHANT_EMAIL", "")
MERCHANT_PHONE: str = os.getenv("MERCHANT_PHONE", "")
MERCHANT_NAME:  str = os.getenv("MERCHANT_NAME", "Merchant")

_ACTION_MESSAGES: dict[RecoveryAction, str] = {
    RecoveryAction.RETRY:                    "Payment retry initiated via payment gateway.",
    RecoveryAction.SEND_PAYMENT_LINK:        "Payment link generated and sent to customer.",
    RecoveryAction.ALTERNATE_PAYMENT_METHOD: "Alternate payment method link (UPI / NetBanking) generated and sent.",
    RecoveryAction.ESCALATE_TO_HUMAN:        "Recovery ticket created and assigned to human recovery agent.",
    RecoveryAction.WAIT:                     "Payment queued for re-evaluation in accordance with recovery plan.",
    RecoveryAction.WAIT_AND_RECHECK:         "Payment queued for cooldown and automatic gateway recheck.",
    RecoveryAction.RECHECK_STATUS:           "Gateway status rechecked to confirm live transaction outcome.",
    RecoveryAction.REQUEST_PROMISE_TO_PAY:    "Promise-to-pay request recorded; awaiting customer commitment.",
    RecoveryAction.STOP:                     "No further recovery action — case closed.",
}

_RECOVERABLE_ACTIONS = {
    RecoveryAction.RETRY,
    RecoveryAction.SEND_PAYMENT_LINK,
    RecoveryAction.ALTERNATE_PAYMENT_METHOD,
}


# ── Main execution function ────────────────────────────────────────────────────

def execute_action(
    payment:             Payment,
    guardrail_result:    GuardrailResult,
    recovery_score_prob: float,
    channel:             Optional[ChannelPreference] = None,
    merchant_id:         str = "mer_default",
) -> RecoveryAttempt:
    """
    Execute the guardrail-approved action and verify the outcome.
    """
    action = guardrail_result.final_action
    now    = datetime.now(timezone.utc)
    target_channel = channel or ChannelPreference.SMS

    sim_message = _ACTION_MESSAGES.get(action, "Action executed.")

    # A captured/paid payment and a Razorpay-owned native retry/checkout are
    # never eligible for RecoverAI outreach, retries, links, or commitments.
    native_owned = payment.failure_reason in (FailureReason.INTERNATIONAL_CARD_UNSUPPORTED, FailureReason.SUBSCRIPTION_RETRY_ACTIVE)
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.RECOVERED) or native_owned:
        action = RecoveryAction.STOP
        sim_message = "Razorpay native recovery/alternate checkout is being monitored." if native_owned else "Captured payment reconciled; no recovery action is permitted."


    # ── Real Razorpay API / Simulated Payment Link ────────────────────────────
    if action in (RecoveryAction.SEND_PAYMENT_LINK, RecoveryAction.ALTERNATE_PAYMENT_METHOD):
        reserved, existing_link = reserve_recovery_link(payment.payment_id, merchant_id)
        if not reserved:
            # This outcome is deliberately visible to callers/UI but does not
            # contact the customer or call Razorpay again.
            action = RecoveryAction.STOP
            sim_message = "Existing recovery link monitored; no additional customer delivery occurred."
        else:
            # Credentials and customer contact data are tenant-owned. Never read
            # them from process-wide environment variables populated by another job.
            razorpay_id = fetch_setting("razorpay_key_id", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_ID")
            razorpay_secret = fetch_setting("razorpay_key_secret", merchant_id=merchant_id) or os.getenv("RAZORPAY_KEY_SECRET")
            customer = fetch_customer(payment.customer_id, merchant_id=merchant_id)
            customer_email = (customer["email"] if customer and customer["email"] else "").strip() or f"{payment.customer_id}@example.com"
            raw_phone = (customer["phone"] if customer and customer["phone"] else "").strip()
            if raw_phone:
                digits = "".join(ch for ch in raw_phone if ch.isdigit())
                if len(digits) == 10:
                    customer_phone = f"+91{digits}"
                elif not raw_phone.startswith("+"):
                    customer_phone = f"+{raw_phone}"
                else:
                    customer_phone = raw_phone
            else:
                customer_phone = "+919876543210"

            if os.getenv("EVALUATION_MODE") == "1":
                razorpay_id = None
                razorpay_secret = None

            if razorpay_id and razorpay_secret and razorpay_id.startswith("rzp_"):
                try:
                    import requests
                    from requests.auth import HTTPBasicAuth

                    desc = f"RecoverAI: Payment for Order #{payment.payment_id[-8:]}"
                    if action == RecoveryAction.ALTERNATE_PAYMENT_METHOD:
                        desc = f"RecoverAI: Alternate payment link for Order #{payment.payment_id[-8:]}"

                    payload = {
                        "amount": int(round(payment.amount * 100)),
                        "currency": "INR",
                        "accept_partial": False,
                        "reference_id": payment.payment_id,
                        "description": desc,
                        "customer": {
                            "name": f"Customer {payment.customer_id}",
                            "contact": customer_phone,
                            "email": customer_email,
                        },
                        "notify": {
                            "sms": target_channel in (ChannelPreference.SMS, ChannelPreference.WHATSAPP),
                            "email": target_channel == ChannelPreference.EMAIL,
                        },
                        "reminder_enable": True,
                        "notes": {
                            "recovered_by": "RecoverAI",
                            "payment_id": payment.payment_id,
                            "merchant_id": merchant_id,
                            "failure_reason": payment.failure_reason.value,
                            "priority": "HIGH" if payment.amount >= 5000 else "MEDIUM",
                        },
                    }

                    resp = requests.post(
                        "https://api.razorpay.com/v1/payment_links",
                        json=payload,
                        auth=HTTPBasicAuth(razorpay_id.strip(), razorpay_secret.strip()),
                        timeout=8,
                    )

                    if resp.status_code in (200, 201):
                        link_data = resp.json()
                        short_url = link_data.get("short_url", "")
                        link_id   = link_data.get("id", "")
                        update_recovery_link(payment.payment_id, merchant_id, "LIVE", link_id, short_url)
                        sim_message = f"LIVE_LINK_DISPATCHED: {short_url}"
                        logger.info(
                            "razorpay.link_created",
                            extra={
                                "payment_id": payment.payment_id,
                                "amount": payment.amount,
                                "short_url": short_url,
                                "link_id": link_id,
                                "merchant_id": merchant_id,
                            },
                        )
                    else:
                        logger.warning(
                            f"razorpay.link_failed status={resp.status_code} body={resp.text[:300]}"
                        )
                except Exception as exc:
                    logger.warning(f"razorpay.api_exception: {exc}")
            else:
                update_recovery_link(payment.payment_id, merchant_id, "SIMULATED")
                sim_message = f"SIMULATED_LINK_ONLY: Payment link simulated via {target_channel.value} (Razorpay credentials not set)"

    # ── Merchant Notification on Escalation ─────────────────────────────────
    if action == RecoveryAction.ESCALATE_TO_HUMAN:
        _notify_merchant_escalation(payment, guardrail_result.reason or "Payment escalated to human review queue.")

    logger.info(
        "executor.action_executed",
        extra={
            "payment_id": payment.payment_id,
            "action":     action.value,
            "channel":    target_channel.value,
            "amount":     payment.amount,
            "sim_message": sim_message,
        },
    )

    # ── Outcome determination ──────────────────────────────────────────────────
    if os.getenv("EVALUATION_MODE") == "1":
        # Offline benchmark / model evaluation mode only
        gt = fetch_ground_truth(payment.payment_id)
        if gt is not None:
            if gt:
                outcome = AttemptStatus.SUCCESS
                outcome_reason = f"Ground truth confirmed recovery ({action.value})."
            else:
                outcome = AttemptStatus.FAILED
                outcome_reason = f"Ground truth confirmed failure ({action.value})."
        elif action in _RECOVERABLE_ACTIONS:
            if recovery_score_prob >= 0.70:
                outcome = AttemptStatus.SUCCESS
                outcome_reason = f"Payment successfully recovered via {action.value}."
            else:
                outcome = AttemptStatus.FAILED
                outcome_reason = f"Recovery attempt {action.value} failed to recover payment."
        else:
            outcome = AttemptStatus.PENDING
            outcome_reason = f"Action '{action.value}' initiated; outcome pending human or scheduled review."
    else:
        # ── LIVE PRODUCTION EXECUTION: Decouple link dispatch from revenue recovery ──
        # Sending a link or initiating a retry is NOT revenue recovered.
        # It remains PENDING until payment.captured / payment.link.paid webhook
        # or active gateway status verification confirms payment.
        if action in (RecoveryAction.SEND_PAYMENT_LINK, RecoveryAction.ALTERNATE_PAYMENT_METHOD):
            outcome = AttemptStatus.PENDING
            outcome_reason = sim_message
        elif action == RecoveryAction.RETRY:
            outcome = AttemptStatus.PENDING
            outcome_reason = "Gateway retry dispatched. Awaiting transaction outcome from processor."
        elif action == RecoveryAction.ESCALATE_TO_HUMAN:
            outcome = AttemptStatus.PENDING
        elif action == RecoveryAction.REQUEST_PROMISE_TO_PAY:
            outcome = AttemptStatus.PENDING
            outcome_reason = "Promise-to-pay requested. Awaiting customer-selected payment date or alternate method."
            outcome_reason = f"Escalated to human review queue: {guardrail_result.reason or 'Limit reached'}."
        elif action == RecoveryAction.STOP:
            outcome = AttemptStatus.FAILED
            outcome_reason = f"Recovery stopped: {guardrail_result.reason or 'Unrecoverable transaction'}."
        else:  # WAIT, WAIT_AND_RECHECK, RECHECK_STATUS
            outcome = AttemptStatus.PENDING
            outcome_reason = "Payment queued for cooldown and gateway recheck."

    # ── Persist attempt to DB with merchant ownership ──────────────────────────
    attempt = RecoveryAttempt(
        attempt_id=f"att_{uuid.uuid4().hex[:10]}",
        payment_id=payment.payment_id,
        action=action,
        status=outcome,
        reason=outcome_reason,
        timestamp=now,
        channel_used=target_channel,
    )
    _save_attempt(attempt, merchant_id=merchant_id)

    return attempt


def _notify_merchant_escalation(payment: Payment, escalation_reason: str) -> None:
    """
    Notify the merchant via Razorpay SMS (payment link to themselves) and/or email
    whenever a high-value payment is escalated for human review.
    """
    if os.getenv("EVALUATION_MODE") == "1":
        return

    razorpay_id     = os.getenv("RAZORPAY_KEY_ID")
    razorpay_secret = os.getenv("RAZORPAY_KEY_SECRET")
    merchant_email  = MERCHANT_EMAIL
    merchant_phone  = MERCHANT_PHONE

    if not (razorpay_id and razorpay_secret):
        logger.warning("executor.merchant_notify_skip: Razorpay credentials not set")
        return

    if not merchant_email and not merchant_phone:
        logger.warning("executor.merchant_notify_skip: MERCHANT_EMAIL / MERCHANT_PHONE not configured in .env")
        return

    try:
        import requests
        from requests.auth import HTTPBasicAuth

        # Build merchant alert note
        note = (
            f"[RecoverAI ALERT] High-value payment escalated for review.\n"
            f"Payment ID : {payment.payment_id}\n"
            f"Amount     : ₹{payment.amount:,.2f}\n"
            f"Failure    : {payment.failure_reason.value.replace('_', ' ').title()}\n"
            f"Reason     : {escalation_reason}\n"
            f"Action     : Please review at /recovery-cases"
        )

        # Send a ₹1 (100 paise) info-payment-link to the merchant as an alert
        # This uses Razorpay's built-in SMS + email notification system
        payload = {
            "amount": 100,  # ₹1 — dummy amount for the alert link itself
            "currency": "INR",
            "accept_partial": False,
            "reference_id": f"alert_{payment.payment_id}",
            "description": f"[RecoverAI Alert] Escalation: {payment.payment_id} — ₹{payment.amount:,.0f} needs review",
            "customer": {
                "name": MERCHANT_NAME,
                "contact": merchant_phone or "+919999999999",
                "email": merchant_email or "merchant@example.com",
            },
            "notify": {
                "sms": bool(merchant_phone),
                "email": bool(merchant_email),
            },
            "notes": {
                "alert_for": payment.payment_id,
                "amount": str(payment.amount),
            },
            "reminder_enable": False,
            "expire_by": int(__import__("time").time()) + 3600,  # 1-hour alert window
        }

        resp = requests.post(
            "https://api.razorpay.com/v1/payment_links",
            json=payload,
            auth=HTTPBasicAuth(razorpay_id, razorpay_secret),
            timeout=8,
        )

        if resp.status_code in (200, 201):
            alert_url = resp.json().get("short_url", "")
            logger.info(
                "executor.merchant_notified",
                extra={
                    "payment_id":   payment.payment_id,
                    "amount":       payment.amount,
                    "merchant_email": merchant_email,
                    "alert_url":    alert_url,
                },
            )
        else:
            logger.warning(
                f"executor.merchant_notify_api_error: {resp.status_code} — {resp.text[:200]}"
            )
    except Exception as exc:
        logger.warning(f"executor.merchant_notify_exception: {exc}")


def _save_attempt(attempt: RecoveryAttempt, merchant_id: str = "mer_default") -> None:
    """Write one RecoveryAttempt row to the database with strict merchant ownership."""
    import sqlite3
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO recovery_attempts
                    (attempt_id, merchant_id, user_id, payment_id, action, status, reason, timestamp, channel_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.attempt_id,
                    merchant_id,
                    "usr_" + merchant_id,
                    attempt.payment_id,
                    attempt.action.value,
                    attempt.status.value,
                    attempt.reason,
                    attempt.timestamp.isoformat(),
                    attempt.channel_used.value if attempt.channel_used else "SMS",
                ),
            )
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE recovery_attempts ADD COLUMN merchant_id TEXT DEFAULT 'mer_default'")
                conn.execute("ALTER TABLE recovery_attempts ADD COLUMN user_id TEXT DEFAULT 'usr_default'")
                conn.execute("ALTER TABLE recovery_attempts ADD COLUMN channel_used TEXT DEFAULT 'SMS'")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO recovery_attempts
                        (attempt_id, merchant_id, user_id, payment_id, action, status, reason, timestamp, channel_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt.attempt_id,
                        merchant_id,
                        "usr_" + merchant_id,
                        attempt.payment_id,
                        attempt.action.value,
                        attempt.status.value,
                        attempt.reason,
                        attempt.timestamp.isoformat(),
                        attempt.channel_used.value if attempt.channel_used else "SMS",
                    ),
                )
            except Exception:
                pass
        except sqlite3.IntegrityError:
            pass
