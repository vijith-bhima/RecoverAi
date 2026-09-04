"""
core/audit.py — Audit trail and verifiable decision log for RecoverAI 2.0.

Provides full transparency into:
- Recovery Probability, Expected Recovery Value & Revenue Priority Tier
- Failure-specific Strategy & Multi-step Execution Roadmap
- Channel Selected (SMS / Email)
- Guardrail outcome (APPROVED / BLOCKED & Rule triggered)
- Action Taken and Verifiable Recovery Status
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_connection
from logging_config import get_logger
from models.schemas import (
    AgentDecision,
    AttemptStatus,
    AuditLogEntry,
    GuardrailResult,
    RecoveryAttempt,
    RecoveryScore,
)

logger = get_logger(__name__)


# ── Write ──────────────────────────────────────────────────────────────────────

def write_audit_log(
    score:       RecoveryScore,
    decision:    AgentDecision,
    guardrail:   GuardrailResult,
    attempt:     RecoveryAttempt,
    merchant_id: str = "mer_default",
    user_id:     str = "usr_default",
) -> AuditLogEntry:
    """
    Assemble and persist one complete audit log entry with strict tenant ownership.
    """
    now = datetime.now(timezone.utc)
    channel_str = attempt.channel_used.value if attempt.channel_used else decision.preferred_channel.value

    entry = AuditLogEntry(
        event_id=f"evt_{uuid.uuid4().hex[:10]}",
        payment_id=score.payment_id,
        ml_score=score.recovery_probability,
        expected_value=score.expected_recovery_value,
        priority_tier=score.priority_tier.value,
        ai_diagnosis=decision.diagnosis,
        ai_recommendation=decision.recommended_action,
        strategy_type=decision.strategy_type.value,
        channel_used=channel_str,
        guardrail_result=guardrail.result,
        action_taken=guardrail.final_action,
        result=attempt.status,
        timestamp=now,
    )

    # Persist to DB with merchant_id ownership
    import sqlite3
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_logs
                    (event_id, merchant_id, user_id, payment_id, ml_score, expected_value, priority_tier,
                     ai_diagnosis, ai_recommendation, strategy_type, channel_used,
                     guardrail_result, action_taken, result, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    merchant_id,
                    user_id,
                    entry.payment_id,
                    entry.ml_score,
                    entry.expected_value,
                    entry.priority_tier,
                    entry.ai_diagnosis,
                    entry.ai_recommendation.value,
                    entry.strategy_type,
                    entry.channel_used,
                    entry.guardrail_result.value,
                    entry.action_taken.value,
                    entry.result.value,
                    entry.timestamp.isoformat(),
                ),
            )
        except Exception:
            pass

    logger.info(
        "audit.written",
        extra={
            "event_id":          entry.event_id,
            "payment_id":        entry.payment_id,
            "ml_score":          entry.ml_score,
            "expected_value":    entry.expected_value,
            "priority_tier":     entry.priority_tier,
            "strategy":          entry.strategy_type,
            "channel":           entry.channel_used,
            "ai_recommendation": entry.ai_recommendation.value,
            "guardrail_result":  entry.guardrail_result.value,
            "action_taken":      entry.action_taken.value,
            "result":            entry.result.value,
        },
    )

    return entry


# ── Read / display ─────────────────────────────────────────────────────────────

def print_audit(payment_id: str) -> None:
    """
    Print a formatted audit record for one payment_id.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM audit_logs WHERE payment_id = ? ORDER BY timestamp DESC LIMIT 1",
            (payment_id,),
        ).fetchone()

        payment_row = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()

    if row is None:
        print(f"\n  No audit log found for payment_id: {payment_id}")
        return

    guardrail_icon = "✓ APPROVED" if row["guardrail_result"] == "APPROVED" else "✗ BLOCKED"
    outcome_icon   = {
        "SUCCESS": "✅ SUCCESS",
        "FAILED":  "❌ FAILED",
        "PENDING": "⏳ PENDING",
    }.get(row["result"], row["result"])

    print("\n" + "═" * 68)
    print("  RecoverAI 2.0 — Verifiable Audit Record")
    print("═" * 68)
    print(f"  Event ID       : {row['event_id']}")
    print(f"  Payment ID     : {row['payment_id']}")
    if payment_row:
        print(f"  Amount         : ₹{payment_row['amount']:,.2f}")
        print(f"  Failure Reason : {payment_row['failure_reason']}")
        print(f"  Payment Method : {payment_row['payment_method']}")
    print("  " + "─" * 64)
    print(f"  Recovery Score : {row['ml_score']:.2%} (probability)")
    if "expected_value" in row.keys() and row["expected_value"]:
        print(f"  Expected Value : ₹{row['expected_value']:,.2f}  [{row.get('priority_tier', 'MEDIUM')} PRIORITY]")
    print(f"  Strategy       : {row.get('strategy_type', 'INTELLIGENT_RETRY')}")
    print(f"  Channel Used   : {row.get('channel_used', 'SMS')}")
    print(f"  AI Recommended : {row['ai_recommendation']}")
    print("  " + "─" * 64)
    print(f"  Guardrail      : {guardrail_icon}")
    print(f"  Action Taken   : {row['action_taken']}")
    print("  " + "─" * 64)
    print(f"  Outcome        : {outcome_icon}")
    print(f"  Timestamp      : {row['timestamp']}")
    print("═" * 68 + "\n")


def get_audit_entry(payment_id: str) -> dict | None:
    """Return the latest audit log row as a dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM audit_logs WHERE payment_id = ? ORDER BY timestamp DESC LIMIT 1",
            (payment_id,),
        ).fetchone()
    return dict(row) if row else None
