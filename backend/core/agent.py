"""
core/agent.py — AI Agent layer: strategy routing, failure playbooks, and multi-step Recovery Plans.

What this module does:
1. Chooses failure-specific & customer-specific strategy playbooks:
   - INTELLIGENT_RETRY (Bank downtime, network timeout)
   - CHECKOUT_ABANDONMENT_RECOVERY (Abandoned cart drop-offs)
   - ALTERNATE_PAYMENT_LINK (Expired cards, OTP issues)
   - FUNDS_COOLDOWN_REMINDER (Insufficient balance)
   - BOUNDED_ESCALATION (Max retries reached or high-value risks)
2. Selects optimal Contact Channel (SMS, Email, WhatsApp)
3. Generates a structured multi-step Recovery Plan
4. Supports MockProvider (deterministic reasoning), GroqProvider (real LLM), and OllamaProvider
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from logging_config import get_logger
from models.schemas import (
    AgentDecision,
    ChannelPreference,
    Customer,
    FailureReason,
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

logger = get_logger(__name__)


# ── LLM provider interface ─────────────────────────────────────────────────────

class LLMProvider(ABC):
    """
    Abstract base for all LLM backends.
    """

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...

    def name(self) -> str:
        return self.__class__.__name__


# ── Mock provider (rule-based, failure-specific playbooks) ──────────────────────

class MockProvider(LLMProvider):
    """
    Deterministic rule-based provider that produces comprehensive,
    failure-specific reasoning and multi-step recovery plans.
    """

    _DIAGNOSIS: dict[FailureReason, str] = {
        FailureReason.BANK_SERVER_DOWN:        "temporary_service_failure",
        FailureReason.NETWORK_TIMEOUT:         "transient_network_error",
        FailureReason.TEMPORARY_GATEWAY_ERROR: "gateway_latency_issue",
        FailureReason.INVALID_OTP:             "authentication_timeout",
        FailureReason.INSUFFICIENT_FUNDS:      "insufficient_balance",
        FailureReason.CARD_EXPIRED:            "expired_payment_method",
        FailureReason.CHECKOUT_ABANDONED:      "checkout_abandonment",
    }

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        lines = {
            k.strip(): v.strip()
            for line in user_prompt.splitlines()
            if ":" in line
            for k, v in [line.split(":", 1)]
        }

        reason_str = lines.get("failure_reason", "BANK_SERVER_DOWN")
        prev_att   = int(lines.get("previous_attempts", "0"))
        amount     = float(lines.get("amount", "1000").replace(",", ""))
        prob       = float(lines.get("recovery_probability", "0.5"))
        is_temp    = lines.get("is_temporary", "True").lower() == "true"
        channel    = lines.get("preferred_channel", "SMS")

        try:
            failure_reason = FailureReason(reason_str)
        except ValueError:
            failure_reason = FailureReason.BANK_SERVER_DOWN

        diagnosis = self._DIAGNOSIS.get(failure_reason, "unknown_failure")

        # ── 1. Stop if clearly unrecoverable ──────────────────────────────────
        if prob < 0.15 and not is_temp:
            return json.dumps({
                "diagnosis":          diagnosis,
                "strategy_type":      StrategyType.STOP_UNRECOVERABLE.value,
                "recommended_action": RecoveryAction.STOP.value,
                "preferred_channel":  channel,
                "reason": (
                    f"Recovery probability {prob:.0%} is very low and failure "
                    f"({failure_reason.value}) is permanent. Stopping to prevent customer friction."
                ),
                "confidence": 0.88,
            })

        # ── 2. Checkout Abandonment Recovery ───────────────────────────────────
        if failure_reason == FailureReason.CHECKOUT_ABANDONED:
            return json.dumps({
                "diagnosis":          diagnosis,
                "strategy_type":      StrategyType.CHECKOUT_ABANDONMENT_RECOVERY.value,
                "recommended_action": RecoveryAction.SEND_PAYMENT_LINK.value,
                "preferred_channel":  channel,
                "reason": (
                    f"Customer dropped off during checkout (₹{amount:,.2f}). "
                    f"Sending gentle abandoned cart recovery link via {channel}."
                ),
                "confidence": 0.82,
            })

        # ── 3. Bounded retry limit exceeded ────────────────────────────────────
        if prev_att >= 2:
            return json.dumps({
                "diagnosis":          diagnosis,
                "strategy_type":      StrategyType.BOUNDED_ESCALATION.value,
                "recommended_action": RecoveryAction.ESCALATE_TO_HUMAN.value,
                "preferred_channel":  channel,
                "reason": (
                    f"Previous recovery attempts ({prev_att}) reached autonomous limit. "
                    "Stopping automated retries and assigning to recovery team."
                ),
                "confidence": 0.90,
            })

        # ── Route via core/playbook_router.py ────────────────────────────────
        from core.playbook_router import route_playbook
        
        # Construct temporary lightweight Payment and RecoveryScore objects for routing
        temp_payment = Payment(
            payment_id=lines.get("payment_id", "pay_mock"),
            customer_id=lines.get("customer_id", "cust_mock"),
            amount=amount,
            status=PaymentStatus.FAILED,
            failure_reason=failure_reason,
            payment_method=PaymentMethod.UPI,
            timestamp=datetime.now(timezone.utc),
            previous_attempts=prev_att,
        )
        temp_score = RecoveryScore(
            payment_id=temp_payment.payment_id,
            failure_reason=failure_reason,
            recovery_probability=prob,
            expected_recovery_value=amount * prob,
            priority_tier=PriorityTier.HIGH if (amount * prob >= 4000) else PriorityTier.MEDIUM if (amount * prob >= 1500) else PriorityTier.LOW,
            is_temporary=is_temp,
            is_recoverable=prob >= 0.5,
            previous_attempts=prev_att,
            amount=amount,
            customer_success_rate=0.8,
            model_type="ML",
        )
        try:
            pref_ch = ChannelPreference(channel)
        except ValueError:
            pref_ch = ChannelPreference.SMS
        temp_customer = Customer(
            customer_id=temp_payment.customer_id,
            total_payments=5,
            successful_payments=4,
            failed_payments=1,
            lifetime_value=float(lines.get("customer_ltv", "0").replace(",", "")),
            preferred_channel=pref_ch,
        )

        route = route_playbook(temp_payment, temp_score, temp_customer)
        return json.dumps({
            "diagnosis":          route.diagnosis,
            "strategy_type":      route.strategy_type.value,
            "recommended_action": route.recommended_action.value,
            "preferred_channel":  route.preferred_channel.value,
            "reason":             route.reason,
            "confidence":         route.confidence,
        })


# ── Groq provider (real LLM) ───────────────────────────────────────────────────

class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Install groq: pip install groq")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")

        self._client = Groq(api_key=api_key)
        self._model  = (os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")).split("#")[0].strip()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        import time

        models_to_try = [self._model, "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
        # deduplicate while preserving order
        seen_models = set()
        models = [m for m in models_to_try if m and not (m in seen_models or seen_models.add(m))]

        for model_name in models:
            kwargs = dict(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            for attempt in range(2):
                try:
                    response = self._client.chat.completions.create(
                        **kwargs,
                        response_format={"type": "json_object"},
                        timeout=10,
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str and attempt == 0:
                        time.sleep(1.0)
                        continue
                    if any(k in err_str for k in ("404", "model_not_found", "model_decommissioned", "decommissioned")):
                        break  # try next active model
                    logger.warning(f"agent.groq_fallback: {e} -> fallback to MockProvider")
                    return MockProvider().complete(system_prompt, user_prompt)

        return MockProvider().complete(system_prompt, user_prompt)


# ── Ollama provider ────────────────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        import requests
        self._requests = requests
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model    = os.getenv("OLLAMA_MODEL", "llama3")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        combined = f"{system_prompt}\n\n{user_prompt}"
        resp = self._requests.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": combined, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["response"]


# ── Provider factory ───────────────────────────────────────────────────────────

def _get_provider() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "mock").lower()

    if provider_name == "groq":
        try:
            return GroqProvider()
        except Exception:
            return MockProvider()
    elif provider_name == "ollama":
        try:
            return OllamaProvider()
        except Exception:
            return MockProvider()

    return MockProvider()


# ── Prompt Builder ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are RecoverAI, an autonomous revenue-recovery agent for an Indian fintech platform.
Your job is to analyse payment events, diagnose root causes, select failure-specific playbooks,
and generate executable multi-step recovery recommendations.

Respond ONLY with valid JSON in this exact schema:
{
  "diagnosis":          "<short snake_case label>",
  "strategy_type":      "<INTELLIGENT_RETRY | CHECKOUT_ABANDONMENT_RECOVERY | ALTERNATE_PAYMENT_LINK | FUNDS_COOLDOWN_REMINDER | BOUNDED_ESCALATION | STOP_UNRECOVERABLE>",
  "recommended_action": "<WAIT | SEND_PAYMENT_LINK | RETRY | ESCALATE_TO_HUMAN | STOP>",
  "preferred_channel":  "<SMS | EMAIL | WHATSAPP>",
  "reason":             "<concise 1-2 sentence explanation>",
  "confidence":         <float between 0.0 and 1.0>
}
"""


def _build_prompt(payment: Payment, score: RecoveryScore, customer: Optional[Customer] = None) -> str:
    channel = customer.preferred_channel.value if customer else "SMS"
    ltv = customer.lifetime_value if customer else 0.0
    return f"""\
Analyse this failed payment event and recommend a recovery strategy.

payment_id: {payment.payment_id}
event_type: {payment.event_type.value}
failure_reason: {payment.failure_reason.value}
amount: {payment.amount:,.2f}
payment_method: {payment.payment_method.value}
previous_attempts: {payment.previous_attempts}
customer_ltv: {ltv:,.2f}
preferred_channel: {channel}
recovery_probability: {score.recovery_probability}
expected_recovery_value: {score.expected_recovery_value}
priority_tier: {score.priority_tier.value}
is_temporary: {score.is_temporary}
diagnosis_notes: {score.diagnosis_notes}

Respond with JSON only.
"""


# ── Multi-Step Recovery Plan Generator ─────────────────────────────────────────

def generate_recovery_plan(
    payment: Payment,
    score: RecoveryScore,
    strategy: StrategyType,
    channel: ChannelPreference,
) -> RecoveryPlan:
    """
    Construct a structured, multi-step execution roadmap for the recovery agent.
    """
    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
    steps: list[RecoveryStep] = []

    if strategy == StrategyType.INTELLIGENT_RETRY:
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.WAIT,
                duration_minutes=5,
                description="Wait 5 minutes for bank / gateway server instability to subside.",
            ),
            RecoveryStep(
                step_number=2,
                action=RecoveryAction.RETRY,
                description="Verify gateway status to prevent double charge, then initiate retry.",
            ),
            RecoveryStep(
                step_number=3,
                action=RecoveryAction.SEND_PAYMENT_LINK,
                channel=channel,
                description=f"If retry unsuccessful, generate and dispatch payment link via {channel.value}.",
            ),
            RecoveryStep(
                step_number=4,
                action=RecoveryAction.ESCALATE_TO_HUMAN,
                description="Stop after bounded attempt limit and assign to human recovery queue.",
            ),
        ]

    elif strategy == StrategyType.CHECKOUT_ABANDONMENT_RECOVERY:
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.WAIT,
                duration_minutes=15,
                description="Wait 15 minutes to confirm customer has not completed checkout in another session.",
            ),
            RecoveryStep(
                step_number=2,
                action=RecoveryAction.SEND_PAYMENT_LINK,
                channel=channel,
                description=f"Send personalized abandoned cart recovery link via {channel.value}.",
            ),
            RecoveryStep(
                step_number=3,
                action=RecoveryAction.ESCALATE_TO_HUMAN,
                description="Escalate high-value carts if unanswered within 24 hours.",
            ),
        ]

    elif strategy == StrategyType.ALTERNATE_PAYMENT_LINK:
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.STOP,
                description="Halt automated retry on expired / invalid card to prevent issuer penalty.",
            ),
            RecoveryStep(
                step_number=2,
                action=RecoveryAction.SEND_PAYMENT_LINK,
                channel=channel,
                description=f"Dispatch payment link via {channel.value} with UPI, NetBanking, and alternate card choices.",
            ),
            RecoveryStep(
                step_number=3,
                action=RecoveryAction.ESCALATE_TO_HUMAN,
                description="Escalate to human review if unresolved after 1 attempt.",
            ),
        ]

    elif strategy == StrategyType.FUNDS_COOLDOWN_REMINDER:
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.WAIT,
                duration_minutes=120,
                description="Apply 2-hour cooldown to avoid aggressive retries on zero-balance account.",
            ),
            RecoveryStep(
                step_number=2,
                action=RecoveryAction.SEND_PAYMENT_LINK,
                channel=channel,
                description=f"Send flexible payment link via {channel.value} allowing customer to pay when funds clear.",
            ),
            RecoveryStep(
                step_number=3,
                action=RecoveryAction.ESCALATE_TO_HUMAN,
                description="Escalate if payment remains unpaid after 48 hours.",
            ),
        ]

    elif strategy == StrategyType.BOUNDED_ESCALATION:
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.ESCALATE_TO_HUMAN,
                description="Autonomous recovery limit reached or amount exceeds safety threshold. Assigned to human agent.",
            )
        ]

    else:  # STOP_UNRECOVERABLE
        steps = [
            RecoveryStep(
                step_number=1,
                action=RecoveryAction.STOP,
                description="Permanently close recovery effort to prevent customer annoyance.",
            )
        ]

    return RecoveryPlan(
        plan_id=plan_id,
        payment_id=payment.payment_id,
        strategy=strategy,
        steps=steps,
        priority=score.priority_tier,
        expected_recovery_value=score.expected_recovery_value,
        created_at=datetime.now(timezone.utc),
    )


# ── Main Public Function ───────────────────────────────────────────────────────

def get_agent_decision(
    payment: Payment,
    score: RecoveryScore,
    customer: Optional[Customer] = None,
) -> AgentDecision:
    """
    Get a structured recovery recommendation and multi-step plan from the AI agent.
    """
    provider    = _get_provider()
    user_prompt = _build_prompt(payment, score, customer)

    try:
        raw_json = provider.complete(_SYSTEM_PROMPT, user_prompt)
        data     = json.loads(raw_json)

        action = RecoveryAction(data["recommended_action"])
        strategy = StrategyType(data.get("strategy_type", StrategyType.INTELLIGENT_RETRY.value))
        channel = ChannelPreference(data.get("preferred_channel", "SMS"))

        plan = generate_recovery_plan(payment, score, strategy, channel)

        decision = AgentDecision(
            payment_id=payment.payment_id,
            diagnosis=data["diagnosis"],
            recommended_action=action,
            strategy_type=strategy,
            preferred_channel=channel,
            reason=data["reason"],
            confidence=float(data["confidence"]),
            plan=plan,
        )

    except Exception as exc:
        logger.error(
            "agent.decision_error",
            extra={
                "payment_id": payment.payment_id,
                "error":      str(exc),
                "fallback":   "ESCALATE_TO_HUMAN",
            },
        )
        plan = generate_recovery_plan(
            payment, score, StrategyType.BOUNDED_ESCALATION, ChannelPreference.SMS
        )
        decision = AgentDecision(
            payment_id=payment.payment_id,
            diagnosis="parse_error",
            recommended_action=RecoveryAction.ESCALATE_TO_HUMAN,
            strategy_type=StrategyType.BOUNDED_ESCALATION,
            preferred_channel=ChannelPreference.SMS,
            reason=f"Agent response error ({exc}); escalating for bounded safety.",
            confidence=0.0,
            plan=plan,
        )

    # Persist plan to DB if DB available and not in fast evaluation mode
    if not os.environ.get("EVALUATION_MODE"):
        try:
            from db import save_recovery_plan
            if decision.plan:
                save_recovery_plan(
                    decision.plan.plan_id,
                    decision.plan.payment_id,
                    decision.plan.strategy.value,
                    [s.model_dump() for s in decision.plan.steps],
                    decision.plan.priority.value,
                    decision.plan.expected_recovery_value,
                    decision.plan.created_at.isoformat(),
                )
        except Exception:
            pass

    logger.info(
        "agent.decision",
        extra={
            "payment_id":         decision.payment_id,
            "strategy":           decision.strategy_type.value,
            "channel":            decision.preferred_channel.value,
            "recommended_action": decision.recommended_action.value,
            "confidence":         decision.confidence,
        },
    )

    return decision
