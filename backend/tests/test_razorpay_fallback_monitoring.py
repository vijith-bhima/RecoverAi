"""Regression tests for Razorpay-managed alternative payment fallbacks."""
from datetime import datetime, timezone

from core.playbook_router import route_playbook
from models.schemas import (
    ChannelPreference,
    Customer,
    FailureReason,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PriorityTier,
    RecoveryAction,
    StrategyType,
    RecoveryScore,
)


def test_international_card_fallback_is_monitored_without_a_duplicate_link():
    payment = Payment(
        payment_id="pay_international_fallback",
        customer_id="cust_fallback",
        amount=2500.0,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.INTERNATIONAL_CARD_UNSUPPORTED,
        payment_method=PaymentMethod.CREDIT_CARD,
        timestamp=datetime.now(timezone.utc),
    )
    customer = Customer(customer_id="cust_fallback", total_payments=1, successful_payments=0, failed_payments=1, preferred_channel=ChannelPreference.SMS)
    score = RecoveryScore(
        payment_id=payment.payment_id,
        failure_reason=payment.failure_reason,
        recovery_probability=0.7,
        expected_recovery_value=1750.0,
        priority_tier=PriorityTier.MEDIUM,
        is_temporary=False,
        is_recoverable=True,
        previous_attempts=0,
        amount=payment.amount,
        customer_success_rate=0.0,
        model_type="RULE_BASED",
    )

    route = route_playbook(payment, score, customer)

    assert route.strategy_type == StrategyType.RAZORPAY_FALLBACK_MONITORING
    assert route.recommended_action == RecoveryAction.WAIT_AND_RECHECK
    assert route.requires_wait is True
    assert all(step.action != RecoveryAction.SEND_PAYMENT_LINK for step in route.steps)