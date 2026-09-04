"""Explainable eligibility and attribution for incremental revenue recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from models.schemas import Customer, FailureReason, Payment, RecoveryScore


NATIVE_RECOVERY_REASONS = {
    FailureReason.INTERNATIONAL_CARD_UNSUPPORTED,
    FailureReason.SUBSCRIPTION_RETRY_ACTIVE,
}


def native_recovery_active(payment: Payment) -> bool:
    """True when Razorpay already owns the next recovery action."""
    return payment.failure_reason in NATIVE_RECOVERY_REASONS


def recovery_eligibility(payment: Payment) -> tuple[bool, str]:
    """Return whether RecoverAI may contact a customer without duplication."""
    if native_recovery_active(payment):
        return False, "Razorpay native retry or alternate-payment checkout is active. Monitor only."
    if payment.failure_reason == FailureReason.SUBSCRIPTION_HALTED:
        return True, "Razorpay retries are exhausted; customer-directed recovery is now eligible."
    if payment.failure_reason == FailureReason.INVOICE_OVERDUE:
        return True, "Invoice is overdue; a consent-based promise-to-pay workflow is eligible."
    if payment.failure_reason == FailureReason.CHECKOUT_ABANDONED:
        return True, "Checkout was abandoned before a successful payment; one contextual recovery path is eligible."
    return True, "No active native recovery path is known; guardrails still apply."


def build_recovery_passport(
    payment: Payment,
    score: RecoveryScore,
    customer: Optional[Customer] = None,
    promise: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Small, UI-ready explanation of an agent's decision for one revenue-risk case."""
    eligible, eligibility_reason = recovery_eligibility(payment)
    return {
        "payment_id": payment.payment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recovery_type": payment.failure_reason.value,
        "amount": payment.amount,
        "customer_context": {
            "lifetime_value": customer.lifetime_value if customer else 0.0,
            "success_rate": round(customer.success_rate, 3) if customer else 0.0,
            "preferred_channel": customer.preferred_channel.value if customer else "SMS",
        },
        "prediction": {
            "recovery_probability": score.recovery_probability,
            "expected_recovery_value": score.expected_recovery_value,
            "priority": score.priority_tier.value,
        },
        "native_recovery_active": native_recovery_active(payment),
        "eligible_for_recoverai": eligible,
        "eligibility_reason": eligibility_reason,
        "attribution_rule": "Razorpay-native" if native_recovery_active(payment) else "RecoverAI-incremental only after an eligible RecoverAI intervention is verified",
        "promise_to_pay": promise,
        "safety": [
            "No duplicate payment link while native recovery is active",
            "No automatic charge",
            "Contact and amount guardrails enforced before outreach",
        ],
    }
