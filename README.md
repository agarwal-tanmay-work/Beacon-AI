<div align="center">

<img src="docs/assets/brand-logo.png" alt="Beacon AI" width="200"/>

# Beacon AI

### Anonymous Corruption Reporting, Powered by AI

[![FastAPI](https://img.shields.io/badge/FastAPI-0.161-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/Gemini-3.x_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/gemini-api/docs/models)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)

**Beacon AI** lets anyone report corruption or misconduct safely and anonymously. A conversational assistant collects the facts and evidence, the case is scored for credibility in the background, and the reporter receives a Case ID + Secret Key to follow up and message investigators - without ever creating an account.

</div>

---

## How it works

```
 Reporter (anonymous)               Backend                              Investigators
 ────────────────────          ───────────────────────────          ─────────────────────
 1. chats at /report     ───▶  Gemini guides the interview:
 2. attaches photos/audio       what / where / when / who,
    PDFs, documents             evidence, optional contact
 3. says "that's all"    ───▶  Server checks the facts are there,
                                creates the case, issues
                                Case ID + Secret Key (shown once)
 4. saves the credentials       Background: evidence analysis ─▶ AI summary ─▶ score ──▶ admin portal
 5. /track any time      ◀───▶  status, updates, two-way messages ◀────────────────────  posts updates
```

### Resilience (what happens when Gemini misbehaves)

| Situation | What Beacon does |
|---|---|
| A model is retired / restricted (e.g. the old `gemini-2.5-flash`) | Per-model circuit breaker skips it; the next model in the **fallback chain** answers. |
| Rate limit / daily quota on one model | Classified from the API's error details; that model rests for the right amount of time, others take over. |
| Output cut off by thinking tokens, malformed JSON, empty reply | Retried with a bigger budget, then on the next model. |
| **Every** model is down | The conversation continues in **basic mode** with fixed questions, so a reporter can still finish a report. Analysis of the case is queued and retried automatically later. |
| API key rejected / leaked | Detected, surfaced on the admin dashboard and in `/health` (`"ai": "key_invalid"`). |
| A message is refused by safety filters | The user is asked to rephrase; nothing is stored. |
| The server restarts mid-analysis | A maintenance sweep re-runs stalled analyses with back-off. |

Default chains (`backend/app/services/gemini/registry.py`, override with `GEMINI_MODELS` / `GEMINI_FAST_MODELS`), tried in this order:

- **Smart** (chat, summary, scoring): `gemini-3.8-flash → gemini-3.5-flash → gemini-flash-latest → gemini-3.5-flash-lite → gemini-3.1-flash-lite → gemini-flash-lite-latest`
- **Fast** (vision, transcription, rewrites): `gemini-3.5-flash-lite → gemini-flash-lite-latest → gemini-3.1-flash-lite → gemini-3.5-flash → gemini-flash-latest`

---

## Repository layout

```
backend/            FastAPI service (Python 3.12)
  app/api/          HTTP routes: public (reporter) and admin
  app/core/         settings, security primitives, logging, rate limiting, middleware
  app/db/           async engine, schema upgrades
  app/models/       SQLAlchemy models
  app/schemas/      request/response + LLM schemas
  app/services/     gemini/ (client, fallback chain), chat_agent, report_engine, evidence_processor,
                    scoring_service, maintenance, storage_service ...
  tests/            pytest suite (fake Gemini at the HTTP level)
frontend/           Reporter-facing Next.js app (chat, tracking)
admin-portal/       Investigator Next.js app
docs/assets/        Images used by this README
.github/workflows/  CI + Render keep-alive
```

---

## Getting started (local)

Requirements: Python 3.12, Node 22, a Gemini API key. A Supabase project is **optional** locally (SQLite + a local folder are used instead).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example backend_config.env                          # then edit it
#   minimum for local use:
#     SECRET_KEY=<64 random hex chars>   DATABASE_URL=sqlite+aiosqlite:///./dev.db
#     GEMINI_API_KEY=...  ENVIRONMENT=development  ADMIN_PASSWORD=<something for local use>
uvicorn app.main:app --reload --port 8000                   # docs: http://localhost:8000/api/v1/docs

# Reporter site
cd frontend && npm install && echo 'BACKEND_URL=http://localhost:8000' > .env.local && npm run dev      # :3000

# Admin portal
cd admin-portal && npm install && echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local && npm run dev   # :3001
```

Tests and checks: `cd backend && pytest && ruff check app tests`; `cd frontend && npm run lint && npm run build` (same for `admin-portal`).

---

## Configuration (backend)

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes | ≥ 32 random chars. Signs admin JWTs and file links. |
| `DATABASE_URL` | yes | Supabase *session pooler* string (IPv4). `postgres://` / `postgresql://` are converted automatically. |
| `GEMINI_API_KEY` | yes\* | \*Without it the assistant runs in basic mode and cases are not scored. |
| `ADMIN_PASSWORD_HASH` **or** `ADMIN_PASSWORD` | for the admin portal | **No default password exists.** Without one, admin login is disabled. Generate a hash: `python -m app.tools.hash_password`. bcrypt hashes from the old README keep working. |
| `ADMIN_USERNAME` | no | default `beaconai` (`admin` is accepted as an alias) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | production | Evidence storage. Accepts the new `sb_secret_…` keys and legacy service-role keys. Without them files go to local disk, which Render wipes on every deploy. |
| `CORS_ORIGINS` | for the admin portal | The admin portal's URL. The reporter site uses a same-origin proxy and needs no CORS. |
| `GEMINI_MODELS`, `GEMINI_FAST_MODELS`, `GEMINI_AUTO_DISCOVER` | no | Override / extend the fallback chains. |
| `ENVIRONMENT` | no | `production` (default) hides `/api/v1/docs`. |

`GROQ_API_KEY`, `SUPABASE_KEY` and other legacy variables are ignored if still set.

## Deployment

**Backend (Render, Docker)** - root directory `backend/`, health check path `/health`. Set the variables above.
**Reporter site (Vercel)** - project root `frontend/`, set `BACKEND_URL=https://<your-render-service>`.
**Admin portal (Vercel)** - project root `admin-portal/`, set `NEXT_PUBLIC_API_URL=https://<your-render-service>`, and add its URL to `CORS_ORIGINS` on the backend.
**Supabase** - make the `evidence` bucket **private** (the backend creates it as private if missing). Files are only ever served through short-lived signed links from `GET /api/v1/files`.

Upgrading an existing deployment is automatic: on start-up the schema is brought up to date (additive only) and legacy plaintext secret keys are hashed and scrubbed.

---

## Security model

| Concern | Implementation |
|---|---|
| Reporter anonymity | No accounts. Photos are re-encoded to drop EXIF/GPS/device data before storage. |
| Reporting sessions | 256-bit access token, only its SHA-256 is stored, verified on every message and upload. |
| Case access | Case ID **and** Secret Key. Keys are 80-bit, stored only as PBKDF2 hashes, shown once; per-IP and per-case lock-outs; identical error and timing for unknown IDs. A lost response can be recovered until the reporter confirms they saved the key (max 24 h). |
| Submission | Decided by the server from validated facts, never by model output. Prompt-injection cannot create cases or credentials. |
| Admin | JWT (1 h), constant-time password check, lock-out after 6 failures, fail-closed when unconfigured. |
| Evidence files | Private bucket, type decided from file bytes against an allowlist, size/count caps, names never reach storage paths, served with `nosniff` + restrictive CSP. |
| Abuse | Per-IP and global rate limits, request-body size limit enforced while streaming. |
| Logging | Secrets are redacted; message bodies and evidence text are never logged. |

### Privacy note on Gemini
Google's pricing page states that **free-tier** API traffic may be used to improve Google's products; paid-tier traffic is not. For a service handling whistleblower reports, use a **paid-tier** key in production.

### If keys were ever committed
The git history of this repository contained API credentials. Rotating them is required even though they are no longer in the current tree: **Gemini** (create a new key in AI Studio, delete the old), **Supabase** (create a new secret key, then deactivate the legacy `service_role`/`anon` keys under *Settings → API Keys*), the **database password**, `SECRET_KEY`, and the admin password.

---

## API (summary)

Public: `POST /api/v1/public/reports/create` · `/message` · `/credentials` · `/credentials/ack` · `POST /public/evidence/upload` · `POST /public/track` · `/track/message` · `/track/upload`
Admin (Bearer JWT): `POST /admin/auth/login` · `GET /admin/reports/` · `GET|PUT /admin/reports/{id}[/status]` · `GET|POST /admin/reports/{id}/messages|message|upload|update|analyze` · `GET /admin/system/status`
Files: `GET /api/v1/files?ref=…&exp=…&sig=…` (signed). Health: `GET /health`.

Errors are `{"detail": "...", "code": "..."}` (`ai_unavailable`, `rate_limited`, `invalid_session`, `file_too_large`, …).

## Credibility score

`narrative (0-40) + evidence (0-40) + behaviour (0-20)`, computed by the server from the model's three judgements: **Low** 0-33, **Medium** 34-66, **High** 67-100. No usable evidence ⇒ evidence points are exactly 0. The score prioritises cases for human review; it is not a verdict.

---

<div align="center">

*Secure · Anonymous · Verified* — © 2026 Beacon AI

</div>
