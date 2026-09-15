# Backend — Enterprise Knowledge Intelligence API

FastAPI + MongoDB + Redis + Pinecone + an LLM. Phases 1-4: auth + workspaces,
document ingestion, vector pipeline, baseline RAG.

Config lives in **`backend/.env`** (copy from `backend/.env.example`). The frontend has
its own `frontend/.env`. There is no root env file.

## Run (Docker)

From the repo root:

```bash
cp backend/.env.example backend/.env     # set JWT_SECRET for anything real
docker compose up --build                # mongo + redis + api on :8000
```

No object storage, no separate worker — document processing runs in-process
(see Phase 2 below). Just these three services.

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
| DELETE | `/api/documents/{id}` | member | removes record + indexed vectors (204) |
| GET | `/api/documents/{id}/chunks` | member | up to `?limit=` (default 20, max 100) indexed chunk previews |
| POST | `/api/workspaces/{id}/search` | member | `{question, document_ids?}` → `{answer, citations, retrieved_count}` |
| GET | `/api/llm-providers` | – | `[{id, label, default_model}]` — openai / gemini / openrouter / groq |
| GET | `/api/auth/llm-config` | Bearer | `{configured, provider, model}` — never the key |
| PUT | `/api/auth/llm-config` | Bearer | `{provider, api_key, model?}` → stores it (encrypted), returns the same shape |
| DELETE | `/api/auth/llm-config` | Bearer | clears it, falls back to the server default (204) |

Errors: `{"error": {"code": "...", "message": "..."}}`. Interactive docs at `/docs`.

### Per-user LLM + embedding provider

Each user can pick their own provider + paste their own key (Settings → LLM
provider in the frontend) — it's used for every `/search` call *they* make, in
every workspace, instead of the server-wide default. OpenAI, Groq and
OpenRouter all speak the OpenAI chat-completions format natively; Gemini is
reached through Google's OpenAI-compatibility endpoint — so one `OpenAILLM`
class handles chat for all four, just swapping `base_url`/model
(`app/llm/providers.py`).

**Embeddings follow the same provider choice where possible** — OpenAI and
Gemini have their own embeddings endpoint; OpenRouter has none of its own but
proxies OpenAI's embedding model under OpenAI's name, so an OpenRouter user's
own key/credits still embed, via OpenRouter. Groq has no embeddings endpoint
at all (not even proxied) — a Groq user falls back to the server-wide embedder
for embedding only, chat still uses their own key (`app/embeddings/resolver.py`).

This also drives **ingestion**, not just querying: every `documents` row
records `uploaded_by`, and processing embeds with *that user's* provider
(`app/services/ingestion/processing.py::_index_chunks`), so what indexed a
document matches what a query with the same provider expects.

**The catch, by design** (see `app/embeddings/providers.py`): a Pinecone index
has one fixed vector dimension, and different providers' embeddings aren't
points in a comparable space anyway. Mixing providers within a workspace means
documents indexed under one provider become unsearchable — often a hard
`409 embedding_mismatch` — for a user querying with a different one. There's no
automatic re-indexing; switching provider on an existing workspace requires an
admin to re-process its documents under the new provider.

Keys are encrypted at rest (Fernet, `SECRETS_ENCRYPTION_KEY`) and **never**
returned by the API after saving — `GET`/`PUT /api/auth/llm-config` only ever
report `{configured, provider, model}`. Nothing configured anywhere (user or
server) → `503 rag_unavailable` / `llm_unavailable` rather than guessing.

### Phase 2 — ingestion (object storage + background worker deferred)

Upload creates a `documents` record at `status:"uploaded"` and hands the file's
bytes to a **FastAPI `BackgroundTasks`** call
(`process_document_now`, `app/services/ingestion/processing.py`) — same
process, no queue, no separate worker, nothing persisted beyond the Mongo
record. The bytes only ever exist in memory for that one request; there's no
storage to re-read from, so a transient embedding/vector-store failure goes
straight to `status:"failed"` rather than retrying — re-upload to try again.

Object storage (S3/MinIO) and a real Redis-backed `arq` worker were built once
and deliberately removed for local-dev simplicity — see
[plan/backend/phase-2b-storage-and-workers.md](../plan/backend/phase-2b-storage-and-workers.md)
for the tradeoff and what it takes to bring them back.

Processing still extracts + normalizes text and stashes structured blocks in
Redis (`doc:{id}:blocks`, TTL 1h, best-effort — Redis being down doesn't fail
the upload).

### Phase 3 — vector pipeline

After extraction, processing chunks each block with `StructuralChunker`
(sentence-packed windows of `CHUNK_TARGET_TOKENS` with `CHUNK_OVERLAP_TOKENS`
overlap, page/section preserved per chunk), embeds the chunks (`OpenAIEmbedder`,
`text-embedding-3-small`), and upserts them into Pinecone (`PineconeStore`) with
`workspace_id`/`document_id`/`page`/`section`/`chunk_index` metadata. Re-running a
document deletes its existing vectors first — safe to retry.

**No `PINECONE_API_KEY` / `EMBEDDING_API_KEY` set?** The pipeline skips indexing —
the document still reaches `status:"processed"`, just with `chunk_count: 0`. Set
both to activate it; no code change needed. Create the index once:

```bash
cd backend && .venv/Scripts/python scripts/init_pinecone.py
```

Vector isolation: chunk ids are deterministic (`{document_id}_chunk_{n}`), so
listing/deleting a document's chunks is done by id prefix — Pinecone serverless has
no delete-by-metadata-filter.

### Phase 4 — baseline RAG

`POST /api/workspaces/{id}/search` is the whole pipeline, one stage per module —
not one big function:

```
question → embed_query (Embedder) → retrieve_chunks (workspace_id filter always
         applied server-side, optional document_ids) → build_context (numbered
         [1], [2]... sources with page/section) → LLM.generate (system prompt:
         "answer only from these sources, cite them, say so if they don't cover
         it") → {answer, citations, retrieved_count}
```

`app/services/rag/{retrieval,context,prompt,pipeline}.py`. Every citation returned
is a chunk that was put in front of the LLM — validating that the *answer* actually
used each one is Phase 7 (citation validation guardrail). No query rewriting, hybrid
search, reranking or conversation memory yet — those are Phase 5/6, added without
restructuring this.

Zero indexed chunks → a canned "nothing indexed yet" answer, **LLM is never
called**. No `PINECONE_API_KEY`/`EMBEDDING_API_KEY`/`LLM_API_KEY` → `503
rag_unavailable` / `llm_unavailable` rather than a stack trace.

## Layout

```
app/
├── main.py            app factory, lifespan (mongo/redis/vectorstore init), /health
├── core/              config, security (bcrypt + JWT), crypto (Fernet), logging, errors
├── db/                mongo.py, redis.py  (module-level clients + retry)
├── models/            UserDoc, WorkspaceDoc, DocumentDoc  (Mongo document shapes)
├── schemas/           request/response DTOs
├── services/
│   ├── auth_service.py, workspace_service.py, user_llm_service.py
│   ├── ingestion/
│   │   ├── validation.py, loaders.py, normalize.py, document_service.py
│   │   ├── processing.py    process_document_now — extract/chunk/embed/index, in-process
│   │   └── chunking/        Chunker protocol + StructuralChunker
│   └── rag/             retrieval.py, context.py, prompt.py, pipeline.py
├── embeddings/         Embedder protocol, OpenAIEmbedder, providers.py, resolver.py (per-user)
├── vectorstore/        VectorStore protocol + PineconeStore
├── llm/                LLM protocol, OpenAILLM, providers.py, resolver.py (per-user)
└── api/                deps.py, auth.py, workspaces.py, documents.py, search.py
```

`services/guardrails|evaluation` land in their own phases — not created yet.
`storage/` and `workers/` were removed — deferred, see
[plan/backend/phase-2b-storage-and-workers.md](../plan/backend/phase-2b-storage-and-workers.md).
