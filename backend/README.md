# Beacon AI backend

FastAPI service. Full documentation (configuration, deployment, security model) is in the [root README](../README.md).

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example backend_config.env                     # edit it
uvicorn app.main:app --reload --port 8000
pytest                                                 # runs against a fake Gemini API; no network or keys needed
ruff check app tests
python -m app.tools.hash_password                      # create an ADMIN_PASSWORD_HASH
```

Health check: `GET /health` → `{"status":"ok","db":"connected","ai":"ok"}` (`ai` is one of `ok`, `unknown`, `degraded`, `key_invalid`, `unconfigured`).

Key modules: `app/services/gemini/` (client, model fallback chain, circuit breaker), `app/services/chat_agent.py` (AI + basic mode),
`app/services/report_engine.py` (session → submission), `app/services/scoring_service.py` + `maintenance.py` (background analysis and self-healing).
