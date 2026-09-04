"""
tests/test_guardrails.py — pytest suite for the guardrail engine.

Run with: pytest tests/test_guardrails.py -v

The centerpiece is the demo-video scenario:
  - A ₹75,000 payment where the agent recommends RETRY
    → must be BLOCKED and overridden to ESCALATE_TO_HUMAN (R2)

Each test is named for the exact rule it exercises.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import (
    AgentDecision,
    AttemptStatus,
    FailureReason,
    GuardrailOutcome,
    Payment,
    PaymentMethod,
    PaymentStatus,
    RecoveryAction,
    RecoveryAttempt,
)
from core.guardrails import check_guardrails

# ── Shared fixtures ────────────────────────────────────────────────────────────

NOW = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)   # fixed clock for all tests


def _payment(
    *,
    amount: float = 2000.0,
    status: PaymentStatus = PaymentStatus.FAILED,
    failure_reason: FailureReason = FailureReason.BANK_SERVER_DOWN,
    previous_attempts: int = 0,
    payment_id: str = "test_pay_001",
) -> Payment:
    return Payment(
        payment_id=payment_id,
        customer_id="test_cust_001",
        amount=amount,
        status=status,
        failure_reason=failure_reason,
        payment_method=PaymentMethod.UPI,
        timestamp=NOW - timedelta(hours=12),
        previous_attempts=previous_attempts,
    )


def _decision(
    action: RecoveryAction = RecoveryAction.RETRY,
    payment_id: str = "test_pay_001",
) -> AgentDecision:
    return AgentDecision(
        payment_id=payment_id,
        diagnosis="test_diagnosis",
        recommended_action=action,
        reason="Test reason.",
        confidence=0.85,
    )


def _attempt(
    *,
    action: RecoveryAction = RecoveryAction.RETRY,
    hours_ago: float = 24.0,
    attempt_id: str = "att_001",
    payment_id: str = "test_pay_001",
) -> RecoveryAttempt:
    return RecoveryAttempt(
        attempt_id=attempt_id,
        payment_id=payment_id,
        action=action,
        status=AttemptStatus.FAILED,
        reason="Test attempt.",
        timestamp=NOW - timedelta(hours=hours_ago),
    )


# ── R1: Already successful ─────────────────────────────────────────────────────

class TestR1AlreadySuccessful:
    def test_already_successful_payment_is_blocked(self):
        # The Payment validator rejects status=SUCCESS (correct behaviour —
        # successful payments shouldn't enter the pipeline normally).
        # But R1 guards against exactly this edge case: a duplicate event
        # fired after recovery. We use model_construct() to bypass validation
        # and simulate that state reaching the guardrail.
        payment = Payment.model_construct(
            payment_id="test_pay_001",
            customer_id="test_cust_001",
            amount=2000.0,
            status=PaymentStatus.SUCCESS,
            failure_reason=FailureReason.BANK_SERVER_DOWN,
            payment_method=PaymentMethod.UPI,
            timestamp=NOW - timedelta(hours=12),
            previous_attempts=0,
        )
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R1_ALREADY_SUCCESSFUL"
        assert result.final_action   == RecoveryAction.STOP

    def test_failed_payment_not_blocked_by_r1(self):
        payment  = _payment(status=PaymentStatus.FAILED)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        # Should not be blocked by R1 (may be approved or blocked by another rule)
        assert result.rule_triggered != "R1_ALREADY_SUCCESSFUL"


# ── R2: Amount limit ───────────────────────────────────────────────────────────

class TestR2AmountLimit:
    def test_large_payment_retry_is_blocked_and_escalated(self):
        """
        ★ DEMO VIDEO CENTERPIECE ★
        ₹75,000 payment with agent-recommended RETRY
        → must be BLOCKED and force-escalated to ESCALATE_TO_HUMAN
        """
        payment  = _payment(amount=75_000.00)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R2_AMOUNT_LIMIT"
        assert result.final_action   == RecoveryAction.ESCALATE_TO_HUMAN

    def test_large_payment_send_link_is_also_blocked(self):
        """Any autonomous action on a large payment should be blocked."""
        payment  = _payment(amount=15_000.00)
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R2_AMOUNT_LIMIT"
        assert result.final_action   == RecoveryAction.ESCALATE_TO_HUMAN

    def test_large_payment_already_escalated_passes_r2(self):
        """If agent already recommended ESCALATE, R2 should not block it again."""
        payment  = _payment(amount=75_000.00)
        decision = _decision(RecoveryAction.ESCALATE_TO_HUMAN)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R2_AMOUNT_LIMIT"

    def test_large_payment_stop_passes_r2(self):
        """STOP action on a large payment should not trigger R2."""
        payment  = _payment(amount=20_000.00)
        decision = _decision(RecoveryAction.STOP)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R2_AMOUNT_LIMIT"

    def test_normal_payment_approved(self):
        """
        ★ DEMO VIDEO: the normal ₹2,000 case that should be APPROVED ★
        """
        payment  = _payment(amount=2_000.00)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result       == GuardrailOutcome.APPROVED
        assert result.final_action == RecoveryAction.RETRY

    def test_exactly_at_limit_is_approved(self):
        """₹10,000 exactly (not exceeding) should pass the amount check."""
        payment  = _payment(amount=10_000.00)
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R2_AMOUNT_LIMIT"


# ── R4: Max retries ────────────────────────────────────────────────────────────

class TestR4MaxRetries:
    def test_max_retries_reached_blocks_retry(self):
        payment  = _payment(previous_attempts=3)   # at the limit (max=3)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R4_MAX_RETRIES"
        assert result.final_action   == RecoveryAction.ESCALATE_TO_HUMAN

    def test_one_attempt_retry_not_blocked_by_r4(self):
        payment  = _payment(previous_attempts=2)   # below limit (max=3)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R4_MAX_RETRIES"

    def test_max_retries_does_not_block_send_payment_link(self):
        """R4 only blocks RETRY action, not other actions."""
        payment  = _payment(previous_attempts=5)
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R4_MAX_RETRIES"


# ── R5: Cooldown ───────────────────────────────────────────────────────────────

class TestR5Cooldown:
    def test_recent_attempt_blocks_retry(self):
        """Last attempt was 2h ago, cooldown is 6h → BLOCKED."""
        payment  = _payment()
        decision = _decision(RecoveryAction.RETRY)
        history  = [_attempt(hours_ago=2.0)]   # too recent

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R5_COOLDOWN"
        assert result.final_action   == RecoveryAction.WAIT

    def test_old_attempt_does_not_block(self):
        """Last attempt was 8h ago, cooldown is 6h → should NOT be blocked by R5."""
        payment  = _payment()
        decision = _decision(RecoveryAction.RETRY)
        history  = [_attempt(hours_ago=8.0)]   # past the cooldown window

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.rule_triggered != "R5_COOLDOWN"

    def test_cooldown_only_applies_to_retry(self):
        """Cooldown does not block SEND_PAYMENT_LINK even if last attempt was recent."""
        payment  = _payment()
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)
        history  = [_attempt(hours_ago=1.0)]

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.rule_triggered != "R5_COOLDOWN"

    def test_no_history_does_not_trigger_cooldown(self):
        """No previous attempts → cooldown doesn't apply."""
        payment  = _payment()
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered != "R5_COOLDOWN"


# ── R6: Contact limit ──────────────────────────────────────────────────────────

class TestR6ContactLimit:
    def test_contact_limit_reached_blocks_any_action(self):
        """Two prior contact attempts → R6 blocks and sets STOP."""
        payment  = _payment()
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)
        history  = [
            _attempt(action=RecoveryAction.RETRY,             hours_ago=25, attempt_id="att_1"),
            _attempt(action=RecoveryAction.SEND_PAYMENT_LINK, hours_ago=10, attempt_id="att_2"),
        ]

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.result         == GuardrailOutcome.BLOCKED
        assert result.rule_triggered == "R6_CONTACT_LIMIT"
        assert result.final_action   == RecoveryAction.STOP

    def test_one_contact_attempt_not_blocked(self):
        """One prior contact → still within limit of 2."""
        payment  = _payment()
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)
        history  = [
            _attempt(action=RecoveryAction.RETRY, hours_ago=25, attempt_id="att_1"),
        ]

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.result         == GuardrailOutcome.APPROVED

    def test_wait_and_stop_do_not_count_as_contacts(self):
        """WAIT and STOP are not 'contacts' — shouldn't count toward the limit."""
        payment  = _payment()
        decision = _decision(RecoveryAction.RETRY)
        history  = [
            _attempt(action=RecoveryAction.WAIT, hours_ago=8,  attempt_id="att_1"),
            _attempt(action=RecoveryAction.STOP, hours_ago=12, attempt_id="att_2"),
        ]

        result = check_guardrails(payment, decision, history, now=NOW)

        assert result.rule_triggered != "R5_CONTACT_LIMIT"


# ── Combined / integration scenarios ──────────────────────────────────────────

class TestCombinedScenarios:
    def test_r2_takes_priority_over_r3(self):
        """A ₹75,000 payment with 5 attempts: R2 (amount) fires before R3 (retries)."""
        payment  = _payment(amount=75_000.00, previous_attempts=5)
        decision = _decision(RecoveryAction.RETRY)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.rule_triggered == "R2_AMOUNT_LIMIT"

    def test_fully_clean_case_is_approved(self):
        """No rule should fire for a clean ₹500 first-attempt payment."""
        payment  = _payment(amount=500.00, previous_attempts=0)
        decision = _decision(RecoveryAction.SEND_PAYMENT_LINK)

        result = check_guardrails(payment, decision, [], now=NOW)

        assert result.result       == GuardrailOutcome.APPROVED
        assert result.final_action == RecoveryAction.SEND_PAYMENT_LINK
        assert result.rule_triggered is None
