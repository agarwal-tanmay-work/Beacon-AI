<div align="center">

<img src="frontend/public/brand-logo.png" alt="Beacon AI" width="200"/>

# Beacon AI

### Anonymous Corruption Reporting, Powered by AI

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)

**Beacon AI** is a full-stack, production-grade platform that lets anyone safely and anonymously report corruption or workplace misconduct — guided by a conversational AI that collects structured evidence, generates a credibility score, and issues a cryptographic Case ID + Secret Key for anonymous case tracking.

</div>

---

## How It Works

```
 Reporter (Anonymous)           Beacon AI Backend                Admin Portal
 ─────────────────────          ──────────────────────           ─────────────────
 1. Opens /report               → Session created (UUID)
 2. Chats with AI               → Gemini 2.5 Flash collects:
    "Officer took a bribe"         • What happened
    "At the border post"           • Where & when
    "Yesterday at 3 PM"            • Who was involved
    "Officer Raj"                  • Evidence (optional)
                                   • Contact info (optional)
 3. Uploads evidence photo      → Stored in Supabase Storage
                                   AI performs forensic analysis
 4. Says "I'm done"             → Case ID + Secret Key issued
                                   Credibility scoring starts ───→ Score + breakdown
                                                                    visible to admin
 5. Saves Case ID +             → Returns to /track anytime        Admin posts updates
    Secret Key                     to check status
```

---

## Architecture

```mermaid
graph TB
    subgraph FE["Public Frontend (Next.js 16 + React 19)"]
        A["Landing Page<br/>Three.js · Framer Motion · tsParticles"]
        B["/report — AI Chat Interface"]
        C["/track — Case Status Lookup"]
    end

    subgraph BE["Backend API (FastAPI · Python 3.11 · Docker)"]
        D["POST /public/reports/create"]
        E["POST /public/reports/message"]
        F["POST /public/evidence/upload"]
        G["GET  /public/track"]
        H["Admin Routes /admin/*"]
    end

    subgraph AI["AI Layer (Google Gemini 2.5 Flash)"]
        I["LLM Agent — Conversational Intake"]
        J["Credibility Scorer<br/>Narrative · Evidence · Behavior"]
        K["Forensic Analysis<br/>OCR · Vision · Audio"]
    end

    subgraph DB["Data Layer (Supabase)"]
        L[("reports")]
        M[("report_conversations")]
        N[("report_state_tracking")]
        O[("beacon — Finalized Cases")]
        P[("evidence")]
        Q["Supabase Storage<br/>Files & Media"]
    end

    subgraph AP["Admin Portal (Next.js)"]
        R["Dashboard · Cases · Evidence · Updates"]
    end

    A --> B
    A --> C
    B -->|"Axios"| E
    E --> I
    I --> M
    I --> N
    F --> P
    F --> Q
    I -->|"on completion"| O
    O -.->|"background job"| J
    J --> K
    H --> R
    C --> G
    G --> O
```

---

## Features

| Feature | Description |
|---|---|
| **Anonymous by default** | No account required. Reporter identity is never stored or linked across cases. |
| **Conversational intake** | Gemini AI guides reporters through structured questions in natural prose — never robotic bullet points. |
| **Multi-format evidence** | Upload images, PDFs, audio files. Each gets forensic AI analysis (OCR, visual scene description). |
| **Credibility scoring** | Every case receives an AI score (0–100) across Narrative Consistency, Evidence Strength, and Behavioral Reliability. |
| **Case ID + Secret Key** | Cryptographic pair issued at submission. Both are required together to retrieve case status. Neither alone grants access. |
| **Admin portal** | Separate Next.js app with JWT auth for investigators to triage, score, and post case updates visible to the reporter. |
| **Background analysis** | Scoring runs asynchronously — reporter gets instant Case ID while analysis completes in the background. |
| **Race-condition safe** | Case ID generation retries up to 3 times on UniqueConstraint violations to handle concurrent submissions. |
| **Degraded mode startup** | If the DB is unreachable at startup, the app still binds its port (Render won't kill the service) and retries on each request. |

---

## Tech Stack

### Backend (`/backend`)

| Technology | Role |
|---|---|
| **FastAPI** | Async Python web framework, REST API, background tasks |
| **SQLAlchemy (async) + asyncpg** | Async PostgreSQL ORM |
| **Supabase PostgreSQL** | Primary relational database |
| **Supabase Storage** | File storage for evidence uploads |
| **Google Gemini 2.5 Flash** | Chat, evidence analysis, credibility scoring (direct REST via httpx) |
| **Passlib pbkdf2_sha256** | Secret key hashing |
| **Python-JOSE** | JWT generation and validation (admin auth) |
| **Alembic** | Database schema migrations |
| **Structlog** | Structured JSON logging |
| **Tesseract OCR + PyMuPDF** | Text extraction from images and PDFs |
| **OpenCV** | Image preprocessing |
| **dnspython** | Reliable DNS resolution (bypasses flaky libc resolver on Render) |
| **Docker (python:3.11-slim-bookworm)** | Containerized deployment |

### Frontend (`/frontend`)

| Technology | Role |
|---|---|
| **Next.js 16** | React framework with App Router |
| **React 19** | Component model |
| **Tailwind CSS** | Utility-first styling |
| **Framer Motion** | Page and component animations |
| **Three.js** | 3D fire sphere background effect |
| **tsParticles** | Particle sparkle effects |
| **Axios** | API client with request/response interceptors |
| **React Markdown + remark-gfm** | Renders AI responses as rich text |
| **Radix UI** | Accessible headless components |

### Admin Portal (`/admin-portal`)

| Technology | Role |
|---|---|
| **Next.js 16** | React framework |
| **Tailwind CSS** | Styling |
| **JWT auth** | Protected routes via `AuthGuard` component |

---

## Project Structure

```
Beacon-AI/
├── backend/                         # FastAPI application
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── public/
│   │   │   │   ├── reporting.py     # POST /create, POST /message
│   │   │   │   ├── evidence.py      # POST /evidence/upload
│   │   │   │   └── tracking.py      # GET /track
│   │   │   └── admin/
│   │   │       ├── auth.py          # POST /admin/auth/login
│   │   │       ├── reports.py       # GET/PATCH cases
│   │   │       ├── evidence.py      # Evidence viewer
│   │   │       └── updates.py       # POST case updates
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings (reads env vars)
│   │   │   ├── exceptions.py        # Global exception handlers + traceback logging
│   │   │   ├── security.py          # JWT + bcrypt
│   │   │   └── scoring_logic.py     # Credibility scoring criteria
│   │   ├── db/
│   │   │   ├── session.py           # Async SQLAlchemy engine (pool_size=5)
│   │   │   └── init_db.py           # Startup table creation with 10s timeout
│   │   ├── models/
│   │   │   ├── report.py            # Report, ReportConversation, StateTracking, Evidence
│   │   │   └── beacon.py            # Finalized case (beacon table)
│   │   ├── services/
│   │   │   ├── report_engine.py     # Core message processing orchestrator
│   │   │   ├── llm_agent.py         # Gemini conversation handler + state extraction
│   │   │   ├── ai_service.py        # Gemini REST API wrapper (httpx)
│   │   │   ├── scoring_service.py   # Background credibility analysis
│   │   │   ├── storage_service.py   # Supabase Storage upload/download
│   │   │   └── evidence_processor.py # OCR, image analysis pipeline
│   │   └── main.py                  # FastAPI app, CORS, lifespan, route mounts
│   ├── Dockerfile                   # python:3.11-slim-bookworm, PORT env var support
│   ├── requirements.txt
│   └── run_server.py                # Local dev entry point (reads PORT env var)
│
├── frontend/                        # Reporter-facing Next.js app
│   └── src/
│       ├── app/
│       │   ├── page.tsx             # Landing page (Fire Sphere + Sparkles + FAQ)
│       │   ├── report/page.tsx      # AI chat reporting interface
│       │   └── track/page.tsx       # Case status lookup
│       └── components/
│           ├── features/
│           │   ├── ChatInterface.tsx # Core chat UI with message bubbles
│           │   └── Hero.tsx
│           └── ui/                  # fire-sphere, sparkles, anime-navbar, etc.
│
└── admin-portal/                    # Investigator-facing Next.js app
    └── src/app/
        ├── login/                   # JWT login
        ├── pending/                 # Unreviewed cases
        ├── ongoing/                 # Active investigations
        ├── completed/               # Closed cases
        ├── evidence/                # Evidence browser
        └── case/[id]/               # Case detail + update poster
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Supabase](https://supabase.com) project (free tier works)
- A [Google AI Studio](https://aistudio.google.com) Gemini API key

### 1. Clone

```bash
git clone https://github.com/agarwal-tanmay-work/Beacon-AI.git
cd Beacon-AI
```

### 2. Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp backend_config.env.example backend_config.env
# Edit backend_config.env with your credentials (see table below)

python run_server.py
# API docs: http://localhost:8000/api/v1/docs
```

### 3. Frontend

```bash
cd frontend
npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
# http://localhost:3000
```

### 4. Admin Portal

```bash
cd admin-portal
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
# http://localhost:3001
```

---

## Environment Variables

### Backend (`backend/backend_config.env`)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Random 64-char string for JWT signing |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SUPABASE_URL` | Yes | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | Yes | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key (file storage) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `CORS_ORIGINS` | Yes | `["https://your-frontend.com"]` |
| `ENVIRONMENT` | No | `development` or `production` (default: `production`) |
| `ADMIN_PASSWORD_HASH` | No | bcrypt hash of admin password |

### Frontend / Admin Portal (`.env.local` — local dev only)

| Variable | Description |
|---|---|
| `BACKEND_URL` | Backend base URL for local dev, e.g. `http://localhost:8000` |

> `NEXT_PUBLIC_API_URL` is no longer needed. The Next.js rewrite proxy reads the server-side `BACKEND_URL` variable and forwards `/api/v1/*` requests automatically. This also means the backend URL is never exposed in the browser bundle.

---

## Deployment

### Backend on Render

The backend ships with a `Dockerfile` — Render detects it automatically.

1. Create a **Web Service** on Render, point the root directory to `backend/`
2. Set **Environment** to **Docker**
3. Set **Health Check Path** to `/health`
4. Add all environment variables from the Backend table above

> **Security:** If your `GEMINI_API_KEY` was ever committed to a public repository, **revoke it immediately** in [Google AI Studio](https://aistudio.google.com/app/apikey) and generate a new one. Store it only in Render's environment variables — never in source files.

#### Render Free Plan — Cold Start

Render free-tier services sleep after 15 minutes of inactivity and take ~30–60 seconds to wake up. To minimize disruption:

- **UptimeRobot** (free): Ping your backend's `/health` endpoint every 5 minutes to keep it warm
- The frontend already shows `"Server is starting up..."` after 8 seconds of waiting so users know what's happening
- The Axios timeout is set to 150 seconds — more than enough for a cold start

### Frontend on Vercel

The frontend proxies all API calls through Next.js rewrites, so **no CORS configuration is needed on the backend**.

**Required Vercel environment variable:**

| Variable | Value |
|---|---|
| `BACKEND_URL` | Your Render backend URL, e.g. `https://beacon-backend.onrender.com` |

That's it. Do **not** set `NEXT_PUBLIC_API_URL` on Vercel — it's not needed with the proxy setup.

### Supabase Pooler

If connecting via Supabase's Transaction Pooler (port `6543`), `session.py` automatically disables prepared statements when it detects `:6543` or `pooler.supabase.com` in the URL.

---

## API Reference

### Create Session

```
POST /api/v1/public/reports/create
Content-Type: application/json
{}
```

```json
{
  "report_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "access_token": "tk_a1b2c3d4e5f6",
  "message": "Secure session established. Speak freely, I am listening."
}
```

### Send Message

```
POST /api/v1/public/reports/message
Content-Type: application/json

{
  "report_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "access_token": "tk_a1b2c3d4e5f6",
  "content": "An officer demanded payment at the checkpoint."
}
```

```json
{
  "report_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "sender": "SYSTEM",
  "content": "I understand how difficult that must have been. Can you tell me where exactly this happened?",
  "timestamp": "2026-01-01T12:00:00Z",
  "next_step": "ACTIVE",
  "case_id": null,
  "secret_key": null
}
```

When the conversation is complete:

```json
{
  "next_step": "COMPLETED",
  "case_id": "BCN-20260101-001",
  "secret_key": "SK-XXXX-XXXX-XXXX"
}
```

### Track Case

```
GET /api/v1/public/track?case_id=BCN-20260101-001&secret_key=SK-XXXX-XXXX-XXXX
```

---

## Credibility Scoring

Each finalized case is automatically scored (0–100) after submission:

```
Score = Narrative Consistency (0–40) + Evidence Strength (0–40) + Behavioral Reliability (0–20)
```

| Score | Confidence | Meaning |
|---|---|---|
| 0–33 | Low | Vague report, lacks specific details or evidence |
| 34–66 | Medium | Credible with partial corroboration |
| 67–100 | High | Detailed narrative with strong supporting evidence |

**Scoring rules:**
- No evidence submitted → Evidence Strength = 0 automatically
- Unrelated evidence (e.g., random photo for a bribery report) → 0 points
- Reports with only generic details cap at 15/40 for narrative consistency
- The system defaults to skepticism — scores above 60 must be earned

---

## Security Model

| Concern | Implementation |
|---|---|
| Reporter identity | Never stored; no account required |
| Access tokens | SHA-256 hashed before storage; plaintext never persisted |
| Secret keys | pbkdf2_sha256 hashed; shown once and never stored in plaintext |
| Case access | Requires *both* Case ID and Secret Key; neither alone grants access |
| Admin access | JWT with configurable expiry; password stored as bcrypt hash |
| Database connections | SSL enforced on all connections; `CERT_NONE` mode avoids CA chain issues |
| CORS | Configured to allow only known frontend origins |
| API keys | Must only be stored in Render environment variables, never in source code |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit: `git commit -m "feat: describe your change"`
4. Open a pull request

Security bug reports are especially welcome.

---

<div align="center">

Built to give every person a safe, private, and credible way to speak up.

**Secure · Anonymous · Verified**

*© 2026 Beacon AI*

</div>
