# Backend — Enterprise Knowledge Intelligence API

FastAPI + MongoDB + Redis. Phase 1: auth + workspaces.

Config lives in **`backend/.env`** (copy from `backend/.env.example`). The frontend has
its own `frontend/.env`. There is no root env file.

## Run (Docker)

From the repo root:

```bash
cp backend/.env.example backend/.env     # set JWT_SECRET for anything real
docker compose up --build                # mongo + redis + api on :8000
```

Compose overrides `MONGODB_URI` / `REDIS_URL` to the service hostnames; everything
else comes from `backend/.env`.

## Run (local)

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # POSIX: .venv/bin/pip
cp .env.example .env          # localhost URIs; needs mongo + redis reachable
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Edited `.env`? Fully restart uvicorn — settings load once at startup.

## Test

```bash
cd backend
.venv/Scripts/python -m pytest -q      # in-memory Mongo (mongomock) + fakeredis, no services needed
.venv/Scripts/python -m ruff check app tests
```

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | – | `{status, mongo, redis}` |
| POST | `/api/auth/register` | – | `{name,email,password}` → `{access_token, token_type, user}` (201) |
| POST | `/api/auth/login` | – | `{email,password}` → same |
| GET | `/api/auth/me` | Bearer | current user |
| POST | `/api/workspaces` | Bearer | `{name}` → workspace (201) |
| GET | `/api/workspaces` | Bearer | workspaces the caller owns / belongs to |
| GET | `/api/workspaces/{id}` | Bearer | 400 bad id · 403 not a member · 404 missing |
| POST | `/api/workspaces/{id}/documents` | member | multipart `file` + optional `metadata` (JSON) → doc (202) |
| GET | `/api/workspaces/{id}/documents` | member | list, optional `?status=` |
| GET | `/api/documents/{id}` | member | one doc — 403 if not a member of its workspace |
| DELETE | `/api/documents/{id}` | member | removes record + stored original (204) |

Errors: `{"error": {"code": "...", "message": "..."}}`. Interactive docs at `/docs`.

### Phase 2 — ingestion

Upload stores the original in object storage, creates a `documents` record at
`status:"uploaded"`, and enqueues an **arq** job (`process:{id}`, deduped). The
worker extracts + normalizes text, stashes structured blocks in Redis for Phase 3,
and flips status to `processed` (or `failed` with a safe `processing_error`).
Chunking / embeddings are Phase 3.

Run the worker: `arq app.workers.settings.WorkerSettings` (its own process; `docker
compose` starts it plus MinIO). If Redis is unreachable the upload still succeeds —
the doc stays `uploaded` until a worker + queue are available.

## Layout

```
app/
├── main.py            app factory, lifespan (mongo/redis connect), /health
├── core/              config, security (bcrypt + JWT), logging, errors
├── db/                mongo.py, redis.py  (module-level clients + retry)
├── models/            UserDoc, WorkspaceDoc  (Mongo document shapes)
├── schemas/           request/response DTOs
├── services/          auth_service, workspace_service  (all DB access)
└── api/               deps.py (get_current_user, authorize_workspace), auth.py, workspaces.py
```

`services/ingestion|retrieval|rag|...` land in their own phases — not created yet.
