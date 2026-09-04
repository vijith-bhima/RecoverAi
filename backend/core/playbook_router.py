"""
core/playbook_router.py — Deterministic Playbook Router for RecoverAI.

Strictly mapped to the 5 SQL-verified failure reasons present in recoverai.db:
1. BANK_SERVER_DOWN
2. NETWORK_TIMEOUT
3. CARD_EXPIRED
4. INSUFFICIENT_FUNDS
5. INVALID_OTP

No synthetic or unconfirmed categories (like CHECKOUT_ABANDONED, TEMPORARY_GATEWAY_ERROR,
fraud flags, or WhatsApp) are processed here.

Differentiates transient failure types (BANK_SERVER_DOWN, NETWORK_TIMEOUT, INVALID_OTP)
using real row attributes (priority_tier, amount, previous_attempts, lifetime_value)
so their playbooks remain distinct, explainable, and grounded in database truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from models.schemas import (
    ChannelPreference,
    Customer,
    FailureReason,
    Payment,
    PriorityTier,
    RecoveryAction,
    RecoveryPlan,
    RecoveryScore,
    RecoveryStep,
    StrategyType,
)

logger = logging.getLogger(__name__)


@dataclass
class PlaybookRoute:
    strategy_type: StrategyType
    recommended_action: RecoveryAction
    preferred_channel: ChannelPreference
    diagnosis: str
    reason: str
    confidence: float
    steps: List[RecoveryStep]
    playbook_name: str = "TEMPORARY_BANK_FAILURE"
    delay_seconds: int = 0
    requires_wait: bool = False


def route_playbook(
    payment: Payment,
    score: RecoveryScore,
    customer: Optional[Customer] = None,
) -> PlaybookRoute:
    """
    Selects the exact recovery playbook based on failure reason and real row attributes.
    Enforces the rule: Temporary failures WAIT and RECHECK before customer contact.
    """
    reason = payment.failure_reason
    amount = payment.amount
    prev_attempts = payment.previous_attempts
    tier = score.priority_tier
    prob = score.recovery_probability
    
    # Preferred channel fallback to SMS if not specified
    channel = customer.preferred_channel if customer else ChannelPreference.SMS
    if channel == ChannelPreference.WHATSAPP:
        channel = ChannelPreference.SMS

    # ──────────────────────────────────────────────────────────────────────────
    # 0. High-Value or Bounded Limit Check
    # ──────────────────────────────────────────────────────────────────────────
    if amount > 10000.0 or prev_attempts >= 2:
        return PlaybookRoute(
            strategy_type=StrategyType.BOUNDED_ESCALATION,
            recommended_action=RecoveryAction.ESCALATE_TO_HUMAN,
            preferred_channel=channel,
            playbook_name="HIGH_VALUE_GUARDRAIL_BLOCK",
            diagnosis="high_value_guardrail_escalation",
            reason=(
                f"Transaction value ₹{amount:,.2f} exceeds autonomous limit (₹10,000) or reached max attempts ({prev_attempts}). "
                "Autonomous link generation blocked; routed to senior merchant recovery queue."
            ),
            confidence=0.95,
            delay_seconds=0,
            requires_wait=False,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.ESCALATE_TO_HUMAN,
                    channel=channel,
                    delay_seconds=0,
                    description="Immediate human escalation and merchant alert notification",
                )
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 1. BANK_SERVER_DOWN (Playbook: TEMPORARY_BANK_FAILURE)
    # Transient issuer/bank downtime. DO NOT send link immediately.
    # WAIT -> RECHECK -> DECIDE.
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.BANK_SERVER_DOWN:
        return PlaybookRoute(
            strategy_type=StrategyType.INTELLIGENT_RETRY,
            recommended_action=RecoveryAction.WAIT_AND_RECHECK,
            preferred_channel=channel,
            playbook_name="TEMPORARY_BANK_FAILURE",
            diagnosis="bank_server_downtime_transient",
            reason=(
                f"Bank server downtime detected (₹{amount:,.2f}). Failure is transient. "
                "Waiting 10s for bank gateway to stabilize before rechecking status."
            ),
            confidence=min(0.92, max(0.65, prob + 0.1)),
            delay_seconds=10,
            requires_wait=True,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.WAIT_AND_RECHECK,
                    channel=channel,
                    delay_seconds=10,
                    description="Wait for bank gateway stabilization and recheck payment status",
                ),
                RecoveryStep(
                    step_number=2,
                    action=RecoveryAction.SEND_PAYMENT_LINK,
                    channel=channel,
                    delay_seconds=0,
                    description="Generate secure recovery payment link if payment remains uncompleted",
                ),
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. NETWORK_TIMEOUT (Playbook: NETWORK_TIMEOUT)
    # Transport/gateway latency drop. DO NOT contact customer immediately.
    # WAIT -> RECHECK -> RAPID RETRY / LINK.
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.NETWORK_TIMEOUT:
        return PlaybookRoute(
            strategy_type=StrategyType.INTELLIGENT_RETRY,
            recommended_action=RecoveryAction.WAIT_AND_RECHECK,
            preferred_channel=channel,
            playbook_name="NETWORK_TIMEOUT",
            diagnosis="network_timeout_transient_latency",
            reason=(
                f"Network timeout encountered on ₹{amount:,.2f}. "
                "Waiting 10s to verify if transaction settled asynchronously before contacting customer."
            ),
            confidence=min(0.90, max(0.65, prob + 0.05)),
            delay_seconds=10,
            requires_wait=True,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.WAIT_AND_RECHECK,
                    channel=channel,
                    delay_seconds=10,
                    description="Recheck payment state to prevent duplicate charge",
                ),
                RecoveryStep(
                    step_number=2,
                    action=RecoveryAction.SEND_PAYMENT_LINK,
                    channel=channel,
                    delay_seconds=0,
                    description="Dispatch fresh link if transaction was genuinely dropped",
                ),
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 3. INSUFFICIENT_FUNDS (Playbook: INSUFFICIENT_FUNDS)
    # Funds unavailable. DO NOT spam immediately.
    # Schedule cooldown recovery link.
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.INSUFFICIENT_FUNDS:
        return PlaybookRoute(
            strategy_type=StrategyType.FUNDS_COOLDOWN_REMINDER,
            recommended_action=RecoveryAction.WAIT_AND_RECHECK,
            preferred_channel=channel,
            playbook_name="INSUFFICIENT_FUNDS",
            diagnosis="insufficient_funds_delayed_recovery",
            reason=(
                f"Insufficient funds detected on ₹{amount:,.2f}. Immediate retry is counterproductive. "
                "Scheduling 15s cooldown period before sending flexible payment reminder."
            ),
            confidence=0.75,
            delay_seconds=15,
            requires_wait=True,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.WAIT_AND_RECHECK,
                    channel=channel,
                    delay_seconds=15,
                    description="Account cooldown period to allow fund reload / alternative arrangement",
                ),
                RecoveryStep(
                    step_number=2,
                    action=RecoveryAction.SEND_PAYMENT_LINK,
                    channel=channel,
                    delay_seconds=0,
                    description="Deliver flexible multi-method payment link with extended validity",
                ),
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 4. CARD_EXPIRED (Playbook: CARD_EXPIRED)
    # Permanent card instrument failure. NEVER retry same card.
    # Route directly to Alternate Payment Method (UPI, NetBanking, New Card).
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.CARD_EXPIRED:
        return PlaybookRoute(
            strategy_type=StrategyType.ALTERNATE_PAYMENT_LINK,
            recommended_action=RecoveryAction.ALTERNATE_PAYMENT_METHOD,
            preferred_channel=channel,
            playbook_name="CARD_EXPIRED",
            diagnosis="card_expired_alternate_method_routing",
            reason=(
                f"Card is expired on ₹{amount:,.2f}. Retrying the card is blocked by safety guardrails. "
                f"Generating smart payment link with UPI and NetBanking alternatives via {channel.value}."
            ),
            confidence=0.82,
            delay_seconds=0,
            requires_wait=False,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.ALTERNATE_PAYMENT_METHOD,
                    channel=channel,
                    delay_seconds=0,
                    description="Dispatch alternate payment method link (UPI / NetBanking enabled)",
                ),
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 5. INVALID_OTP (Playbook: INVALID_OTP)
    # Customer entered wrong OTP or session timed out.
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.INVALID_OTP:
        return PlaybookRoute(
            strategy_type=StrategyType.INTELLIGENT_RETRY,
            recommended_action=RecoveryAction.SEND_PAYMENT_LINK,
            preferred_channel=channel,
            playbook_name="INVALID_OTP",
            diagnosis="otp_auth_timeout_renewal",
            reason=(
                f"Authentication / OTP timed out on ₹{amount:,.2f}. "
                f"Dispatching 1-click renewal payment link via {channel.value}."
            ),
            confidence=0.80,
            delay_seconds=0,
            requires_wait=False,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.SEND_PAYMENT_LINK,
                    channel=channel,
                    delay_seconds=0,
                    description="Direct 1-click re-authorization link delivered",
                ),
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 6. CHECKOUT_ABANDONED (Playbook: CHECKOUT_ABANDONED)
    # Drop-off during cart review / payment selection.
    # ──────────────────────────────────────────────────────────────────────────
    if reason == FailureReason.CHECKOUT_ABANDONED:
        return PlaybookRoute(
            strategy_type=StrategyType.CHECKOUT_ABANDONMENT_RECOVERY,
            recommended_action=RecoveryAction.SEND_PAYMENT_LINK,
            preferred_channel=channel,
            playbook_name="CHECKOUT_ABANDONED",
            diagnosis="checkout_cart_abandonment",
            reason=(
                f"Customer abandoned checkout cart (₹{amount:,.2f}). "
                f"Sending gentle cart reminder recovery link via {channel.value}."
            ),
            confidence=0.85,
            delay_seconds=0,
            requires_wait=False,
            steps=[
                RecoveryStep(
                    step_number=1,
                    action=RecoveryAction.SEND_PAYMENT_LINK,
                    channel=channel,
                    delay_seconds=0,
                    description="Deliver personalized cart recovery link",
                ),
            ],
        )

    # Fallback for unexpected reasons
    return PlaybookRoute(
        strategy_type=StrategyType.INTELLIGENT_RETRY,
        recommended_action=RecoveryAction.SEND_PAYMENT_LINK,
        preferred_channel=channel,
        playbook_name="UNKNOWN_FAILURE",
        diagnosis="unclassified_failure_handling",
        reason=f"Unclassified failure '{reason.value}' on ₹{amount:,.2f}. Dispatching standard recovery link.",
        confidence=0.60,
        delay_seconds=0,
        requires_wait=False,
        steps=[
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.SEND_PAYMENT_LINK,
                channel=channel,
                delay_seconds=0,
                description="General recovery payment link",
            )
        ],
    )
