"""
core/diagnosis.py — Failure diagnosis, recovery scoring, and priority tiering.

What this module does:
1. Diagnoses failure modes (transient bank/network blips, auth issues, insufficient funds, expired cards, abandoned carts)
2. Evaluates Customer Context: past payment success rate, lifetime value (LTV), total transactions
3. Computes Recovery Probability (via ML Random Forest or Explainable Heuristic)
4. Calculates Expected Recovery Value (Amount × Probability)
5. Assigns Revenue Priority Tier (HIGH, MEDIUM, LOW) for prioritized recovery routing
"""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logging_config import get_logger
from models.schemas import Customer, FailureReason, Payment, PriorityTier, RecoveryScore

logger = get_logger(__name__)

# ── Per-reason base configuration ─────────────────────────────────────────────

_REASON_CONFIG: dict[FailureReason, dict] = {
    FailureReason.BANK_SERVER_DOWN: {
        "is_temporary":   True,
        "is_recoverable": True,
        "base_prob":      0.85,
        "notes":          "Bank server was temporarily unavailable — not a customer issue.",
    },
    FailureReason.NETWORK_TIMEOUT: {
        "is_temporary":   True,
        "is_recoverable": True,
        "base_prob":      0.80,
        "notes":          "Network glitch — highly likely to succeed on retry or via payment link.",
    },
    FailureReason.TEMPORARY_GATEWAY_ERROR: {
        "is_temporary":   True,
        "is_recoverable": True,
        "base_prob":      0.82,
        "notes":          "Payment gateway experienced a transient latency/error.",
    },
    FailureReason.INVALID_OTP: {
        "is_temporary":   True,
        "is_recoverable": True,
        "base_prob":      0.55,
        "notes":          "Customer may have entered wrong OTP; recovery depends on engagement.",
    },
    FailureReason.INSUFFICIENT_FUNDS: {
        "is_temporary":   False,
        "is_recoverable": True,
        "base_prob":      0.40,
        "notes":          "Funds unavailable at time of payment; link recovery possible for loyal customers.",
    },
    FailureReason.CARD_EXPIRED: {
        "is_temporary":   False,
        "is_recoverable": True,
        "base_prob":      0.22,
        "notes":          "Card is expired — retry useless; only a payment-link with method choice can recover.",
    },    FailureReason.INTERNATIONAL_CARD_UNSUPPORTED: {
        "is_temporary":   False,
        "is_recoverable": True,
        "base_prob":      0.70,
        "notes":          "Razorpay already offered local payment methods; monitor that fallback before contacting the customer.",
    },
    FailureReason.CHECKOUT_ABANDONED: {
        "is_temporary":   False,
        "is_recoverable": True,
        "base_prob":      0.65,
        "notes":          "Customer dropped off during checkout; gentle reminder link can recover conversion.",
    },

    FailureReason.SUBSCRIPTION_RETRY_ACTIVE: {
        "is_temporary": False, "is_recoverable": True, "base_prob": 0.72,
        "notes": "Razorpay native subscription retry is active; monitor without customer outreach.",
    },
    FailureReason.SUBSCRIPTION_HALTED: {
        "is_temporary": False, "is_recoverable": True, "base_prob": 0.58,
        "notes": "Native subscription retries are exhausted; offer a consent-based recovery choice.",
    },
    FailureReason.INVOICE_OVERDUE: {
        "is_temporary": False, "is_recoverable": True, "base_prob": 0.62,
        "notes": "Invoice is overdue; a promise-to-pay commitment is preferable to repeated link reminders.",
    },
}
# ── Adjustment weights ─────────────────────────────────────────────────────────

LOYALTY_WEIGHT    = 0.20   # bonus for customers with high success rate
RETRY_PENALTY     = 0.10   # per previous attempt beyond 0
LARGE_AMT_PENALTY = 0.08   # applied when amount > ₹10,000
NEW_CUST_PENALTY  = 0.08   # applied when customer has < 3 total payments


# ── ML Model Loader ────────────────────────────────────────────────────────────

def _load_ml_model():
    """Attempt to load the trained Random Forest model and encoder metadata."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None, None

    model_path = Path(__file__).resolve().parent.parent / "models" / "recovery_model.pkl"
    encoder_path = Path(__file__).resolve().parent.parent / "models" / "encoder_metadata.pkl"

    if model_path.exists() and encoder_path.exists():
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            with open(encoder_path, "rb") as f:
                encoder_meta = pickle.load(f)
            return model, encoder_meta
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            return None, None
    return None, None


_ML_MODEL, _ENCODER_META = _load_ml_model()


# ── Main scoring function ──────────────────────────────────────────────────────

def score_recovery(payment: Payment, customer: Customer) -> RecoveryScore:
    """
    Diagnose a failed payment or abandoned checkout, evaluate customer context,
    and estimate recovery probability, expected revenue value, and priority tier.
    """
    config = _REASON_CONFIG.get(
        payment.failure_reason,
        {
            "is_temporary":   False,
            "is_recoverable": True,
            "base_prob":      0.50,
            "notes":          "Unspecified failure mode.",
        },
    )

    # Check if ML model is active and failure_reason is within standard RF classes
    is_rf_compatible = payment.failure_reason in (
        FailureReason.BANK_SERVER_DOWN,
        FailureReason.NETWORK_TIMEOUT,
        FailureReason.INVALID_OTP,
        FailureReason.INSUFFICIENT_FUNDS,
        FailureReason.CARD_EXPIRED,
    )

    if _ML_MODEL is not None and _ENCODER_META is not None and is_rf_compatible:
        import pandas as pd

        df = pd.DataFrame([{
            'amount': payment.amount,
            'previous_attempts': payment.previous_attempts,
            'payment_method': payment.payment_method.value,
            'failure_reason': payment.failure_reason.value,
            'total_payments': customer.total_payments,
            'successful_payments': customer.successful_payments,
        }])

        df['success_rate'] = df['successful_payments'] / df['total_payments'].replace(0, 1)

        categorical_cols = ['payment_method', 'failure_reason']
        numerical_cols = ['amount', 'previous_attempts', 'total_payments', 'success_rate']

        df_encoded = pd.get_dummies(df[numerical_cols + categorical_cols], columns=categorical_cols)

        expected_cols = _ENCODER_META['feature_columns']
        for col in expected_cols:
            if col not in df_encoded.columns:
                df_encoded[col] = 0
        df_encoded = df_encoded[expected_cols]

        prob = _ML_MODEL.predict_proba(df_encoded)[0][1]
        p = round(float(prob), 4)

        # LTV booster for VIP customers
        if customer.lifetime_value > 30000:
            p = min(0.95, p + 0.05)

        notes = f"ML Model (RF) Prediction | Base: {config['notes']}"
    else:
        # Transparent Heuristic with Customer LTV Awareness
        p: float = config["base_prob"]
        notes_list: list[str] = [config["notes"]]

        # 1. Customer Loyalty & History
        if customer.total_payments >= 3:
            loyalty_bonus = (customer.success_rate - 0.5) * LOYALTY_WEIGHT
            p += loyalty_bonus
            direction = "+" if loyalty_bonus >= 0 else ""
            notes_list.append(
                f"Customer success rate {customer.success_rate:.0%} "
                f"→ loyalty adj {direction}{loyalty_bonus:+.3f}"
            )
        else:
            p -= NEW_CUST_PENALTY
            notes_list.append(
                f"New customer ({customer.total_payments} total payments) "
                f"→ penalty -{NEW_CUST_PENALTY}"
            )

        # 2. Customer Lifetime Value (LTV) Boost
        if customer.lifetime_value >= 50000:
            p += 0.08
            notes_list.append(f"High LTV VIP (₹{customer.lifetime_value:,.0f}) → boost +0.08")
        elif customer.lifetime_value >= 20000:
            p += 0.04
            notes_list.append(f"Valued customer LTV (₹{customer.lifetime_value:,.0f}) → boost +0.04")

        # 3. Previous Attempts Penalty
        if payment.previous_attempts > 0:
            retry_pen = payment.previous_attempts * RETRY_PENALTY
            p -= retry_pen
            notes_list.append(
                f"{payment.previous_attempts} prior attempt(s) "
                f"→ penalty -{retry_pen:.2f}"
            )

        # 4. Large-amount penalty
        if payment.amount > 10000:
            p -= LARGE_AMT_PENALTY
            notes_list.append(
                f"Large amount ₹{payment.amount:,.2f} > ₹10,000 "
                f"→ penalty -{LARGE_AMT_PENALTY}"
            )

        notes = " | ".join(notes_list)

    # Clamp to [0.05, 0.95]
    p = max(0.05, min(0.95, round(p, 4)))

    # Compute Expected Recovery Value
    expected_value = round(payment.amount * p, 2)

    # Assign Priority Tier
    if expected_value >= 4000 or (payment.amount >= 3000 and p >= 0.75):
        priority = PriorityTier.HIGH
    elif expected_value >= 1200 or p >= 0.45:
        priority = PriorityTier.MEDIUM
    else:
        priority = PriorityTier.LOW

    score = RecoveryScore(
        payment_id=payment.payment_id,
        is_temporary=config["is_temporary"],
        is_recoverable=config["is_recoverable"],
        recovery_probability=p,
        expected_recovery_value=expected_value,
        priority_tier=priority,
        diagnosis_notes=notes,
    )

    logger.info(
        "diagnosis.scored",
        extra={
            "payment_id":            payment.payment_id,
            "failure_reason":        payment.failure_reason.value,
            "recovery_probability":  score.recovery_probability,
            "expected_value":        score.expected_recovery_value,
            "priority_tier":         score.priority_tier.value,
            "is_temporary":          score.is_temporary,
            "amount":                payment.amount,
            "customer_ltv":          customer.lifetime_value,
        },
    )

    return score
