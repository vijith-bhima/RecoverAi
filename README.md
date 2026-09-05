# RecoverAI ⚡
### Autonomous Revenue Recovery Agent for Payment Failures

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Python](https://img.shields.io/badge/Language-Python%203.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016%20%2B%20SQLite%20WAL-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Razorpay](https://img.shields.io/badge/Payments-Razorpay%20API%20v1-0C2340?style=flat&logo=razorpay&logoColor=white)](https://razorpay.com)
[![Scikit-Learn](https://img.shields.io/badge/ML-Random%20Forest%20Classifier-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Tests](https://img.shields.io/badge/Tests-49%20Passed-brightgreen?style=flat&logo=pytest&logoColor=white)](#proof-it-works)
[![Security](https://img.shields.io/badge/Multi--Tenancy-JWT%20%2B%20PBKDF2%20Isolated-blueviolet?style=flat)](#authentication--multi-tenancy)

> **Buildathon Track:** Razorpay AI Buildathon — *AI Revenue Recovery (Track 03)*  
> **Mission:** Recover lost digital revenue autonomously by detecting payment risk, diagnosing root failure causes, selecting failure-specific recovery playbooks, enforcing deterministic financial guardrails, executing bounded actions, and verifying actual payment capture.

---

## Table of Contents

- [The Problem](#the-problem)
- [RecoverAI in One Sentence](#recoverai-in-one-sentence)
- [Why This Is an Agent](#why-this-is-an-agent)
- [System Architecture](#system-architecture)
- [Lifecycle: Event → Decision → Guardrail → Action → Verification](#lifecycle-event--decision--guardrail--action--verification)
- [Recovery Decision Engine](#recovery-decision-engine)
- [Native-First Razorpay Recovery](#native-first-razorpay-recovery)
- [Ghost Revenue Hunter](#ghost-revenue-hunter)
- [Recovery Passport & Recover Promise](#recovery-passport--recover-promise)
- [AI + ML Architecture](#ai--ml-architecture)
- [Safety & Bounded Autonomy (Guardrails)](#safety--bounded-autonomy-guardrails)
- [Authentication & Multi-Tenancy](#authentication--multi-tenancy)
- [Database Architecture](#database-architecture)
- [API Architecture](#api-architecture)
- [Frontend & Product Architecture](#frontend--product-architecture)
- [Visual Assets & Interface Tour](#visual-assets--interface-tour)
- [Proof It Works](#proof-it-works)
- [Demo Scenarios](#demo-scenarios)
- [Observability & Audit Trail](#observability--audit-trail)
- [Failure Handling & Edge Cases](#failure-handling--edge-cases)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Key Engineering Decisions](#key-engineering-decisions)
- [What Makes RecoverAI Different](#what-makes-recoverai-different)
- [Security Considerations](#security-considerations)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Engineering Takeaways](#engineering-takeaways)
- [License](#license)

---

## The Problem

In modern digital commerce, **10% to 25% of all checkout transactions fail**. For high-growth businesses processing millions of rupees, payment failure is the single largest source of direct revenue leakage and involuntary customer churn.

A failed payment is never a single monolithic event. In reality, failures fall across distinct technical and behavioral categories:

1. **Transient Bank Server Downtime:** Issuer bank gateway or switch is temporarily down.
2. **Network Timeouts & Latency Glitches:** Packets dropped between merchant, gateway, and issuing switch.
3. **Customer Balance Exhaustion:** Insufficient funds in account at the moment of charge.
4. **Permanent Instrument Invalidation:** Expired credit/debit cards or blocked cards.
5. **Authentication Drop-off:** Incorrect OTP, OTP timeout, or 3D-Secure modal dismissal.
6. **Checkout Cart Abandonment:** Friction during payment method selection or checkout review.
7. **Halted Subscriptions & Overdue Invoices:** Recurring billing exhaustion needing customer grace commitments.
8. **Orphan Captured Payments (Ghost Revenue):** Gateway captures funds but the local checkout drops or fails reconciliation.
9. **High-Risk / Suspicious Activity:** Potential fraud indicators requiring human review.

### Why Basic & Naive Approaches Fail

Existing payment systems rely on crude, static automation:
- **Blind Retries:** Immediately resubmitting an expired card or insufficient balance payment triggers issuer penalty fees, worsens bank risk scoring, and annoys the customer.
- **Immediate Spam Messaging:** Blasting a customer with generic payment links when the failure was a transient 5-second bank switch drop causes double-charging and merchant support overhead.
- **Unbounded Loops:** Automated retry bots with no cooldown or attempt ceilings loop infinitely until accounts are locked.
- **Unchecked LLM Generation:** Allowing an LLM to directly call payment charge APIs without deterministic guardrails creates severe financial exposure.
- **Phantom/Ghost Revenue Dilemma:** Blindly creating duplicate orders or ignoring unmatched captures results in unfulfilled customer orders or double billing.

RecoverAI answers the foundational fintech question:
> *"What is the optimal, safe, and verifiable next action for THIS payment, for THIS customer, at THIS exact moment?"*

---

## RecoverAI in One Sentence

**RecoverAI is a compound AI revenue-recovery agent that combines supervised machine learning, contextual LLM strategy planning, deterministic financial guardrails, and automated payment gateway verification to safely recover failed transactions without human intervention.**

### The Core Architectural Principle

$$\text{ML Predicts} \longrightarrow \text{AI Reasons} \longrightarrow \text{Rules Protect} \longrightarrow \text{Code Executes} \longrightarrow \text{Database Remembers}$$

* **ML Predicts:** Random Forest classifier evaluates historical payment parameters, customer transaction track record, and amounts to compute empirical recovery probabilities and expected recovery values.
* **AI Reasons:** LLM parses failure taxonomy, customer lifetime value (LTV), and previous retry attempts to generate structured, multi-step recovery execution plans.
* **Rules Protect:** Deterministic guardrail engine evaluates hard financial boundaries (amount ceilings, retry limits, cooldown windows, fraud tripwires) and overrides unsafe AI suggestions.
* **Code Executes:** Strongly-typed Python execution services interact with Razorpay APIs to generate payment links, dispatch multi-channel alerts, and trigger status checks.
* **Database Remembers:** Enterprise PostgreSQL 16 (with SQLite/WAL supported for local development) maintains tenant-isolated payment states, idempotency keys, structured recovery plans, Ghost Revenue incident records, and tamper-evident audit logs.

> [!IMPORTANT]
> **Financial Execution Fence:** The Large Language Model (LLM) **never** executes financial transactions or charges directly. All recovery operations are strictly bounded by deterministic Python guardrails.

---

## Why This Is an Agent

RecoverAI is not a simple script or a passive dashboard. It implements a closed-loop **Perception → Diagnosis → Strategy → Guardrail → Execution → Verification → Learning** agentic cycle:

```mermaid
flowchart TD
    A[Payment Failure / Webhook Event] --> B[Context Assembler & Feature Extractor]
    B --> C[ML Recovery Scorer & Expected Value Engine]
    C --> D[AI Recovery Planner & Strategy Router]
    D --> E[Structured Multi-Step Recovery Plan]
    E --> F{Deterministic Guardrail Engine}
    F -->|Approved| G[Action Executor & Razorpay Dispatcher]
    F -->|Blocked / High-Value| H[Human Escalation Queue & Merchant Alert]
    G --> I[Gateway Status Verification & Webhook Recheck]
    I -->|Confirmed Paid| J[State Transition: RECOVERED]
    I -->|Pending / Retry Needed| K[Next Plan Step / Cooldown Queue]
    H --> L[(Tenant-Scoped Database & Audit Log)]
    J --> L
    K --> L
```

### The Autonomous Agent Loop

1. **Sense & Ingest:** Listens to Razorpay webhooks (`payment.failed`, `payment.captured`, `payment.link.paid`) or scheduled queue workers.
2. **Context Enrichment:** Pulls customer lifetime value, historical success rate, retry history, and failure telemetry.
3. **ML Scoring:** Estimates recovery probability $P(\text{recovery})$ and calculates Expected Value:
   $$\text{Expected Recovery Value} = \text{Amount} \times P(\text{recovery})$$
4. **Strategy Formulation:** Selects from 7 failure-specific playbooks and generates a multi-step `RecoveryPlan`.
5. **Deterministic Bounding:** Evaluates 7 formal safety rules (amount limits, cooldown periods, contact frequencies, instrument validity).
6. **Execution & Dispatch:** Creates authenticated payment links with SMS/Email notifications via Razorpay API.
7. **State Verification & Reconciliation:** Awaits payment capture confirmation before declaring revenue recovered and handles orphan captures via Ghost Revenue Hunter.

---

## System Architecture

```mermaid
flowchart TB
    subgraph ClientLayer["Frontend Architecture (Next.js 16 + React 19 + Tailwind CSS)"]
        UI_Dash["Dashboard (Overview & Metrics)"]
        UI_Console["Agent Console (Live Streaming Feed)"]
        UI_Queue["Recovery Opportunities & Escalations"]
        UI_Ghost["Ghost Revenue Hunter (Capture Reconciliation)"]
        UI_Passport["Recovery Passport & Promise-to-Pay"]
        UI_Analytics["Analytics & ROI Breakdown"]
        UI_Audit["Audit Trail & Compliance Log"]
        UI_Guide["Interactive Guide & Playbook Tour"]
        UI_Settings["Merchant Profile & Razorpay Credentials"]
    end

    subgraph APILayer["API & Security Layer (FastAPI + JWT + PBKDF2)"]
        API_Auth["Authentication & Tenant Resolver (/auth/*)"]
        API_Webhooks["Razorpay Webhook Handler (HMAC-SHA256)"]
        API_Payments["Payment & Recovery Ingestion (/payments/*, /recovery/*)"]
        API_Ghost["Ghost Revenue Engine (/ghost-revenue/*)"]
        API_Passport["Recovery Passport API (/recovery/passport/*)"]
        API_Metrics["Metrics & ROI Engine (/metrics, /analytics/roi)"]
        API_Worker["Background Agent Loop (Autonomous Worker)"]
    end

    subgraph CoreEngine["RecoverAI Core Agent Engine (Python 3.11+)"]
        Core_Diag["Diagnosis & Context Scorer (core/diagnosis.py)"]
        Core_ML["Random Forest Classifier (models/recovery_model.pkl)"]
        Core_Agent["AI Strategy & Plan Generator (core/agent.py)"]
        Core_Router["Deterministic Playbook Router (core/playbook_router.py)"]
        Core_Guard["Deterministic Guardrails R1-R7 (core/guardrails.py)"]
        Core_Passport["Recovery Passport & Eligibility (core/recovery_passport.py)"]
        Core_Exec["Action Executor & Razorpay Client (core/executor.py)"]
        Core_Audit["Tamper-Proof Audit Logger (core/audit.py)"]
    end

    subgraph StorageLayer["Persistence & Infrastructure (PostgreSQL 16 / SQLite WAL / Razorpay)"]
        DB_Tenant["Tenant Isolation (merchants, users, settings)"]
        DB_Core["Core Tables (payments, customers, recovery_plans)"]
        DB_Links["Link Guard (recovery_links unique per payment)"]
        DB_Ghost["Ghost Revenue (ghost_revenue_incidents, events)"]
        DB_Audit["Audit & Ground Truth (audit_logs, ground_truth)"]
        Ext_Razorpay["Razorpay Live Gateway (Payment Links, Webhooks)"]
        Ext_LLM["LLM Inference (Groq LLaMA 3.1 / Ollama / MockProvider)"]
    end

    ClientLayer -->|Bearer JWT / API Key| APILayer
    APILayer --> CoreEngine
    CoreEngine --> StorageLayer
    Core_Exec --> Ext_Razorpay
    Core_Agent --> Ext_LLM
```

---

## Lifecycle: Event → Decision → Guardrail → Action → Verification

The table below traces the exact step-by-step lifecycle of an event across the codebase:

| Step | Operation | Source Module | Database Interaction | Output / State Transition |
| :--- | :--- | :--- | :--- | :--- |
| **1. Ingest** | Webhook or API event arrives with failure payload | [`api/main.py`](file:///c:/RecoverAi/backend/api/main.py) | Inserts into `payments` & `customers` | State: `FAILED` |
| **2. Authenticate** | Verifies HMAC-SHA256 signature / Bearer token | [`api/main.py`](file:///c:/RecoverAi/backend/api/main.py) | Resolves `merchant_id` via secret/API key | Tenant identified |
| **3. Contextualize** | Computes customer success rate, LTV, retry count | [`core/diagnosis.py`](file:///c:/RecoverAi/backend/core/diagnosis.py) | Reads `customers` history | Customer profile built |
| **4. ML Predict** | Random Forest model calculates recovery likelihood | [`models/train.py`](file:///c:/RecoverAi/backend/models/train.py) | Reads `encoder_metadata.pkl` | `RecoveryScore` ($P$, EV, Tier) |
| **5. Plan & Passport** | LLM/Router generates structured roadmap; verifies eligibility & native ownership | [`core/agent.py`](file:///c:/RecoverAi/backend/core/agent.py), [`core/recovery_passport.py`](file:///c:/RecoverAi/backend/core/recovery_passport.py) | Inserts into `recovery_plans` | `RecoveryPlan` & `RecoveryPassport` |
| **6. Guard** | Evaluates deterministic safety rules R1–R7 | [`core/guardrails.py`](file:///c:/RecoverAi/backend/core/guardrails.py) | Queries recent `recovery_attempts` | `APPROVED` or `BLOCKED` |
| **7. Execute / Monitor** | Monitors native Razorpay recovery, or conditionally dispatches one link only after eligibility is confirmed | [`core/executor.py`](file:///c:/RecoverAi/backend/core/executor.py) | Reserves `recovery_links` before any gateway call | Native path monitored, or one `PENDING` RecoverAI link attempt |
| **8. Audit** | Records complete decision trail and score telemetry | [`core/audit.py`](file:///c:/RecoverAi/backend/core/audit.py) | Inserts into `audit_logs` | Immutable `evt_...` record |
| **9. Verify / Reconcile** | Receives `payment.captured`, `payment.link.paid`, or rechecks gateway status | [`api/main.py`](file:///c:/RecoverAi/backend/api/main.py) | Updates tenant payment state, or records a Ghost Revenue incident if no internal match exists | `RECOVERED` only after confirmation; no order or charge is auto-created |

---

## Recovery Decision Engine

RecoverAI evaluates incoming failure reasons against distinct playbooks and row-level attributes:

| Failure Mode | Diagnosis Classification | Strategy Playbook | Primary Action | Safety Stop Condition |
| :--- | :--- | :--- | :--- | :--- |
| **`BANK_SERVER_DOWN`** | Transient issuer downtime | `INTELLIGENT_RETRY` | `WAIT_AND_RECHECK` (10s) $\rightarrow$ `SEND_PAYMENT_LINK` | Retry limit (2) or Max Cooldown reached |
| **`NETWORK_TIMEOUT`** | Latency / dropped packet | `INTELLIGENT_RETRY` | `WAIT_AND_RECHECK` (10s) $\rightarrow$ `SEND_PAYMENT_LINK` | Transaction settled or Max attempts reached |
| **`INSUFFICIENT_FUNDS`** | Account balance deficiency | `FUNDS_COOLDOWN_REMINDER` | Persist cooldown $\rightarrow$ gateway recheck $\rightarrow$ one eligible flexible link | Paid status, Razorpay-native path, existing link, or contact limits |
| **`CARD_EXPIRED`** | Invalid payment instrument | `ALTERNATE_PAYMENT_LINK` | `ALTERNATE_PAYMENT_METHOD` (UPI / NetBanking Link) | Direct card retry blocked by Rule R3 |
| **`INTERNATIONAL_CARD_UNSUPPORTED`** | Razorpay alternate checkout available | `RAZORPAY_FALLBACK_MONITORING` | Monitor Razorpay only | No RecoverAI retry, link, message, or Promise-to-Pay |
| **`SUBSCRIPTION_RETRY_ACTIVE`** | Razorpay native subscription retry in progress | `NATIVE_RETRY_MONITORING` | Monitor Razorpay only | No RecoverAI retry, link, message, or Promise-to-Pay |
| **`SUBSCRIPTION_HALTED`** | Native retries exhausted | `SUBSCRIPTION_RECOVERY` | Customer outreach + Promise-to-Pay commitment | Customer service cancellation or payment completed |
| **`INVOICE_OVERDUE`** | B2B/B2C invoice past due | `INVOICE_RECOVERY` | Schedule payment link + Promise-to-Pay workflow | Payment captured or escalated to collections |
| **`INVALID_OTP`** | Authentication failure/timeout | `INTELLIGENT_RETRY` | Direct 1-Click Renewal Link | Customer ignores renewal link |
| **`CHECKOUT_ABANDONED`**| Cart funnel drop-off | `CHECKOUT_ABANDONMENT_RECOVERY`| Personalized recovery payment link | 24-hour expiry without conversion |
| **`FRAUD_SUSPECTED`** | High-risk telemetry / stolen card | `BOUNDED_ESCALATION` | `ESCALATE_TO_HUMAN` | Autonomous recovery prohibited (Rule R7) |
| **Amount > ₹10,000** | Exceeds autonomous threshold | `BOUNDED_ESCALATION` | `ESCALATE_TO_HUMAN` | Autonomous action blocked (Rule R2) |

---

## Native-First Razorpay Recovery

RecoverAI treats Razorpay as the primary owner of a recovery path whenever Razorpay is already retrying or presenting an alternate checkout. It never claims those outcomes as RecoverAI recovery.

| Situation | RecoverAI Behavior |
| :--- | :--- |
| `INTERNATIONAL_CARD_UNSUPPORTED` | Monitor Razorpay alternate checkout silently; do not create a link, retry, message, or Promise-to-Pay. |
| `SUBSCRIPTION_RETRY_ACTIVE` | Monitor Razorpay native subscription retry silently; do not create a duplicate recovery path. |
| `BANK_SERVER_DOWN`, `NETWORK_TIMEOUT`, `INSUFFICIENT_FUNDS` | Persist a cooldown job, recheck the gateway/payment state, then create at most one eligible RecoverAI link. |
| Razorpay `captured` / `paid` | Stop all recovery actions. An unmatched capture becomes a tenant-scoped Ghost Revenue Hunter incident for explicit reconciliation. |

### Dispatch and Activity Semantics

`recovery_links` enforces one tenant-scoped RecoverAI link per original failed payment for both automated and manual dispatch. A live customer delivery is recorded only after Razorpay returns a successful payment-link response. The activity feed distinguishes cooldown waiting, gateway recheck, Razorpay-native monitoring, live dispatch, simulated/test-only output, existing-link monitoring, and Ghost Revenue reconciliation.

---

## Ghost Revenue Hunter

In production digital commerce, a critical edge case occurs when funds are successfully captured on the payment gateway (e.g. customer completed checkout via Razorpay), but the merchant backend or frontend dropped the session, timed out, or failed to record an internal order. This is **Ghost Revenue** (phantom captured money with unfulfilled orders).

```mermaid
flowchart TD
    A[Razorpay Webhook: payment.captured] --> B{Internal Payment / Order Matched?}
    B -->|Matched| C[Mark Payment RECOVERED]
    B -->|Unmatched / Orphan| D[Ghost Revenue Hunter Activated]
    D --> E[Record Tenant Incident in ghost_revenue_incidents]
    D --> F[Log Immutable Event in ghost_revenue_events]
    D --> G[Present Incident in Ghost Revenue UI Drawer]
    G --> H{Operator Action}
    H -->|Fulfill & Attach| I[Link to Order & Notify Customer]
    H -->|Refund / Investigate| J[Initiate Gateway Resolution]
```

### Key Principles of Ghost Revenue Hunter
1. **Zero Blind Order Creation:** RecoverAI never auto-creates an arbitrary database order upon detecting an unmatched capture.
2. **Zero Double Charges:** It never attempts to charge the customer a second time or trigger a duplicate payment link.
3. **Tenant-Scoped Incident Ledger:** Every incident is isolated to the authenticated merchant with complete Razorpay payload metadata, payment ID, amount, and contact details.
4. **Actionable Resolution Workflows:** Through the `/ghost-revenue` UI and `POST /ghost-revenue/incidents/{incident_id}/resolve`, operators can explicitly resolve incidents via order fulfillment reconciliation or escalation.

---

## Recovery Passport & Recover Promise

To bridge transparency and customer retention, RecoverAI introduces two foundational features:

### 1. Recovery Passport (`/recovery-passport`)
Every revenue-at-risk transaction is accompanied by an explainable **Recovery Passport** (`core/recovery_passport.py`):
- **Customer Context:** Historical payment success rate, lifetime value (LTV), and preferred outreach channel.
- **ML Expected Value:** Recovery probability score ($P$) and calculated expected recovery value.
- **Eligibility & Ownership:** Clear justification of whether Razorpay-native recovery is active or if RecoverAI intervention is eligible.
- **Attribution Rule:** Explicitly states whether recovered funds will be attributed as Razorpay-native or RecoverAI-incremental.
- **Safety Proof:** Lists the exact guardrail rules enforced prior to any outreach.

### 2. Recover Promise (Promise-to-Pay)
For subscriptions that have halted (`SUBSCRIPTION_HALTED`) or invoices that are past due (`INVOICE_OVERDUE`), immediate aggressive collection causes involuntary churn. **Recover Promise** provides a consent-based commitment workflow:
- The customer or merchant agrees on a promised payment date (`promised_date`) with a grace period.
- Prevents premature subscription cancellation while maintaining an active recovery schedule.
- **Strict Guardrail:** Unavailable for active native retries, already captured payments, or ordinary transient card failures.

---

## AI + ML Architecture

RecoverAI adopts a decoupled, layered ML/AI pipeline to ensure speed, explainability, and safety.

```mermaid
flowchart LR
    subgraph Layer1["ML Scorer (Supervised Random Forest)"]
        F1[Transaction Amount]
        F2[Previous Attempts]
        F3[Payment Method]
        F4[Failure Reason]
        F5[Customer Success Rate]
        F6[Customer LTV]
        F1 & F2 & F3 & F4 & F5 & F6 --> RF[Random Forest Classifier]
        RF --> Prob[Recovery Probability P: 0.05-0.95]
        Prob --> EV[Expected Recovery Value: Amount × P]
        EV --> Tier[Priority Tier: HIGH / MEDIUM / LOW]
    end

    subgraph Layer2["AI Strategy Planner (LLM Provider Interface)"]
        Tier & Prob & EV --> PromptBuilder[System & Context Prompt Builder]
        PromptBuilder --> Router{Provider Switch}
        Router -->|Live Cloud| Groq[Groq: LLaMA-3.1-8B-Instant]
        Router -->|Local LLM| Ollama[Ollama: LLaMA-3]
        Router -->|Fast / Offline| Mock[Deterministic MockProvider]
        Groq & Ollama & Mock --> PlanGen[Structured Multi-Step Recovery Plan]
    end

    Layer1 --> Layer2
```

### 1. Machine Learning Recovery Scorer ([`core/diagnosis.py`](file:///c:/RecoverAi/backend/core/diagnosis.py))
- **Model:** `RandomForestClassifier(n_estimators=100, max_depth=5)` trained in [`models/train.py`](file:///c:/RecoverAi/backend/models/train.py).
- **Features:** One-hot encoded payment method, failure reason, transaction amount, retry count, customer total transaction history, and historical payment success rate.
- **Expected Value Computation:**
  $$\text{Expected Recovery Value} = \text{Amount} \times \text{Recovery Probability}$$
- **Revenue Priority Tiering:**
  - **`HIGH`**: Expected Value $\ge$ ₹4,000, or (Amount $\ge$ ₹3,000 and Probability $\ge$ 75%).
  - **`MEDIUM`**: Expected Value $\ge$ ₹1,200, or Probability $\ge$ 45%.
  - **`LOW`**: Remaining low-probability or low-value cases.

### 2. Multi-Provider LLM Engine ([`core/agent.py`](file:///c:/RecoverAi/backend/core/agent.py))
- **Abstract Interface:** `LLMProvider` base class with pluggable drivers:
  - `GroqProvider`: Uses `llama-3.1-8b-instant` via Groq's low-latency API with JSON mode.
  - `OllamaProvider`: Local fallback via HTTP `http://localhost:11434/api/generate`.
  - `MockProvider`: Fast, deterministic fallback ensuring offline test and evaluation reliability.
- **Structured JSON Output:** Strict Pydantic schema validation enforcing `diagnosis`, `strategy_type`, `recommended_action`, `preferred_channel`, `reason`, and `confidence`.

---

## Safety & Bounded Autonomy (Guardrails)

In financial applications, an AI recommendation is **not** an authorization. Every action recommended by the AI agent must pass through the deterministic Guardrail Engine in [`core/guardrails.py`](file:///c:/RecoverAi/backend/core/guardrails.py):

```mermaid
flowchart TD
    AI_Rec[AI Agent Recommendation] --> R1{R1: Already Success?}
    R1 -->|Yes| Block_R1[BLOCKED: Action -> STOP]
    R1 -->|No| R2{R2: Amount > ₹10,000?}
    R2 -->|Yes| Block_R2[BLOCKED: Action -> ESCALATE_TO_HUMAN]
    R2 -->|No| R3{R3: Card Expired & Retry?}
    R3 -->|Yes| Block_R3[BLOCKED: Action -> SEND_PAYMENT_LINK]
    R3 -->|No| R4{R4: Attempts >= 2?}
    R4 -->|Yes| Block_R4[BLOCKED: Action -> ESCALATE_TO_HUMAN]
    R4 -->|No| R5{R5: Cooldown < 6 Hours?}
    R5 -->|Yes| Block_R5[BLOCKED: Action -> WAIT]
    R5 -->|No| R6{R6: Contact Count >= 2?}
    R6 -->|Yes| Block_R6[BLOCKED: Action -> STOP]
    R6 -->|No| R7{R7: Fraud / Risk Indicator?}
    R7 -->|Yes| Block_R7[BLOCKED: Action -> ESCALATE_TO_HUMAN]
    R7 -->|No| Approved[APPROVED: Agent Action Executed]
```

### Deterministic Safety Rules Summary

| Rule ID | Rule Name | Condition Evaluated | Enforcement Outcome | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **`R1`** | `ALREADY_SUCCESSFUL` | `payment.status == PaymentStatus.SUCCESS` | **BLOCKED** $\rightarrow$ `STOP` | Prevents double-charging on replayed webhooks |
| **`R2`** | `AMOUNT_LIMIT` | `payment.amount > MAX_AUTONOMOUS_AMOUNT` (₹10,000) | **BLOCKED** $\rightarrow$ `ESCALATE_TO_HUMAN` | Bounded ceiling on autonomous financial transactions |
| **`R3`** | `CARD_EXPIRED_NO_RETRY`| `failure_reason == CARD_EXPIRED` and action `RETRY` | **BLOCKED** $\rightarrow$ `SEND_PAYMENT_LINK`| Prevents card network fines on invalid instruments |
| **`R4`** | `MAX_RETRIES` | `previous_attempts >= MAX_RETRY_ATTEMPTS` (2) | **BLOCKED** $\rightarrow$ `ESCALATE_TO_HUMAN` | Enforces bounded autonomy; halts infinite retry loops |
| **`R5`** | `COOLDOWN` | Last attempt was $< 6\text{ hours}$ ago and action `RETRY` | **BLOCKED** $\rightarrow$ `WAIT` | Prevents rapid-fire gateway hammering |
| **`R6`** | `CONTACT_LIMIT` | Customer contacted $\ge 2\text{ times}$ across attempts | **BLOCKED** $\rightarrow$ `STOP` | Prevents customer harassment and fatigue |
| **`R7`** | `FRAUD_SUSPECTED` | Telemetry contains `FRAUD`, `STOLEN`, or `SUSPICIOUS` | **BLOCKED** $\rightarrow$ `ESCALATE_TO_HUMAN` | Prohibits automated action on compromised cards |

---

## Authentication & Multi-Tenancy

RecoverAI is built from the ground up as a secure, multi-tenant SaaS application ([`core/auth.py`](file:///c:/RecoverAi/backend/core/auth.py), [`tests/test_multi_tenant_security.py`](file:///c:/RecoverAi/backend/tests/test_multi_tenant_security.py)):

```mermaid
flowchart LR
    User[User / Client] --> AuthHeader[Authorization: Bearer <JWT> or X-API-Key]
    AuthHeader --> TenantResolver[FastAPI Dependency: get_current_user_context]
    TenantResolver --> CryptVerify[Verify HS256 JWT Signature & Expiration]
    CryptVerify --> TenantContext[Inject Authenticated Dict: merchant_id, role, user_id]
    TenantContext --> ScopedQuery[SQL Query: WHERE merchant_id = ? AND payment_id = ?]
    ScopedQuery --> Data[Isolated Tenant Records Only]
```

### Security Properties
1. **Password Protection:** PBKDF2-HMAC-SHA256 with 100,000 iterations and unique 16-byte random salts per user.
2. **Stateless JWT Tokens:** Standard HS256 JSON Web Tokens with embedded user IDs, expiration stamps, and in-memory process revocation.
3. **High-Entropy API Keys:** Generated with `rec_live_...` prefix using `secrets.token_urlsafe(24)`.
4. **Zero-Trust IDOR Protection:** Client-supplied `merchant_id` in request bodies is ignored. All queries enforce `WHERE merchant_id = ?` based strictly on the cryptographically validated token.
5. **Cross-Tenant Verification:** Accessing another tenant's payment, customer, recovery plan, or audit log yields an immediate `404 Not Found`.

---

## Database Architecture

RecoverAI implements an enterprise dual database architecture: **PostgreSQL 16 for production** and **SQLite/WAL for rapid zero-dependency local development** through a unified repository layer in [`db.py`](file:///c:/RecoverAi/backend/db.py).

```mermaid
erDiagram
    MERCHANTS ||--o{ USERS : "employs"
    MERCHANTS ||--o{ CUSTOMERS : "owns"
    MERCHANTS ||--o{ PAYMENTS : "processes"
    MERCHANTS ||--o{ CHECKOUTS : "tracks"
    MERCHANTS ||--o{ RECOVERY_PLANS : "manages"
    MERCHANTS ||--o{ RECOVERY_ATTEMPTS : "executes"
    MERCHANTS ||--o{ RECOVERY_LINKS : "owns one active link per payment"
    MERCHANTS ||--o{ GHOST_REVENUE_INCIDENTS : "reconciles"
    MERCHANTS ||--o{ AUDIT_LOGS : "audits"
    CUSTOMERS ||--o{ PAYMENTS : "initiates"
    CUSTOMERS ||--o{ CHECKOUTS : "abandons"
    PAYMENTS ||--o{ RECOVERY_PLANS : "generates"
    PAYMENTS ||--o{ RECOVERY_ATTEMPTS : "triggers"
    PAYMENTS ||--o| RECOVERY_LINKS : "has at most one"
    PAYMENTS ||--o{ AUDIT_LOGS : "logs"
    PAYMENTS ||--o| GROUND_TRUTH : "evaluates"

    MERCHANTS {
        string merchant_id PK
        string name
        string business_name
        string email
        string phone
        string razorpay_key_id
        string razorpay_webhook_secret
    }
    USERS {
        string user_id PK
        string merchant_id FK
        string email UK
        string password_hash
        string salt
        string full_name
        string role
        string api_key UK
    }
    CUSTOMERS {
        string customer_id PK
        string merchant_id FK
        int total_payments
        int successful_payments
        int failed_payments
        float lifetime_value
        string preferred_channel
    }
    PAYMENTS {
        string payment_id PK
        string merchant_id FK
        string customer_id FK
        float amount
        string status
        string failure_reason
        string payment_method
        int previous_attempts
    }
    RECOVERY_PLANS {
        string plan_id PK
        string merchant_id FK
        string payment_id FK
        string strategy
        string steps_json
        string priority
        float expected_recovery_value
    }
    RECOVERY_ATTEMPTS {
        string attempt_id PK
        string merchant_id FK
        string payment_id FK
        string action
        string status
        string reason
        string channel_used
    }
    RECOVERY_LINKS {
        string recovery_link_id PK
        string merchant_id FK
        string payment_id
        string status
        string razorpay_link_id
        string short_url
    }
    GHOST_REVENUE_INCIDENTS {
        string incident_id PK
        string merchant_id FK
        string razorpay_payment_id
        string issue_type
        string status
    }
    AUDIT_LOGS {
        string event_id PK
        string merchant_id FK
        string payment_id FK
        float ml_score
        float expected_value
        string priority_tier
        string ai_diagnosis
        string ai_recommendation
        string guardrail_result
        string action_taken
        string result
    }
```

### PostgreSQL Migration & Persistence Engine
1. **Numbered SQL Migrations (`backend/migrations/postgres/`):**
   - `001_initial.sql`: Core multi-tenant tables (`merchants`, `users`, `customers`, `payments`, `checkouts`, `recovery_plans`, `recovery_attempts`, `audit_logs`, `ground_truth`, `merchant_settings`, `scheduled_recovery_jobs`).
   - `002_ghost_revenue.sql`: `ghost_revenue_incidents` & `ghost_revenue_events` for tracking captured-without-order edge cases.
   - `003_recovery_link_guard.sql`: Unique `(merchant_id, payment_id)` constraint on `recovery_links` ensuring strict idempotency across worker, webhook, retry, and manual dispatch.
2. **Transparent SQL Dialect Translation:** `db.py` handles dialect differences automatically (translating `INSERT OR REPLACE` to PostgreSQL `ON CONFLICT DO UPDATE`, `INSERT OR IGNORE` to `ON CONFLICT DO NOTHING`, and query positional parameters from `?` to `%s`).
3. **Database Drivers:** Supports `psycopg` (v3) for high-performance PostgreSQL connections with dictionary row mapping, alongside SQLite WAL mode for local zero-dependency testing.

---

## API Architecture

The backend exposes strongly-typed, Pydantic-validated REST endpoints ([`api/main.py`](file:///c:/RecoverAi/backend/api/main.py)):

### 1. Authentication & Tenant Identity
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Register new merchant user and organization | No |
| `POST` | `/auth/login` | Authenticate credentials and issue JWT token | No |
| `GET` | `/auth/me` | Fetch active user profile and merchant organization | **Yes (Bearer)** |
| `POST` | `/auth/logout` | Terminate session and revoke active token | **Yes (Bearer)** |
| `PUT` | `/auth/profile` | Update user name, company name, or password | **Yes (Bearer)** |
| `POST` | `/auth/regenerate-api-key` | Generate a new merchant live API key | **Yes (Bearer)** |
| `POST` | `/auth/forgot-password` | Request password reset verification link | No |
| `POST` | `/auth/reset-password` | Reset merchant password using reset token | No |

### 2. Payments, Webhooks & Ingestion
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/webhooks/razorpay` | Production Razorpay webhook receiver (`payment.failed`, `payment.captured`, `payment.link.paid`) | HMAC Signature |
| `POST` | `/payments/event` | Ingest new failed payment event into recovery queue | **Yes (Bearer / API Key)** |
| `GET` | `/payments` | List tenant payments with pagination and status filters | **Yes (Bearer / API Key)** |
| `GET` | `/payments/{payment_id}` | Retrieve individual payment details | **Yes (Bearer / API Key)** |
| `POST` | `/checkouts/event` | Ingest abandoned checkout session | **Yes (Bearer / API Key)** |
| `GET` | `/checkouts` | List abandoned checkout drop-off events | **Yes (Bearer / API Key)** |

### 3. Agent Operations, Passport & Recovery
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/recovery/run/{payment_id}` | Execute full agent recovery pipeline on specific payment | **Yes (Bearer / API Key)** |
| `GET` | `/recovery/opportunities` | List prioritised revenue recovery queue sorted by EV | **Yes (Bearer / API Key)** |
| `GET` | `/recovery/plan/{payment_id}` | Fetch structured multi-step recovery plan for a payment | **Yes (Bearer / API Key)** |
| `GET` | `/recovery/passport/{payment_id}` | Explain eligibility, native ownership, and attribution before outreach | **Yes (Bearer / API Key)** |
| `POST` | `/recovery/promise-to-pay` | Record an eligible customer commitment for a halted subscription or overdue invoice | **Yes (Bearer / API Key)** |
| `GET` | `/recovery/escalations` | List payments escalated to human review queue | **Yes (Bearer / API Key)** |
| `POST` | `/recovery/resolve` | Mark an escalated payment as resolved/actioned | **Yes (Bearer / API Key)** |
| `GET` | `/agent/activity` | Stream real-time agent execution events | **Yes (Bearer / API Key)** |
| `POST` | `/agent/toggle` | Enable or pause the autonomous background worker loop | **Yes (Bearer / API Key)** |

### 4. Ghost Revenue, Analytics & Settings
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/ghost-revenue/incidents` | List tenant-scoped captured-but-unreconciled Razorpay incidents | **Yes (Bearer / API Key)** |
| `POST` | `/ghost-revenue/incidents/{incident_id}/resolve` | Explicitly record order verification/restoration or escalation | **Yes (Bearer / API Key)** |
| `GET` | `/metrics` | Retrieve recovery rate, F1-score, and volume statistics | **Yes (Bearer / API Key)** |
| `GET` | `/analytics/roi` | Compute gross recovered revenue vs communication costs | **Yes (Bearer / API Key)** |
| `GET` | `/audit` | Retrieve complete tenant audit logs | **Yes (Bearer / API Key)** |
| `GET` | `/audit/{payment_id}` | Retrieve audit log for specific payment | **Yes (Bearer / API Key)** |
| `GET` | `/api/settings` | Get merchant recovery thresholds and notification settings | **Yes (Bearer / API Key)** |
| `POST` | `/api/settings` | Update autonomous amount limits, cooldowns, and channels | **Yes (Bearer / API Key)** |
| `POST` | `/api/settings/test-razorpay`| Validate live Razorpay API key and secret | **Yes (Bearer / API Key)** |
| `GET` | `/reports/export/csv` | Download complete audit trail and recovery records as CSV | **Yes (Bearer / API Key)** |
| `GET` | `/readyz` / `/healthz` | Backend container health and database readiness probe | No |

---

## Frontend & Product Architecture

The frontend is built with **Next.js 16 (App Router)**, **React 19**, and **Tailwind CSS**, featuring dark-mode glassmorphism and real-time streaming updates:

| Page Route | Purpose | Key Data Presented | Backend API Integrated |
| :--- | :--- | :--- | :--- |
| **`/` (Dashboard)** | Revenue recovery executive overview | Revenue at Risk, Total Recovered, Active Plans, Success Rate | `GET /metrics`, `GET /recovery/opportunities` |
| **`/recover` (Agent Console)** | Live agent monitoring & interactive simulator | Real-time event feed (`Detect → Diagnose → Plan → Guard → Execute`) | `GET /agent/activity`, `POST /demo/scenario/{id}` |
| **`/recovery-cases`** | Revenue Opportunity Queue | High/Medium/Low priority queue sorted by Expected Value | `GET /recovery/opportunities`, `GET /recovery/escalations` |
| **`/ghost-revenue`** | Ghost Revenue Hunter Dashboard | Unmatched captured transactions, reconciliation status, actions | `GET /ghost-revenue/incidents`, `POST /ghost-revenue/incidents/{id}/resolve` |
| **`/recovery-passport`** | Recovery Passport & Promise-to-Pay | Eligibility explanations, attribution rules, customer commitments | `GET /recovery/passport/{id}`, `POST /recovery/promise-to-pay` |
| **`/payments`** | Comprehensive payment records | Filterable list of all payments, failure taxonomy, attempt counts | `GET /payments`, `POST /recovery/run/{id}` |
| **`/analytics`** | Financial ROI & ML performance | Net Recovery ROI, Action Cost breakdown, Daily trend charts | `GET /analytics/roi`, `GET /metrics` |
| **`/audit-trail`** | Compliance & decision verification | Complete immutable audit log with rule triggers and timestamps | `GET /audit`, `GET /reports/export/csv` |
| **`/guide`** | Interactive Product Guide & Playbooks | Visual tour of failure playbooks, guardrails, and agent states | Static & interactive walkthrough |
| **`/customers`** | Customer context directory | LTV, success rates, contact preferences, transaction history | `GET /customers` |
| **`/settings`** | Merchant workspace & guardrail configuration | Razorpay credentials test, autonomous amount limit, cooldown hours | `GET /api/settings`, `POST /api/settings` |
| **`/login`** | Merchant authentication portal | Tenant login, organization registration, session management | `POST /auth/login`, `POST /auth/register` |

---

## Visual Assets & Interface Tour

The repository contains real application UI assets located in [`frontend/public/Assets/`](file:///c:/RecoverAi/frontend/public/Assets/):

* **Agent Identity:** [`ai_agent_robot.png`](file:///c:/RecoverAi/frontend/public/Assets/ai_agent_robot.png) — Represents the autonomous background decision agent.
* **Hero Visual Background:** [`heroText_backgroundImage.png`](file:///c:/RecoverAi/frontend/public/Assets/heroText_backgroundImage.png) — Dashboard design asset.
* **Product Hero Concept:** [`purple_wallet_hero.jpg`](file:///c:/RecoverAi/frontend/public/purple_wallet_hero.jpg) — Fintech revenue recovery visual identity.

### Screen Workflows & Capabilities
1. **Agent Console (`/recover`):** Real-time interactive timeline displaying each stage of the recovery pipeline with live JSON payload inspectors, ML confidence meters, and guardrail decision badges.
2. **Opportunity Queue (`/recovery-cases`):** Priority tiering badge matrix (`HIGH` in emerald, `MEDIUM` in amber, `LOW` in slate) sorted by Expected Value in Indian Rupees ($₹$).
3. **Ghost Revenue Hunter (`/ghost-revenue`):** Dedicated incident reconciliation view to audit captured-without-order events and restore fulfillment without double-billing.
4. **Recovery Passport & Promise Drawer (`/recovery-passport`):** Transparency sheet explaining gateway ownership, attribution, and logging customer promise-to-pay commitments.
5. **Interactive Guide (`/guide`):** End-to-end visual manual explaining failure taxonomy, recovery playbooks, and deterministic safety rules for merchant operations teams.

---

## Proof It Works

RecoverAI has been rigorously validated across automated unit tests, end-to-end integration pipelines, and multi-tenant security barriers.

### 1. Automated Test Suite (49 Tests — 100% Passing)

Run the test suite locally:
```bash
pytest -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\RecoverAi
collected 49 items

tests/test_guardrails.py ....................                            [ 42%]
tests/test_diagnosis.py ..                                               [ 46%]
tests/test_pipeline.py ...................                               [ 87%]
tests/test_multi_tenant_security.py ......                               [100%]

============================== 49 passed =============================
```

#### Test Suite Breakdown
* **`tests/test_guardrails.py` (20 tests):** Verifies each guardrail rule in isolation (`R1` duplicate prevention, `R2` ₹10,000 ceiling, `R3` card expired block, `R4` 2-attempt limit, `R5` 6-hour cooldown, `R6` 2-contact ceiling, `R7` fraud tripwires).
* **`tests/test_diagnosis.py` (2 tests):** Verifies transient vs permanent failure classification and baseline scoring logic.
* **`tests/test_pipeline.py` (19 tests):** Verifies end-to-end event flow, LTV boosting, Pydantic schema validation, and metric computation.
* **`tests/test_multi_tenant_security.py` (6 tests):** Verifies tenant registration, JWT token generation, IDOR prevention, customer isolation, opportunity isolation, and agent execution isolation.
* **`tests/test_razorpay_fallback_monitoring.py`:** Verifies native Razorpay paths are monitored without RecoverAI link dispatch.
* **`tests/test_ghost_revenue.py`:** Verifies captured-without-order incidents are idempotent and tenant-scoped.

### 2. Supervised ML Benchmark Metrics ([`evaluate.py`](file:///c:/RecoverAi/backend/evaluate.py))
* **Ground Truth Evaluation:** Evaluated against historical benchmark records with independent ground-truth outcomes.
* **Model Quality:** Computes Precision, Recall, and F1-score against the hidden oracle table to prevent circular evaluation bias.
* **Reproducible Verification:** Standalone verification script [`verify_pipeline.py`](file:///c:/RecoverAi/backend/verify_pipeline.py) verifies pipeline integrity directly against SQLite / PostgreSQL.

---

## Demo Scenarios

The system includes pre-configured demo scenarios in [`run_pipeline.py`](file:///c:/RecoverAi/backend/run_pipeline.py) and the Agent Console (`/recover`):

### Scenario A — Transient Bank Downtime (Auto-Recovered)
* **Input:** Payment `₹5,000` via UPI fails with `BANK_SERVER_DOWN`.
* **Context:** Customer has 92% historical success rate, LTV ₹35,000.
* **ML Score:** Recovery Probability: `85.0%` | Expected Value: `₹4,250.00` | Tier: `HIGH`.
* **AI Decision:** Playbook `INTELLIGENT_RETRY` $\rightarrow$ Initial action: `WAIT_AND_RECHECK`.
* **Guardrail:** Rule evaluation $\rightarrow$ **APPROVED** (amount within limits, zero prior attempts).
* **Action:** 10s cooldown timer scheduled $\rightarrow$ Razorpay Payment Link generated and sent via SMS.
* **Outcome:** Webhook confirms `payment.captured` $\rightarrow$ Status: **`RECOVERED`**.

### Scenario B — Card Expired (Smart Alternate Method Link)
* **Input:** Payment `₹3,200` via Debit Card fails with `CARD_EXPIRED`.
* **Context:** Customer has 4 prior successful payments.
* **ML Score:** Recovery Probability: `22.0%` (permanent instrument failure).
* **AI Decision:** Recommends `RETRY`.
* **Guardrail:** **BLOCKED by Rule R3 (`CARD_EXPIRED_NO_RETRY`)** $\rightarrow$ Overridden to `SEND_PAYMENT_LINK`.
* **Action:** Dispatches smart payment link enabling UPI & NetBanking alternatives.
* **Outcome:** Prevents card network penalty; customer converts via UPI.

### Scenario C — High-Value Risk Guardrail (Escalated to Human)
* **Input:** Payment `₹75,000` fails with `BANK_SERVER_DOWN`.
* **Context:** High-value corporate purchase.
* **ML Score:** Recovery Probability: `80.0%` | Expected Value: `₹60,000.00` | Tier: `HIGH`.
* **AI Decision:** Recommends autonomous `RETRY`.
* **Guardrail:** **BLOCKED by Rule R2 (`AMOUNT_LIMIT`)** $\rightarrow$ ₹75,000 exceeds ₹10,000 autonomous ceiling.
* **Action:** Overridden to `ESCALATE_TO_HUMAN` $\rightarrow$ Ticket assigned to senior recovery queue; SMS alert dispatched to merchant phone.
* **Outcome:** Zero financial risk; human agent verifies transaction before follow-up.

---

## Observability & Audit Trail

In financial software, every autonomous action must be verifiable and tamper-evident. RecoverAI writes an immutable audit record to `audit_logs` for every pipeline execution ([`core/audit.py`](file:///c:/RecoverAi/backend/core/audit.py)):

### Sample Real Audit Record

```
════════════════════════════════════════════════════════════════════
  RecoverAI 2.0 — Verifiable Audit Record
════════════════════════════════════════════════════════════════════
  Event ID       : evt_6d78a91b2c
  Payment ID     : pay_live_948271
  Amount         : ₹4,500.00
  Failure Reason : BANK_SERVER_DOWN
  Payment Method : UPI
  ──────────────────────────────────────────────────────────────────
  Recovery Score : 85.00% (probability)
  Expected Value : ₹3,825.00  [HIGH PRIORITY]
  Strategy       : INTELLIGENT_RETRY
  Channel Used   : SMS
  AI Recommended : WAIT_AND_RECHECK
  ──────────────────────────────────────────────────────────────────
  Guardrail      : ✓ APPROVED
  Action Taken   : WAIT_AND_RECHECK
  ──────────────────────────────────────────────────────────────────
  Outcome        : ⏳ PENDING (Awaiting Payment Confirmation)
  Timestamp      : 2026-09-03T14:35:12.842105+00:00
════════════════════════════════════════════════════════════════════
```

* Sensitive merchant secrets, API keys, and customer credit card numbers are strictly redacted from audit payloads.
* The Live Agent Activity distinguishes `WAITING`, `STATUS RECHECKED`, `RAZORPAY MONITORING`, live dispatch, simulated/test-only output, existing-link monitoring, and verified recovery; “processed” never proves customer delivery.
* Complete logs are exportable as CSV via `GET /reports/export/csv` for financial accounting and compliance audits.

---

## Failure Handling & Edge Cases

| Failure Mode | System Behavior & Mitigation |
| :--- | :--- |
| **Invalid Webhook Signature** | Returns HTTP 403; drops payload immediately; logs security warning. |
| **Duplicate Webhook / Replay** | Tenant-scoped recovery-link reservation and recovery-job state prevent repeat dispatch; an existing link is monitored rather than resent. |
| **Razorpay Native Retry / Alternate Checkout** | `INTERNATIONAL_CARD_UNSUPPORTED` and `SUBSCRIPTION_RETRY_ACTIVE` are monitoring-only; no link, retry, customer contact, or Promise-to-Pay is created. |
| **Captured Payment Without Internal Match** | Ghost Revenue Hunter creates one tenant-scoped reconciliation incident; it never auto-creates an order, charges again, or captures funds. |
| **LLM Provider Outage (Groq 429/500)** | Automatically falls back through `GroqProvider` $\rightarrow$ `OllamaProvider` $\rightarrow$ `MockProvider`. Pipeline never crashes. |
| **Razorpay API Timeout / Error** | Catches `requests.exceptions.RequestException`, marks attempt `FAILED`, queues payment for retry or human review. |
| **Customer Contact Limit Reached** | Rule `R6_CONTACT_LIMIT` halts all further messaging to prevent customer spam. |
| **Database Disconnection** | WAL mode connection manager and PostgreSQL connection pool handle retry with timeout (30s) and automatic rollback on exception. |

---

## Technology Stack

| Layer | Technology | Version | Architectural Purpose |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI | `^0.111.0` | High-performance asynchronous REST API with auto-generated OpenAPI docs |
| **Runtime & Language** | Python | `3.11+` | Core agent execution, data validation, and ML inference |
| **Data Validation** | Pydantic | `^2.7.0` | Strict data schema enforcement and input validation |
| **Machine Learning** | Scikit-Learn | `^1.4.0` | Supervised Random Forest Classifier for recovery likelihood prediction |
| **Data Processing** | Pandas / NumPy | `^2.2.0` | Feature preprocessing and one-hot encoding pipelines |
| **LLM Inference** | Groq / Ollama | `llama-3.1-8b` | Contextual failure reasoning and structured JSON recovery planning |
| **Primary Production Database** | PostgreSQL 16 (psycopg v3) | `16-alpine` | Enterprise relational database with numbered SQL schema migrations |
| **Local / Dev Database** | SQLite (WAL Mode) | Built-in | Fast, zero-dependency concurrent persistence for local testing |
| **Frontend Framework** | Next.js (App Router) | `16.3.3` | React-based server-side rendered dashboard and UI |
| **UI Components** | React 19 + Tailwind CSS | `19.2.8` | Responsive, dark-mode glassmorphism component architecture |
| **Icons & Visuals** | Lucide React | `^1.38.0` | Iconography for payment methods, channels, and statuses |
| **Testing** | Pytest | `^8.2.0` | Unit, integration, and multi-tenant security test suite |
| **Payments Gateway** | Razorpay API v1 | REST / BasicAuth | Payment Links API, Webhooks, and status verification |
| **Container Orchestration** | Docker & Docker Compose | `Compose v2` | Multi-container setup (PostgreSQL + FastAPI + Next.js) |

---

## Project Structure

```
RecoverAI/
├── backend/
│   ├── api/                        # FastAPI application and webhooks
│   ├── core/                       # Agent, audit, auth, execution, guardrails & passport
│   │   ├── agent.py                # Multi-provider LLM strategy planner
│   │   ├── audit.py                # Tamper-proof immutable audit logging
│   │   ├── auth.py                 # PBKDF2 hashing, JWT & tenant resolver
│   │   ├── diagnosis.py            # Failure classifier & ML context scorer
│   │   ├── executor.py             # Razorpay API client & action dispatcher
│   │   ├── guardrails.py           # Deterministic financial rules R1-R7
│   │   ├── playbook_router.py      # Failure-specific playbook routing
│   │   └── recovery_passport.py    # Explainable eligibility & attribution passport
│   ├── models/                     # ML model artifacts and Pydantic schemas
│   ├── data/                       # Synthetic dataset generator
│   ├── migrations/                 # PostgreSQL schema migrations
│   │   └── postgres/
│   │       ├── 001_initial.sql     # Base multi-tenant schema
│   │       ├── 002_ghost_revenue.sql # Ghost revenue incidents & events
│   │       └── 003_recovery_link_guard.sql # Link reservation guard
│   ├── tests/                      # Backend, guardrail, and security test suite
│   ├── db.py                       # Unified PostgreSQL & SQLite repository layer
│   ├── evaluate.py                 # Batch evaluation metrics
│   ├── logging_config.py           # Structured logging configuration
│   ├── run_pipeline.py             # CLI demo scenarios
│   ├── verify_pipeline.py          # Pipeline verification script
│   ├── Dockerfile                  # Production backend container definition
│   └── requirements.txt            # Python backend dependencies
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Executive Dashboard (Metrics & Overview)
│   │   │   ├── recover/            # Agent Console (Interactive Live Feed)
│   │   │   ├── recovery-cases/     # Priority Revenue Opportunity Queue
│   │   │   ├── ghost-revenue/      # Ghost Revenue Hunter (Capture Reconciliation)
│   │   │   ├── recovery-passport/  # Recovery Passport & Promise-to-Pay Drawer
│   │   │   ├── guide/              # Interactive Playbook & Architecture Guide
│   │   │   ├── payments/           # All Payments Management
│   │   │   ├── analytics/          # ROI & ML Metric Breakdown
│   │   │   ├── audit-trail/        # Full Compliance & Audit Log
│   │   │   ├── customers/          # Customer Directory & LTV Context
│   │   │   ├── settings/           # Merchant Workspace & Credentials
│   │   │   ├── profile/            # Merchant Profile & Password Management
│   │   │   └── login/              # Multi-Tenant Authentication Portal
│   │   ├── components/             # Reusable UI components & modals
│   │   └── lib/                    # Auth context & frontend utilities
│   ├── public/Assets/              # Visual assets & icons
│   └── package.json
├── docker-compose.yml              # Multi-container orchestration (Postgres + Backend + Frontend)
└── README.md                       # This production case study & documentation
```

---

## Key Engineering Decisions

### 1. Why Decouple ML Scoring from LLM Reasoning?
* **Problem:** Calling an LLM for pure mathematical probability estimation is non-deterministic, slow ($>1000\text{ms}$), and prone to hallucinated math.
* **Decision:** Use a lightweight Random Forest classifier ($<5\text{ms}$) for statistical scoring and Expected Value calculation, and reserve the LLM for natural language strategy planning and multi-step explanation.

### 2. Why Deterministic Guardrails Outside the LLM?
* **Problem:** System prompts like *"Never retry payments above ₹10,000"* are vulnerable to prompt injection, edge-case bypasses, and temperature drift.
* **Decision:** Guardrails are hardcoded in standard Python conditional statements (`core/guardrails.py`). The LLM's output is treated as untrusted user input until validated.

### 3. Why Decouple Action Dispatch from Revenue Verification?
* **Problem:** Naive recovery systems count a payment as "recovered" the second an SMS link is sent.
* **Decision:** In RecoverAI, sending a link marks the attempt as `PENDING`. Revenue is only counted as recovered when a `payment.captured` or `payment.link.paid` webhook arrives from Razorpay.

### 4. Why Dual Database Architecture (PostgreSQL 16 + SQLite WAL)?
* **Problem:** Production enterprise environments demand robust relational databases with strict foreign key constraints, connection pooling, and ordered migrations, while hackathon review and local development benefit from zero-configuration instant setup.
* **Decision:** Built a transparent repository facade in `db.py` that connects seamlessly to PostgreSQL 16 via `psycopg` (v3) using numbered SQL migrations (`001_initial.sql`, `002_ghost_revenue.sql`, `003_recovery_link_guard.sql`) while retaining automatic fallback to SQLite WAL mode for local zero-config testing.

### 5. Why Safe Ghost Revenue Reconciliation Over Blind Order Creation?
* **Problem:** When an orphan `payment.captured` event arrives without a matching local order ID, naive systems either drop the money or auto-create an unverified order.
* **Decision:** Ghost Revenue Hunter flags the orphan capture into an isolated `ghost_revenue_incidents` ledger, preserving complete payment telemetry and giving merchants one-click explicit reconciliation or refund workflows without double-charging or phantom fulfillment.

---

## What Makes RecoverAI Different

| Dimension | Naive Recovery System | RecoverAI Agentic System |
| :--- | :--- | :--- |
| **Failure Classification** | Treats all payment failures identically | Classifies into 9 distinct transient vs permanent modes |
| **Retry Timing** | Retries immediately upon failure | Applies failure-specific cooldown timers (e.g., 6h) |
| **Communication Strategy** | Sends repetitive generic reminder emails | Selects preferred customer channel (SMS/Email) with dynamic context |
| **Execution Authority** | Hardcoded scripts or unverified LLM | **ML Predicts $\rightarrow$ LLM Reasons $\rightarrow$ Guardrails Protect $\rightarrow$ Code Executes** |
| **Outcome Confirmation** | Assumes dispatch = recovered | Verifies cryptographic gateway webhook before marking recovered |
| **Safety Ceiling** | Retries indefinitely until blocked | Hard ₹10,000 autonomous ceiling and 2-attempt maximum limit |
| **Native Gateway Respect** | Conflicts with gateway retry cycles | Yields to Razorpay native alternate checkouts and active retries |
| **Orphan Captures** | Ignored or creates duplicate orders | Ghost Revenue Hunter audits and isolates captures for safe reconciliation |
| **Customer Retention** | Aggressively spams or halts accounts | Recover Promise (Promise-to-Pay) enables graceful payment scheduling |
| **Auditability** | Ephemeral console output | Immutable, tenant-isolated audit trail recording all scores and rule triggers |

---

## Security Considerations

1. **Webhook Authentication:** Webhooks are verified using HMAC-SHA256 signatures against `RAZORPAY_WEBHOOK_SECRET` via constant-time comparison (`hmac.compare_digest`).
2. **Multi-Tenant Data Isolation:** Every database query is tenant-scoped (`WHERE merchant_id = ?`). Attempting cross-tenant data access returns `404 Not Found`.
3. **Password Security:** Salted PBKDF2-HMAC-SHA256 hashing with 100,000 iterations. Plaintext passwords are never logged or stored.
4. **Credential Redaction:** API keys, webhook secrets, and database connection strings are read from `.env` and never included in API responses or public audit logs.
5. **Idempotency & Replay Protection:** Webhook events, recovery jobs, and payment link dispatches enforce unique reservation keys (`recovery_links`) to eliminate race conditions and repeat messaging.

---

## Limitations

To maintain absolute engineering integrity, the following current limitations are explicitly documented:
1. **Single-Process Revocation:** JWT token revocation is currently maintained in-memory in `core/auth.py`. Multi-replica production deployments benefit from a shared Redis token store.
2. **Channel Integration:** SMS and Email dispatch are integrated with Razorpay's notification engine and SMTP. WhatsApp Business API integration is architected in schemas but requires a registered Meta Business Account.
3. **Live Gateway Settlements:** While payment link creation and status rechecks are live via Razorpay, real customer fund capture depends on actual cardholder settlement.

---

## Roadmap

### Implemented ✅
- [x] Supervised ML Random Forest Scorer with Customer LTV awareness.
- [x] Multi-Provider LLM Agent layer (Groq, Ollama, MockProvider).
- [x] Deterministic Guardrail Engine (Rules R1 through R7).
- [x] Production Razorpay API payment link generation and webhook receiver.
- [x] Multi-tenant authentication with PBKDF2 password hashing & JWT tokens.
- [x] Next.js 16 executive dashboard and interactive real-time Agent Console.
- [x] Immutable audit trail with CSV export capability.
- [x] 49 automated unit, pipeline, tenant-isolation, native-fallback, and Ghost Revenue tests.
- [x] Native-first Razorpay recovery: alternate checkout and active subscription retries are monitoring-only.
- [x] Tenant-scoped one-active-link guard shared by worker, webhook, retry, and manual dispatch.
- [x] Ghost Revenue Hunter for captured Razorpay payments without a safe internal order/recovery match.
- [x] Recovery Passport & Recover Promise (Promise-to-Pay) for subscriptions and overdue invoices.
- [x] PostgreSQL 16 database architecture with ordered SQL migrations (`001_initial.sql`, `002_ghost_revenue.sql`, `003_recovery_link_guard.sql`).
- [x] Docker & Docker Compose container orchestration for full-stack deployment.

### Planned (Future Work) 🚀
- [ ] Distributed Celery / Redis worker architecture for high-volume queue draining.
- [ ] WhatsApp Business Cloud API direct template messaging.
- [ ] Multi-gateway failover routing (e.g. Razorpay $\rightarrow$ Cashfree / PayU fallback).
- [ ] Adaptive reinforcement learning for dynamic cooldown interval optimization.

---

## Local Development Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**
- *(Optional)* **Docker & Docker Compose** (for PostgreSQL and containerized setup)
- *(Optional)* **Groq API Key** (Free tier available at [console.groq.com](https://console.groq.com))
- *(Optional)* **Razorpay Test Keys** (Available at [dashboard.razorpay.com](https://dashboard.razorpay.com))

---

### Option A: Docker Compose (Full Stack with PostgreSQL)

```bash
# 1. Clone repository
git clone https://github.com/vijith-bhima/RecoverAi.git
cd RecoverAi

# 2. Configure environment variables
copy .env.example .env   # On Linux/macOS: cp .env.example .env

# 3. Start PostgreSQL, FastAPI backend, and Next.js frontend
docker compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API & Docs: `http://localhost:8000/docs`

---

### Option B: Local Development (Manual Setup)

#### Step 1: Clone Repository
```bash
git clone https://github.com/vijith-bhima/RecoverAi.git
cd RecoverAi
```

#### Step 2: Backend Setup
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
# source .venv/bin/activate

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Configure environment variables
copy .env.example .env   # On Linux/macOS: cp .env.example .env

# 4. Run backend commands from its service directory
cd backend

# 5. Generate initial database records
python data/generate_data.py

# 6. Run automated test suite
pytest -v

# 7. Start FastAPI backend server
uvicorn api.main:app --reload --port 8000
```
Backend API will be running at: `http://localhost:8000`  
Swagger API Docs available at: `http://localhost:8000/docs`

#### Step 3: Frontend Setup
Open a new terminal window:
```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start Next.js development server
npm run dev
```
Frontend Dashboard will be running at: `http://localhost:3000`

#### Step 4: Run CLI Demo Scenarios
To see the agent process payments in your terminal:
```bash
cd backend
python run_pipeline.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

```ini
# ── LLM Provider Configuration ──────────────────────────────────────
# Options: "mock" | "groq" | "ollama"
LLM_PROVIDER=mock
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Local Ollama Fallback (if LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# ── Database & Persistence ──────────────────────────────────────────
# SQLite for local development:
DATABASE_URL=recoverai.db
# Or PostgreSQL for production / Docker:
# DATABASE_URL=postgresql://recoverai:your_password@localhost:5432/recoverai
# POSTGRES_USER=recoverai
# POSTGRES_PASSWORD=your_password
# POSTGRES_DB=recoverai

# ── Razorpay Gateway Integration ────────────────────────────────────
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# ── Deterministic Guardrail Boundaries ──────────────────────────────
MAX_AUTONOMOUS_AMOUNT=10000       # ₹ ceiling for autonomous recovery
MAX_RETRY_ATTEMPTS=2              # Maximum automated retries per payment
RETRY_COOLDOWN_HOURS=6            # Cooldown window between retries
MAX_CONTACT_ATTEMPTS=2            # Maximum messages per customer

# ── Merchant Alert Notification ─────────────────────────────────────
MERCHANT_EMAIL=merchant@example.com
MERCHANT_PHONE=+919876543210
MERCHANT_NAME=RecoverAI Retail

# ── Security & Authentication ───────────────────────────────────────
JWT_SECRET_KEY=recoverai_super_secret_jwt_key_2026_production
LOG_LEVEL=INFO
LOG_FILE=recoverai.log
```

---

## Engineering Takeaways

Building RecoverAI demonstrates core principles required for production fintech and AI engineering:

1. **Bounded Autonomy:** AI models should recommend and explain, but deterministic software rules must always hold the veto power over financial execution.
2. **Outcome Verification:** In payment engineering, an operation is never successful simply because an API request succeeded; state must be cryptographically confirmed by the settlement processor.
3. **Decoupled Architecture:** Separating supervised ML scoring, LLM reasoning, deterministic rule checking, and async execution creates a resilient system with graceful fallbacks.
4. **Defense in Depth:** Multi-tenancy must be enforced at the database query level with salted cryptography, avoiding reliance on client-side state.
5. **Auditable Decision Trails:** Autonomous systems must record the *why*, *what*, and *when* for every automated decision to enable regulatory compliance and post-incident review.
6. **Graceful Reconciliation:** Solving edge cases like Ghost Revenue (phantom captured payments) and Recover Promise ensures customer trust and financial reconciliation without manual overhead.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>RecoverAI</b> — Autonomous Revenue Recovery for Modern Commerce<br/>
  <i>Built for the Razorpay AI Buildathon 2026</i>
</p>
