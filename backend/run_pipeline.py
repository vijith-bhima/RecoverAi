"""
run_pipeline.py — Autonomous Revenue Recovery Agent (RecoverAI 2.0) Demo Runner.

Demonstrates:
  Demo 1 — Temporary failure (₹5,000 BANK_SERVER_DOWN):
           Intelligent Retry: WAIT → RECHECK → PAYMENT LINK → ₹5,000 Recovered
  Demo 2 — Checkout abandonment (₹12,000 cart drop-off):
           Detect → Score → Channel Link → ₹12,000 Recovered
  Demo 3 — Dangerous / high-value case (₹75,000):
           AI Recommends → Guardrails BLOCK → Bounded Escalation to Human Review
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve()))

from dotenv import load_dotenv

load_dotenv()

from core.agent import get_agent_decision
from core.audit import print_audit, write_audit_log
from core.diagnosis import score_recovery
from core.executor import execute_action
from core.guardrails import check_guardrails
from db import fetch_customer, fetch_payment, get_connection, init_db
from logging_config import get_logger, setup_logging

init_db()
from models.schemas import (
    ChannelPreference,
    Customer,
    EventType,
    FailureReason,
    GuardrailOutcome,
    Payment,
    PaymentMethod,
    PaymentStatus,
    RecoveryAction,
)

setup_logging()
logging.getLogger().setLevel(logging.WARNING)

logger = get_logger(__name__)

NOW = datetime.now(timezone.utc)


def _divider(char: str = "─", width: int = 70) -> str:
    return "  " + char * width


def _banner(title: str) -> None:
    print("\n" + "═" * 74)
    print(f"  {title}")
    print("═" * 74)


def run_payment(
    payment:  Payment,
    customer: Customer,
    label:    str = "",
) -> dict:
    """Run the complete autonomous revenue-recovery pipeline on one event."""
    print(f"\n{_divider('═')}")
    if label:
        print(f"  {label}")
    print(f"  Event Type:   {payment.event_type.value}")
    print(f"  Identifier:   {payment.payment_id}")
    print(f"  Amount:       ₹{payment.amount:,.2f}  |  Reason: {payment.failure_reason.value}")
    print(f"  Customer:     {customer.customer_id}  (LTV: ₹{customer.lifetime_value:,.2f} | Pref: {customer.preferred_channel.value})")
    print(_divider())

    # STEP 1 — Context Engine & Recovery Scoring (ML Scorer)
    score = score_recovery(payment, customer)
    print(f"  [1. ML SCORER]           Prob: {score.recovery_probability:.1%} | Expected Value: ₹{score.expected_recovery_value:,.2f} | Tier: {score.priority_tier.value}")
    print(f"                           Notes: {score.diagnosis_notes.split('|')[0].strip()}")

    # STEP 2 — AI Agent & Structured Recovery Plan Generation
    decision = get_agent_decision(payment, score, customer)
    print(f"\n  [2. RECOVERY AGENT]      Strategy:   {decision.strategy_type.value}")
    print(f"                           Channel:    {decision.preferred_channel.value}")
    print(f"                           Init Action:{decision.recommended_action.value} (Confidence: {decision.confidence:.0%})")
    print(f"                           Reasoning:  {decision.reason}")

    # Display Generated Multi-Step Recovery Plan
    if decision.plan and decision.plan.steps:
        print(f"\n  [3. RECOVERY PLAN - {decision.plan.plan_id}]")
        for s in decision.plan.steps:
            chan_tag = f" via {s.channel.value}" if s.channel else ""
            dur_tag = f" ({s.duration_minutes} mins)" if s.duration_minutes else ""
            print(f"     Step {s.step_number}: [{s.action.value}{chan_tag}{dur_tag}] → {s.description}")

    # STEP 3 — Guardrail Engine
    guardrail = check_guardrails(payment, decision, [], now=NOW)
    if guardrail.result == GuardrailOutcome.APPROVED:
        print(f"\n  [4. GUARDRAIL ENGINE]    ✓ APPROVED → Final action: {guardrail.final_action.value}")
    else:
        print(f"\n  [4. GUARDRAIL ENGINE]    ✗ BLOCKED [{guardrail.rule_triggered}]")
        print(f"                           Reason:       {guardrail.reason}")
        print(f"                           Final Action: {guardrail.final_action.value}")

    # STEP 4 — Execution & Result Verification
    attempt = execute_action(payment, guardrail, score.recovery_probability, decision.preferred_channel)
    outcome_icon = {"SUCCESS": "✅ RECOVERED", "FAILED": "❌ FAILED", "PENDING": "⏳ PENDING"}.get(attempt.status.value, "❓")
    print(f"\n  [5. VERIFICATION]        Outcome: {outcome_icon}")
    print(f"                           Details: {attempt.reason}")

    # STEP 5 — Audit Trail
    entry = write_audit_log(score, decision, guardrail, attempt)
    print(f"  [6. AUDIT TRAIL]         Logged with event_id: {entry.event_id}")

    return {
        "payment_id":   payment.payment_id,
        "amount":       payment.amount,
        "strategy":     decision.strategy_type.value,
        "channel":      decision.preferred_channel.value,
        "ai_action":    decision.recommended_action.value,
        "final_action": guardrail.final_action.value,
        "guardrail":    guardrail.result.value,
        "outcome":      attempt.status.value,
        "recovered":    attempt.status.value == "SUCCESS",
    }


def run_three_demo_cases() -> None:
    """
    Execute the 3 primary situations requested by the user:
      Demo 1 — Temporary failure (₹5,000 BANK_SERVER_DOWN)
      Demo 2 — Checkout abandonment (₹12,000 cart drop-off)
      Demo 3 — Dangerous / high-value case (₹75,000)
    """
    _banner("RecoverAI 2.0 — Autonomous Revenue Recovery Demo Suite")
    print("  Context Engine → ML Scorer → Recovery Plan → Guardrails → Verification")

    results = []

    # Demo 1 — Temporary failure (₹5,000 BANK_SERVER_DOWN)
    p1 = Payment(
        payment_id="demo_temp_001",
        customer_id="cust_vip_001",
        amount=5_000.00,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.BANK_SERVER_DOWN,
        payment_method=PaymentMethod.UPI,
        timestamp=NOW,
        previous_attempts=0,
        event_type=EventType.PAYMENT_FAILED,
    )
    c1 = Customer(
        customer_id="cust_vip_001",
        total_payments=20,
        successful_payments=19,
        failed_payments=1,
        lifetime_value=48000.0,
        preferred_channel=ChannelPreference.SMS,
    )
    results.append(run_payment(p1, c1, "DEMO 1: Temporary Failure (Intelligent Retry: Wait 5m → Recheck → Recover)"))

    # Demo 2 — Checkout abandonment (₹12,000 cart drop-off)
    p2 = Payment(
        payment_id="demo_cart_002",
        customer_id="cust_cart_002",
        amount=12_000.00,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.CHECKOUT_ABANDONED,
        payment_method=PaymentMethod.CHECKOUT_CART,
        timestamp=NOW,
        previous_attempts=0,
        event_type=EventType.CHECKOUT_ABANDONED,
    )
    c2 = Customer(
        customer_id="cust_cart_002",
        total_payments=8,
        successful_payments=7,
        failed_payments=1,
        lifetime_value=32000.0,
        preferred_channel=ChannelPreference.EMAIL,
    )
    results.append(run_payment(p2, c2, "DEMO 2: Checkout Abandonment (Cart Recovery Link via Email)"))

    # Demo 3 — Dangerous / high-value case (₹75,000)
    p3 = Payment(
        payment_id="demo_highval_003",
        customer_id="cust_highval_003",
        amount=75_000.00,
        status=PaymentStatus.FAILED,
        failure_reason=FailureReason.NETWORK_TIMEOUT,
        payment_method=PaymentMethod.NET_BANKING,
        timestamp=NOW,
        previous_attempts=0,
        event_type=EventType.PAYMENT_FAILED,
    )
    c3 = Customer(
        customer_id="cust_highval_003",
        total_payments=12,
        successful_payments=11,
        failed_payments=1,
        lifetime_value=120000.0,
        preferred_channel=ChannelPreference.SMS,
    )
    results.append(run_payment(p3, c3, "DEMO 3: High-Value Risk Case (Guardrail Blocks Autonomous Action → Human Escalation)"))

    # Summary
    print(f"\n{_divider('═')}")
    print("  Demo Suite Summary")
    print(_divider())
    print(f"  {'Demo':<8} {'Amount':>8}  {'Strategy':<24} {'Guardrail':<10} {'Outcome'}")
    print(_divider())
    for i, r in enumerate(results, 1):
        outcome_icon = {"SUCCESS": "✅ RECOVERED", "FAILED": "❌ FAILED", "PENDING": "⏳ PENDING"}.get(r["outcome"], "❓")
        g_icon = "✓" if r["guardrail"] == "APPROVED" else "✗"
        print(
            f"  Demo {i:<3} ₹{r['amount']:>8,.0f}  {r['strategy'][:24]:<24} "
            f"{g_icon} {r['guardrail']:<9} {outcome_icon}"
        )

    recovered = sum(r["amount"] for r in results if r["recovered"])
    total_val = sum(r["amount"] for r in results)
    print(_divider())
    print(f"  Total Revenue Evaluated: ₹{total_val:,.2f}")
    print(f"  Revenue Recovered:       ₹{recovered:,.2f}")
    print(f"  Cases Escalated:         {sum(1 for r in results if r['final_action'] == 'ESCALATE_TO_HUMAN')}")
    print(_divider('═') + "\n")


def run_single_payment(payment_id: str) -> None:
    """Run the pipeline on a specific payment from the database."""
    p_row = fetch_payment(payment_id)
    if p_row is None:
        print(f"\n  ✗ Payment '{payment_id}' not found in database.\n")
        sys.exit(1)

    c_row = fetch_customer(p_row["customer_id"])
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
        event_type=EventType(p_row["event_type"]) if "event_type" in p_row.keys() and p_row["event_type"] else EventType.PAYMENT_FAILED,
    )
    customer = Customer(
        customer_id=p_row["customer_id"],
        total_payments=c_dict.get("total_payments", 5),
        successful_payments=c_dict.get("successful_payments", 4),
        failed_payments=c_dict.get("failed_payments", 1),
        lifetime_value=c_dict.get("lifetime_value", 15000.0),
        preferred_channel=ChannelPreference(c_dict.get("preferred_channel", "SMS")),
    )

    _banner(f"RecoverAI 2.0 — Pipeline Run for {payment_id}")
    run_payment(payment, customer, "")
    print()
    print_audit(payment_id)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        run_single_payment(sys.argv[1])
    else:
        run_three_demo_cases()
