"""
tests/test_pipeline.py — End-to-end pipeline integration tests.

These tests run the full Phase 2–6 pipeline on a small set of synthetic
payments (no DB required — all objects are constructed in-memory) to verify
the pipeline wires together correctly.

Separate from test_guardrails.py which tests the guardrail engine in isolation.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import (
    AgentDecision,
    AttemptStatus,
    ChannelPreference,
    Customer,
    EventType,
    FailureReason,
    GuardrailOutcome,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PriorityTier,
    RecoveryAction,
    RecoveryPlan,
    RecoveryScore,
    RecoveryStep,
    StrategyType,
)
from core.diagnosis import score_recovery
from core.agent import get_agent_decision
from core.guardrails import check_guardrails

NOW = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def loyal_customer() -> Customer:
    return Customer(
        customer_id="pipe_cust_loyal",
        total_payments=50,
        successful_payments=46,
        failed_payments=4,
    )


@pytest.fixture
def new_customer() -> Customer:
    return Customer(
        customer_id="pipe_cust_new",
        total_payments=1,
        successful_payments=0,
        failed_payments=1,
    )


def _payment(failure_reason: FailureReason, amount: float = 3000.0,
             previous_attempts: int = 0) -> Payment:
    return Payment(
        payment_id=f"pipe_test_{failure_reason.value.lower()}",
        customer_id="pipe_cust_loyal",
        amount=amount,
        status=PaymentStatus.FAILED,
        failure_reason=failure_reason,
        payment_method=PaymentMethod.UPI,
        timestamp=NOW,
        previous_attempts=previous_attempts,
    )


# ── Phase 2: Diagnosis scores ──────────────────────────────────────────────────

class TestDiagnosis:
    def test_bank_down_scores_high(self, loyal_customer):
        p = _payment(FailureReason.BANK_SERVER_DOWN)
        score = score_recovery(p, loyal_customer)
        assert score.recovery_probability >= 0.70
        assert score.is_temporary is True
        assert score.is_recoverable is True

    def test_card_expired_scores_low(self, loyal_customer):
        p = _payment(FailureReason.CARD_EXPIRED)
        score = score_recovery(p, loyal_customer)
        assert score.recovery_probability <= 0.40
        assert score.is_temporary is False

    def test_insufficient_funds_not_temporary(self, loyal_customer):
        p = _payment(FailureReason.INSUFFICIENT_FUNDS)
        score = score_recovery(p, loyal_customer)
        assert score.is_temporary is False

    def test_network_timeout_scores_high(self, loyal_customer):
        p = _payment(FailureReason.NETWORK_TIMEOUT)
        score = score_recovery(p, loyal_customer)
        assert score.recovery_probability >= 0.65

    def test_retries_reduce_probability(self, loyal_customer):
        p0 = _payment(FailureReason.BANK_SERVER_DOWN, previous_attempts=0)
        p2 = _payment(FailureReason.BANK_SERVER_DOWN, previous_attempts=2)
        s0 = score_recovery(p0, loyal_customer)
        s2 = score_recovery(p2, loyal_customer)
        assert s2.recovery_probability < s0.recovery_probability

    def test_loyal_scores_higher_than_new(self, loyal_customer, new_customer):
        p = _payment(FailureReason.INSUFFICIENT_FUNDS)
        p_new = Payment(
            payment_id="pipe_new_cust",
            customer_id="pipe_cust_new",
            amount=3000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.INSUFFICIENT_FUNDS,
            payment_method=PaymentMethod.UPI,
            timestamp=NOW,
            previous_attempts=0,
        )
        s_loyal = score_recovery(p, loyal_customer)
        s_new   = score_recovery(p_new, new_customer)
        assert s_loyal.recovery_probability > s_new.recovery_probability

    def test_score_is_pydantic_validated(self, loyal_customer):
        p = _payment(FailureReason.BANK_SERVER_DOWN)
        score = score_recovery(p, loyal_customer)
        assert isinstance(score, RecoveryScore)
        assert 0.0 <= score.recovery_probability <= 1.0
        assert score.payment_id == p.payment_id
        assert score.diagnosis_notes != ""


# ── Phase 3: Agent decisions ───────────────────────────────────────────────────

class TestAgent:
    def test_decision_is_schema_valid(self, loyal_customer):
        p = _payment(FailureReason.BANK_SERVER_DOWN)
        score = score_recovery(p, loyal_customer)
        decision = get_agent_decision(p, score)
        assert isinstance(decision, AgentDecision)
        assert decision.payment_id == p.payment_id
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.recommended_action, RecoveryAction)

    def test_large_amount_escalated_by_agent(self, loyal_customer):
        from core.guardrails import check_guardrails
        p = _payment(FailureReason.NETWORK_TIMEOUT, amount=50_000.0)
        score = score_recovery(p, loyal_customer)
        decision = get_agent_decision(p, score, loyal_customer)
        guardrail = check_guardrails(p, decision, [])
        assert guardrail.final_action == RecoveryAction.ESCALATE_TO_HUMAN

    def test_card_expired_never_retried(self, loyal_customer):
        p = _payment(FailureReason.CARD_EXPIRED)
        score = score_recovery(p, loyal_customer)
        decision = get_agent_decision(p, score)
        assert decision.recommended_action != RecoveryAction.RETRY

    def test_bank_down_first_attempt_retried(self, loyal_customer):
        p = _payment(FailureReason.BANK_SERVER_DOWN, previous_attempts=0)
        score = score_recovery(p, loyal_customer)
        decision = get_agent_decision(p, score)
        assert decision.recommended_action in (RecoveryAction.WAIT_AND_RECHECK, RecoveryAction.RETRY)


# ── Phase 4: Guardrail integration with diagnosis + agent ─────────────────────

class TestGuardrailIntegration:
    def test_full_pipeline_normal_payment_approved(self, loyal_customer):
        """Normal ₹3,000 bank-down payment should pass all guardrails."""
        p = _payment(FailureReason.BANK_SERVER_DOWN, amount=3_000.0)
        score     = score_recovery(p, loyal_customer)
        decision  = get_agent_decision(p, score)
        guardrail = check_guardrails(p, decision, [], now=NOW)

        assert guardrail.result == GuardrailOutcome.APPROVED
        assert guardrail.final_action == decision.recommended_action

    def test_full_pipeline_large_payment_blocked(self, loyal_customer):
        """₹50,000 payment: agent might recommend RETRY, guardrail must block it."""
        p = _payment(FailureReason.NETWORK_TIMEOUT, amount=50_000.0)
        score     = score_recovery(p, loyal_customer)
        decision  = get_agent_decision(p, score)
        guardrail = check_guardrails(p, decision, [], now=NOW)

        # Regardless of agent recommendation, large amount must be handled
        assert guardrail.final_action in (
            RecoveryAction.ESCALATE_TO_HUMAN,
            RecoveryAction.STOP,
        )

    def test_pipeline_produces_different_actions_per_reason(self, loyal_customer):
        """Different failure reasons should produce different final actions."""
        actions = set()
        for reason in FailureReason:
            p = Payment(
                payment_id=f"pipe_{reason.value}",
                customer_id="pipe_cust_loyal",
                amount=2_000.0,
                status=PaymentStatus.FAILED,
                failure_reason=reason,
                payment_method=PaymentMethod.UPI,
                timestamp=NOW,
                previous_attempts=0,
            )
            score     = score_recovery(p, loyal_customer)
            decision  = get_agent_decision(p, score)
            guardrail = check_guardrails(p, decision, [], now=NOW)
            actions.add(guardrail.final_action)

        # We should see at least 2 distinct actions across 5 failure types
        assert len(actions) >= 2


# ── Evaluate.py smoke test ─────────────────────────────────────────────────────

class TestEvaluate:
    def test_compute_metrics_correct(self):
        """Unit test the metric computation function directly."""
        from evaluate import compute_metrics

        # Craft a simple known dataset
        results = [
            {"amount": 1000.0, "predicted_pos": True,  "actual_pos": True,  "recovered": True,  "escalated": False, "guardrail_blocked": False, "failure_reason": "BANK_SERVER_DOWN"},
            {"amount": 2000.0, "predicted_pos": True,  "actual_pos": False, "recovered": False, "escalated": False, "guardrail_blocked": False, "failure_reason": "CARD_EXPIRED"},
            {"amount": 3000.0, "predicted_pos": False, "actual_pos": True,  "recovered": False, "escalated": False, "guardrail_blocked": True,  "failure_reason": "INSUFFICIENT_FUNDS"},
            {"amount": 4000.0, "predicted_pos": False, "actual_pos": False, "recovered": False, "escalated": True,  "guardrail_blocked": True,  "failure_reason": "NETWORK_TIMEOUT"},
        ]

        m = compute_metrics(results)

        # TP=1, FP=1, FN=1, TN=1
        assert m["tp"] == 1
        assert m["fp"] == 1
        assert m["fn"] == 1
        assert m["tn"] == 1
        assert m["precision"] == pytest.approx(0.5, abs=1e-6)
        assert m["recall"]    == pytest.approx(0.5, abs=1e-6)
        assert m["f1"]        == pytest.approx(0.5, abs=1e-6)
        assert m["successful"] == 1
        assert m["revenue_recovered"] == pytest.approx(1000.0)
        assert m["human_escalations"] == 1
        assert m["guardrail_blocks"]  == 2

    def test_compute_metrics_no_division_by_zero(self):
        """All negatives — precision/recall/F1 should be 0, not crash."""
        from evaluate import compute_metrics

        results = [
            {"amount": 500.0, "predicted_pos": False, "actual_pos": False,
             "recovered": False, "escalated": False, "guardrail_blocked": False,
             "failure_reason": "CARD_EXPIRED"},
        ]
        m = compute_metrics(results)
        assert m["precision"] == 0.0
        assert m["recall"]    == 0.0
        assert m["f1"]        == 0.0


# ── RecoverAI 2.0 Core Features ───────────────────────────────────────────────

class TestRecoverAI2Features:
    def test_checkout_abandonment_scoring_and_plan(self, loyal_customer):
        p = Payment(
            payment_id="chk_abandon_001",
            customer_id="pipe_cust_loyal",
            amount=8000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.CHECKOUT_ABANDONED,
            payment_method=PaymentMethod.CHECKOUT_CART,
            timestamp=NOW,
            previous_attempts=0,
            event_type=EventType.CHECKOUT_ABANDONED,
        )
        score = score_recovery(p, loyal_customer)
        assert score.is_recoverable is True
        assert score.expected_recovery_value > 0
        assert score.priority_tier in (PriorityTier.HIGH, PriorityTier.MEDIUM)

        decision = get_agent_decision(p, score, loyal_customer)
        assert decision.plan is not None
        assert decision.plan.strategy == StrategyType.CHECKOUT_ABANDONMENT_RECOVERY
        assert len(decision.plan.steps) >= 2

    def test_intelligent_retry_transient_plan(self, loyal_customer):
        p = _payment(FailureReason.BANK_SERVER_DOWN, amount=4500.0)
        score = score_recovery(p, loyal_customer)
        decision = get_agent_decision(p, score, loyal_customer)
        assert decision.plan is not None
        assert decision.plan.strategy == StrategyType.INTELLIGENT_RETRY
        # Step 1 should be WAIT or WAIT_AND_RECHECK for transient bank error
        assert decision.plan.steps[0].action in (RecoveryAction.WAIT, RecoveryAction.WAIT_AND_RECHECK)

    def test_customer_ltv_priority_tiering(self):
        vip_cust = Customer(
            customer_id="cust_vip",
            total_payments=25,
            successful_payments=24,
            failed_payments=1,
            lifetime_value=60000.0,
            preferred_channel=ChannelPreference.EMAIL,
        )
        p = Payment(
            payment_id="vip_payment_001",
            customer_id="cust_vip",
            amount=6000.0,
            status=PaymentStatus.FAILED,
            failure_reason=FailureReason.NETWORK_TIMEOUT,
            payment_method=PaymentMethod.UPI,
            timestamp=NOW,
            previous_attempts=0,
        )
        score = score_recovery(p, vip_cust)
        assert score.priority_tier == PriorityTier.HIGH
        assert score.expected_recovery_value >= 4000.0

        decision = get_agent_decision(p, score, vip_cust)
        assert decision.preferred_channel == ChannelPreference.EMAIL
