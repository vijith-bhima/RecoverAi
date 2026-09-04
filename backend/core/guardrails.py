"""
core/guardrails.py — Deterministic safety rules and bounded autonomy for RecoverAI 2.0.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES (in evaluation order — first match wins)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

R1 — ALREADY_SUCCESSFUL
   If payment status is already SUCCESS, no action is needed.
   → BLOCKED, action overridden to STOP

R2 — AMOUNT_LIMIT
   Amount > MAX_AUTONOMOUS_AMOUNT (default ₹10,000) and action is NOT
   already ESCALATE_TO_HUMAN or STOP.
   → BLOCKED, action overridden to ESCALATE_TO_HUMAN

R3 — CARD_EXPIRED_NO_RETRY
   If failure_reason is CARD_EXPIRED and agent recommends RETRY.
   → BLOCKED, action overridden to SEND_PAYMENT_LINK (must provide alternate payment methods)

R4 — MAX_RETRIES (Bounded Autonomy)
   previous_attempts >= MAX_RETRY_ATTEMPTS (default 2) and agent recommended RETRY.
   → BLOCKED, action overridden to ESCALATE_TO_HUMAN
   Reason: "RecoverAI stopped automatically because the recovery limit was reached."

R5 — COOLDOWN
   Last recovery attempt was within RETRY_COOLDOWN_HOURS (default 6h)
   and agent recommended RETRY.
   → BLOCKED, action overridden to WAIT

R6 — CONTACT_LIMIT
   Total contact attempts (all actions, not just retries) >=
   MAX_CONTACT_ATTEMPTS (default 2).
   → BLOCKED, action overridden to STOP

APPROVED — no rule triggered, agent's recommendation stands.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from logging_config import get_logger
from models.schemas import (
    AgentDecision,
    AttemptStatus,
    ChannelPreference,
    EventType,
    FailureReason,
    GuardrailOutcome,
    GuardrailResult,
    Payment,
    PaymentStatus,
    RecoveryAction,
    RecoveryAttempt,
)

logger = get_logger(__name__)

# ── Limits (read from env, with safe defaults) ─────────────────────────────────

def _get_limit(key: str, default: int | float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        logger.warning(
            "guardrails.bad_env_value",
            extra={"key": key, "default": default},
        )
        return float(default)


MAX_AUTONOMOUS_AMOUNT: float = _get_limit("MAX_AUTONOMOUS_AMOUNT", 10_000)
MAX_RETRY_ATTEMPTS:    int   = int(_get_limit("MAX_RETRY_ATTEMPTS", 2))
RETRY_COOLDOWN_HOURS:  float = _get_limit("RETRY_COOLDOWN_HOURS", 6)
MAX_CONTACT_ATTEMPTS:  int   = int(_get_limit("MAX_CONTACT_ATTEMPTS", 2))


# ── Core function ──────────────────────────────────────────────────────────────

def check_guardrails(
    payment:        Payment,
    agent_decision: AgentDecision,
    history:        list[RecoveryAttempt],
    *,
    now:            Optional[datetime] = None,
) -> GuardrailResult:
    """
    Evaluate deterministic safety rules against the agent's recommendation.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not history:
        try:
            from db import fetch_recent_recovery_attempts
            rows = fetch_recent_recovery_attempts(payment.payment_id)
            if rows:
                history = [
                    RecoveryAttempt(
                        attempt_id=r["attempt_id"],
                        payment_id=r["payment_id"],
                        action=RecoveryAction(r["action"]),
                        status=AttemptStatus(r["status"]),
                        reason=r["reason"] or "",
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                        channel_used=ChannelPreference(r["channel_used"]) if r["channel_used"] else ChannelPreference.SMS,
                    )
                    for r in rows
                ]
        except Exception:
            pass

    if history is None:
        history = []

    recommended = agent_decision.recommended_action

    # ── R1: Already successful ─────────────────────────────────────────────────
    if payment.status == PaymentStatus.SUCCESS:
        return _block(
            payment_id=payment.payment_id,
            rule="R1_ALREADY_SUCCESSFUL",
            reason="Payment is already in SUCCESS state — no recovery action needed.",
            final_action=RecoveryAction.STOP,
        )

    # ── R2: Amount limit ───────────────────────────────────────────────────────
    is_cart_reminder = (
        payment.event_type == EventType.CHECKOUT_ABANDONED
        or payment.failure_reason == FailureReason.CHECKOUT_ABANDONED
    ) and recommended == RecoveryAction.SEND_PAYMENT_LINK

    effective_limit = 25_000.0 if is_cart_reminder else MAX_AUTONOMOUS_AMOUNT

    if (
        payment.amount > effective_limit
        and recommended not in (RecoveryAction.ESCALATE_TO_HUMAN, RecoveryAction.STOP)
    ):
        return _block(
            payment_id=payment.payment_id,
            rule="R2_AMOUNT_LIMIT",
            reason=(
                f"Payment amount ₹{payment.amount:,.2f} exceeds autonomous limit "
                f"₹{effective_limit:,.0f}. Overriding '{recommended.value}' "
                f"→ ESCALATE_TO_HUMAN for human review."
            ),
            final_action=RecoveryAction.ESCALATE_TO_HUMAN,
        )

    # ── R3: Card Expired — No Retry Allowed ───────────────────────────────────
    if (
        payment.failure_reason == FailureReason.CARD_EXPIRED
        and recommended == RecoveryAction.RETRY
    ):
        return _block(
            payment_id=payment.payment_id,
            rule="R3_CARD_EXPIRED_NO_RETRY",
            reason=(
                "Card is expired. Automated retries on expired cards are blocked to prevent card network penalty. "
                "Overriding to SEND_PAYMENT_LINK for alternate payment methods."
            ),
            final_action=RecoveryAction.SEND_PAYMENT_LINK,
        )

    # ── R4: Max retry attempts (Bounded Autonomy) ──────────────────────────────
    if (
        recommended == RecoveryAction.RETRY
        and payment.previous_attempts >= MAX_RETRY_ATTEMPTS
    ):
        return _block(
            payment_id=payment.payment_id,
            rule="R4_MAX_RETRIES",
            reason=(
                f"RecoverAI stopped automatically because the recovery limit was reached "
                f"({payment.previous_attempts}/{MAX_RETRY_ATTEMPTS} attempts). Escalating to human."
            ),
            final_action=RecoveryAction.ESCALATE_TO_HUMAN,
        )

    # ── R5: Cooldown ───────────────────────────────────────────────────────────
    if recommended == RecoveryAction.RETRY and history:
        most_recent = max(history, key=lambda a: a.timestamp)
        last_ts = most_recent.timestamp
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        elapsed = now - last_ts
        cooldown = timedelta(hours=RETRY_COOLDOWN_HOURS)
        if elapsed < cooldown:
            hours_remaining = (cooldown - elapsed).total_seconds() / 3600
            return _block(
                payment_id=payment.payment_id,
                rule="R5_COOLDOWN",
                reason=(
                    f"Last attempt was {elapsed.total_seconds() / 3600:.1f}h ago; "
                    f"cooldown requires {RETRY_COOLDOWN_HOURS}h between retries. "
                    f"({hours_remaining:.1f}h remaining). Setting to WAIT."
                ),
                final_action=RecoveryAction.WAIT,
            )

    # ── R6: Contact limit ──────────────────────────────────────────────────────
    contact_actions = {
        RecoveryAction.RETRY,
        RecoveryAction.SEND_PAYMENT_LINK,
        RecoveryAction.ESCALATE_TO_HUMAN,
    }
    contact_count = sum(1 for a in history if a.action in contact_actions)
    if contact_count >= MAX_CONTACT_ATTEMPTS:
        return _block(
            payment_id=payment.payment_id,
            rule="R6_CONTACT_LIMIT",
            reason=(
                f"Customer has been contacted {contact_count} time(s) already, "
                f"reaching the limit of {MAX_CONTACT_ATTEMPTS}. Stopping to prevent "
                "customer friction."
            ),
            final_action=RecoveryAction.STOP,
        )

    # ── R7: Fraud / Suspicious activity ───────────────────────────────────────
    reason_str = str(payment.failure_reason.value if hasattr(payment.failure_reason, 'value') else payment.failure_reason).upper()
    if any(k in reason_str for k in ("FRAUD", "STOLEN", "SUSPICIOUS", "LOST_CARD", "BLOCKED_CARD")):
        return _block(
            payment_id=payment.payment_id,
            rule="R7_FRAUD_SUSPECTED",
            reason=(
                f"Suspicious activity or fraud indicator detected ({reason_str}). "
                "Autonomous recovery is prohibited by security policy. Case escalated to human review."
            ),
            final_action=RecoveryAction.ESCALATE_TO_HUMAN,
        )

    # ── All rules passed → APPROVED ────────────────────────────────────────────
    result = GuardrailResult(
        payment_id=payment.payment_id,
        result=GuardrailOutcome.APPROVED,
        reason="All guardrail checks passed.",
        final_action=recommended,
        rule_triggered=None,
    )

    logger.info(
        "guardrails.approved",
        extra={
            "payment_id":   payment.payment_id,
            "final_action": recommended.value,
            "amount":       payment.amount,
        },
    )
    return result


# ── Internal helper ────────────────────────────────────────────────────────────

def _block(
    payment_id:   str,
    rule:         str,
    reason:       str,
    final_action: RecoveryAction,
) -> GuardrailResult:
    result = GuardrailResult(
        payment_id=payment_id,
        result=GuardrailOutcome.BLOCKED,
        reason=reason,
        final_action=final_action,
        rule_triggered=rule,
    )
    logger.warning(
        "guardrails.blocked",
        extra={
            "payment_id":    payment_id,
            "rule":          rule,
            "final_action":  final_action.value,
        },
    )
    return result
