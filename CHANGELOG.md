# CHANGELOG — RecoverAI

Running log of real bugs encountered and fixed during development.
(Required for the pitch video — we document problems honestly, not after the fact.)

---

## [Phase 1] — 2026-08-31

### Initial setup

- Created project structure, Pydantic models, DB schema, and synthetic data generator.
- `models/schemas.py`: Defined `Payment`, `Customer`, `RecoveryScore`, `AgentDecision`,
  `GuardrailResult`, `RecoveryAttempt`, `AuditLogEntry`, `GroundTruth` with full validation.
- `db.py`: SQLite schema with FK constraints, WAL mode, and named-column row factory.
- `data/generate_data.py`: 500 payments across 150 customers with weighted failure-reason
  distribution and hidden `ground_truth` table generated via a separate oracle function.
- `logging_config.py`: JSON-formatted structured logging, replaces all bare `print()`
  calls in pipeline code.

### Design decision recorded

**Circular evaluation guard:** `actual_recovery_outcome` in `ground_truth` is generated
by `_ground_truth_oracle()` which uses different base rates, noise levels, and adjustment
formulas than `diagnosis.py`'s `score_recovery()`. This ensures Phase 7 F1/precision/recall
are honest — the heuristic cannot score 100% by construction.

---
---

## [Phase 2] — 2026-08-31

### Bug #1: `sqlite3.OperationalError: LIMIT clause should come after UNION ALL not before`

**File:** `core/diagnosis.py` — demo query in `_run_demo()`

**What happened:** Wrote a `UNION ALL` query with `LIMIT 2` directly on each branch:
```sql
SELECT ... WHERE failure_reason = 'BANK_SERVER_DOWN' LIMIT 2
UNION ALL
SELECT ... WHERE failure_reason = 'NETWORK_TIMEOUT' LIMIT 2
```

SQLite (and standard SQL) does not allow `LIMIT` on individual `UNION` branches —
`LIMIT` is a clause of the whole `SELECT` statement, not a branch modifier.

**Fix:** Wrapped each branch in a subquery so `LIMIT` applies inside the subquery scope:
```sql
SELECT * FROM (SELECT ... WHERE failure_reason = 'BANK_SERVER_DOWN' LIMIT 2)
UNION ALL
SELECT * FROM (SELECT ... WHERE failure_reason = 'NETWORK_TIMEOUT' LIMIT 2)
```

**Lesson:** SQLite is strict about `LIMIT` placement in compound queries. This is
actually standard SQL behaviour — MySQL is more permissive, which can mask the bug.

---

## [Phase 4] — 2026-08-31

### Bug #2: `ValidationError` — Pydantic rejects `status=SUCCESS` in test for R1 guardrail

**File:** `tests/test_guardrails.py` — `TestR1AlreadySuccessful::test_already_successful_payment_is_blocked`

**What happened:** The `Payment` schema has a validator that rejects `status=SUCCESS`
because successful payments shouldn't normally enter the recovery pipeline:
```python
@field_validator("status")
def must_be_failed(cls, v):
    if v == PaymentStatus.SUCCESS:
        raise ValueError("A successful payment should not enter the recovery pipeline.")
```
But R1 guards *exactly* this edge case — a duplicate event fired after recovery
(race condition, webhook replay, etc.). The test tried to construct `Payment(status=SUCCESS)`
directly, which hit the validator and raised `ValidationError` before the test ran.

**Fix:** Used `Payment.model_construct(status=PaymentStatus.SUCCESS, ...)` which is
Pydantic v2's intended way to bypass validators when you deliberately need to simulate
an invalid/edge-case state in a test.

**Lesson:** `model_construct()` is the right tool when testing guardrail/edge-case code
that handles states the schema intentionally disallows in normal flow. The schema validator
is still correct — we don't weaken it just to make a test pass.
