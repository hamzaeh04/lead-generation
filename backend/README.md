# lead-generation-backend

FastAPI API for the Lead Intelligence Platform (PostgreSQL, optional Redis/Celery).

## Stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy** (async) + **asyncpg**
- **Alembic** migrations
- **Redis** (optional — rate limits / token revocation)
- **Celery** (optional — background campaign sends)

## Prerequisites

- Python 3.11+ (3.12 recommended)
- PostgreSQL 14+ (local or Neon)
- Redis (optional for local API; required for full rate-limit / logout behavior)

## Setup

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Copy or create `backend/.env` (never commit real secrets). Minimum:

```env
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=replace-with-a-long-random-string

DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/lead_platform

# Optional locally; leave unset or point at a real Redis in production
REDIS_URL=redis://localhost:6379/0

CORS_ORIGINS=http://localhost:3000

# Provider keys (also overridable per workspace in Settings UI)
APOLLO_API_KEY=
SMARTLEAD_API_KEY=
ANTHROPIC_API_KEY=
```

Provider credentials resolve in order:

1. Workspace row in `workspace_api_keys` (Settings → Provider API keys)
2. Process env / `.env` (`APOLLO_API_KEY`, `SMARTLEAD_API_KEY`, `ANTHROPIC_API_KEY`)

### Neon / hosted Postgres

Use a `postgresql+asyncpg://…` URL. The app normalizes Neon URLs (async driver, strips `channel_binding`, maps `sslmode` for asyncpg). Prefer the **pooler** host for serverless (Vercel); for one-off migrations, the **direct** (non-pooler) host is more reliable.

On Neon + pooler, the app forces `search_path=public` so unqualified tables resolve correctly.

## Database migrations

```bash
cd backend
# activate .venv first
alembic upgrade head
```

Other useful commands:

```bash
alembic current
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

## Run the API

```bash
cd backend
# activate .venv first
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/health | Liveness |
| http://127.0.0.1:8000/ready | DB (+ Redis) readiness |
| http://127.0.0.1:8000/docs | OpenAPI UI (`ENVIRONMENT=development` only) |
| http://127.0.0.1:8000/api/v1/… | API routes |

## Celery worker (optional)

Needed for scheduled / background campaign sending:

```bash
cd backend
# activate .venv first
celery -A app.workers.celery_app worker --loglevel=info
```

Requires a working `REDIS_URL` (broker).

## Tests

Tests use in-memory SQLite via fixtures — no Postgres/Redis required:

```bash
cd backend
# activate .venv first
pytest -q
```

## Vercel / production notes

- Set `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT=production`, and provider keys (or rely on workspace DB keys).
- Do **not** set `REDIS_URL=redis://localhost:…` on Vercel (it will hang or fail). Leave Redis unset unless you attach Upstash/Redis.
- After deploy, run migrations against the production DB (`alembic upgrade head` from a machine that can reach Neon).
- CORS: exact origins in `CORS_ORIGINS`; `*.vercel.app` frontends are also allowed via regex in `app/main.py`.

## Project layout

```
backend/
  app/
    api/          # HTTP routers
    core/         # config, database, security
    models/       # SQLAlchemy models
    providers/    # Apollo, Smartlead, Groq, …
    repositories/
    services/     # business logic + provider_factory
    workers/      # Celery
  alembic/        # migrations
  tests/
  requirements.txt
  alembic.ini
  .env            # local only — gitignored
```
