# RecoverAI project structure

RecoverAI is split into a deployable Python backend and a Next.js frontend.

```text
RecoverAi/
├── backend/                  # Python API, AI workflow, ML, and test suite
│   ├── api/                  # FastAPI routes and webhooks
│   ├── core/                 # AI agent workflow and business rules
│   │   ├── agent.py          # LLM strategy planning
│   │   ├── diagnosis.py      # Failure diagnosis and recovery scoring
│   │   ├── executor.py       # Bounded recovery actions
│   │   ├── guardrails.py     # Deterministic financial safety rules
│   │   ├── playbook_router.py # Failure-specific recovery playbooks
│   │   ├── audit.py          # Audit trail writer
│   │   └── auth.py           # Password hashing, JWT, tenant context
│   ├── models/               # ML assets and typed API schemas
│   ├── data/                 # Dataset generation utilities
│   ├── tests/                # Backend, security, guardrail, and pipeline tests
│   ├── db.py                 # Tenant-scoped persistence layer
│   ├── Dockerfile            # Backend container
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Next.js dashboard and authentication UI
│   ├── src/app/              # Pages: login, payments, recovery, settings, profile
│   ├── src/components/       # Reusable UI components
│   └── public/               # Browser-safe images and static assets
├── docker-compose.yml        # Local full-stack orchestration
├── .env.example              # Placeholder environment configuration
└── README.md                 # Project documentation
```

Run backend commands from `backend/`; this keeps the existing Python import
paths (`api`, `core`, and `models`) stable without polluting the repository root.

## Files that must never be pushed

- `.env` and any file containing API keys, JWT secrets, SMTP passwords, or webhook secrets
- `recoverai.db` and other database files containing customer/payment records
- `*.log`, `output/`, exports, and runtime reports
- `.venv/`, `frontend/node_modules/`, `frontend/.next/`, and Python caches
- `ngrok.yml`, tunnel credentials, private certificates, and deployment secrets

Commit `.env.example` only, with placeholder values.
