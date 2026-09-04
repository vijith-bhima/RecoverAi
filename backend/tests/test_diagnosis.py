import pytest
from datetime import datetime, timezone
from models.schemas import Payment, Customer, FailureReason, PaymentStatus, PaymentMethod
from core.diagnosis import score_recovery

NOW = datetime.now(timezone.utc)

def test_bank_server_down_is_temporary():
    p = Payment(
        payment_id="pay_1",
        customer_id="cust_1",
        amount=5000,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.BANK_SERVER_DOWN,
        payment_method=PaymentMethod.UPI,
        timestamp=NOW,
        previous_attempts=0
    )
    c = Customer(customer_id="cust_1", total_payments=10, successful_payments=10, failed_payments=0)
    score = score_recovery(p, c)
    assert score.is_temporary is True
    assert score.is_recoverable is True
    assert score.recovery_probability >= 0.70

def test_card_expired_is_permanent():
    p = Payment(
        payment_id="pay_2",
        customer_id="cust_1",
        amount=5000,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.CARD_EXPIRED,
        payment_method=PaymentMethod.DEBIT_CARD,
        timestamp=NOW,
        previous_attempts=0
    )
    c = Customer(customer_id="cust_1", total_payments=1, successful_payments=0, failed_payments=1)
    score = score_recovery(p, c)
    assert score.is_temporary is False
    assert score.recovery_probability < 0.50
