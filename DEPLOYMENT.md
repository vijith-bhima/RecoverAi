# RecoverAI 2.0 — Production Ship & Deployment Guide

This guide outlines how to deploy RecoverAI 2.0 as a production revenue recovery service connected to live Razorpay webhooks and payment links.

---

## 📦 1. Pre-Flight Checklist

Ensure you have your production environment secrets ready:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Groq LLM API Key (fast inference) | `gsk_...` |
| `GROQ_MODEL` | Production LLM model | `llama-3.1-8b-instant` |
| `RAZORPAY_KEY_ID` | Razorpay Key ID | `rzp_live_...` |
| `RAZORPAY_KEY_SECRET` | Razorpay Key Secret | `...` |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signature secret | `...` |
| `MAX_AUTONOMOUS_AMOUNT` | Max ₹ amount AI can retry/charge without human review | `10000` |
| `MAX_RETRY_ATTEMPTS` | Bounded autonomy attempt limit | `2` |

---

## 🐳 2. One-Command Deployment (Docker Compose)

Create the production environment file first. Do not copy an existing local
database or `.env` file into source control:

```bash
cp .env.example .env
```

Set every placeholder secret in `.env`, set `RECOVERAI_ENVIRONMENT=production`,
and configure the browser-reachable API URL before starting the stack:

```env
NEXT_PUBLIC_API_URL=https://api.example.com
APP_BASE_URL=https://app.example.com
CORS_ORIGINS=https://app.example.com
```

Launch the full stack (FastAPI Backend + Next.js Frontend + SQLite with Volume Persistence):

```bash
docker compose up --build -d
```

- **Backend API & Swagger**: `http://localhost:8000/docs`
- **Frontend Dashboard**: `http://localhost:3000`
- **Health Check**: `http://localhost:8000/health`

The SQLite database and application log are stored in the named
`recoverai-data` volume at `/app/data`; application code remains in the image
and is not shadowed by the volume mount.

### Production operating constraints

Run exactly one backend replica with the included SQLite and in-process
recovery scheduler. The container is deliberately configured with one Uvicorn
worker so payment processing cannot run twice. Before horizontal scaling,
migrate persistence to PostgreSQL and move scheduled recovery work to a shared
queue/worker service (for example, Redis-backed workers). Configure a managed
TLS reverse proxy in front of both services and expose only the frontend and
the authenticated webhook route publicly.

---

## ⚡ 3. Deploying to Cloud Providers

### Buildathon HTTPS webhook (Render)

This repository includes `render.yaml` for a temporary public backend. After
you push the repository to GitHub, open Render's **New → Blueprint** flow and
select that repository. Render builds `backend/Dockerfile` and assigns an HTTPS
URL such as `https://recoverai-api.onrender.com`.

In the Render service settings, add these secret environment variables before
enabling live Razorpay events:

```text
GROQ_API_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
APP_BASE_URL=https://your-frontend-url
PUBLIC_API_URL=https://your-render-service.onrender.com
CORS_ORIGINS=https://your-frontend-url
```

Use this exact webhook address in Razorpay:

```text
https://your-render-service.onrender.com/webhooks/razorpay?merchant_id=YOUR_MERCHANT_ID
```

Use Razorpay **Test Mode** for the buildathon. Render's free service sleeps
after 15 minutes of inactivity and its filesystem is ephemeral, so it is not
appropriate for live customer payment records.

### A. Deploy on Render / Railway
1. Push your repository to GitHub.
2. Create a new **Web Service** pointing to the repository.
3. Set the build command:
   - Backend: `pip install -r backend/requirements.txt`
   - Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - Set the backend service working directory to `backend`.
4. Set Environment Variables from `.env`.

### B. Deploy on Fly.io / AWS ECS
Use the provided [backend Dockerfile](C:/RecoverAi/backend/Dockerfile) and [frontend Dockerfile](C:/RecoverAi/frontend/Dockerfile).

---

## 🔗 4. Connecting Live Razorpay Webhooks

1. Go to **Razorpay Dashboard** $\rightarrow$ **Settings** $\rightarrow$ **Webhooks** $\rightarrow$ **Add New Webhook**.
2. **Webhook URL**: `https://<YOUR_DEPLOYED_DOMAIN>/webhooks/razorpay`
3. **Secret**: Enter the exact secret string defined in your `RAZORPAY_WEBHOOK_SECRET`.
4. **Active Events to Subscribe**:
   - `payment.failed` *(Triggers automated ML diagnosis, recovery plan generation, and safe execution)*
   - `payment.captured` *(Synchronizes recovered payments in real time)*
   - `payment_link.paid` *(Verifies payment link completions)*

---

## 🛡 5. Production Safety & Bounded Autonomy

- **Double-Debit Prevention**: Before retrying transient failures, the executor checks the gateway status to ensure no pending debit occurred.
- **Card Network Protection**: Expired cards are blocked from repeated retries and automatically rerouted to multi-method payment links (`SEND_PAYMENT_LINK`).
- **Autonomous Ceiling**: Any transaction above `MAX_AUTONOMOUS_AMOUNT` (₹10,000) is deterministically blocked from autonomous execution and escalated to the **Human Review Queue**.
- **Tamper-Proof Audit Trail**: Every decision, score, plan, and outcome is permanently committed to `audit_logs`.
