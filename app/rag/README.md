# `app/rag/` — what's in here

Everything needed to turn a question into an answer with citations: talking to
an embedding provider, talking to a vector store, talking to an LLM, and the
pipeline that wires those three together. Ingestion (upload, extract, chunk)
lives in `app/services/ingestion/` — it *uses* `embeddings/` and
`vectorstore/` from here, but isn't part of this folder.

## The flow (`POST /api/workspaces/{id}/search`)

```
question
  │
  ▼
embed_query()          app/rag/embeddings/   — turn the question into a vector
  │
  ▼
retrieve_chunks()      app/rag/retrieval.py  — vector search, scoped to one workspace
  │
  ▼
build_context()        app/rag/context.py    — number the chunks as [1] [2] ... sources
  │
  ▼
llm.generate()          app/rag/llm/          — ask the LLM to answer from those sources
  │
  ▼
answer + citations
```

`app/rag/pipeline.py` is the function that runs all four steps in order.
Everything else in this folder is one of those steps, kept in its own file so
each is easy to test and replace on its own.

## Top-level files

| File | What it does |
|---|---|
| **`pipeline.py`** | `answer_question(...)` — the whole flow above, one stage per line. Resolves the embedder and LLM *per user* (their own key if they've set one, else the server default), and turns provider errors into clear API errors (`rag_unavailable`, `embedding_unavailable`, `llm_unavailable`) instead of a stack trace. |
| **`retrieval.py`** | `retrieve_chunks(...)` — the only place that queries the vector store for search. Always adds `workspace_id` to the filter itself, from the authorized path, never from client input — this is where workspace isolation for search is enforced. Also where a Pinecone dimension-mismatch error gets turned into a plain-English "your provider doesn't match what indexed these documents" message. |
| **`context.py`** | `build_context(chunks)` — numbers the retrieved chunks `[1]`, `[2]`, ... with their document/page/section, and returns a matching `Citation` per chunk for the API response. Every chunk shown to the LLM becomes a citation (nothing checks yet whether the LLM's answer actually *used* each one — that's a later guardrail). |
| **`prompt.py`** | The system prompt ("answer only from these sources, cite them, say so if you can't") and `build_user_prompt(context, question)`, which just glues the numbered sources and the question together. |

## `embeddings/` — turning text into vectors

| File | What it does |
|---|---|
| **`base.py`** | The `Embedder` protocol (`embed(texts)`, `embed_query(text)`) and `EmbeddingError`. Any class with these two methods can be an embedder. |
| **`compatible_embedder.py`** | `CompatibleEmbedder` — the one implementation, used for every provider (see below). Batches requests (96 texts per call), retries transient failures 3x, and can force its output to a fixed `dimensions` so different providers still fit the same Pinecone index. |
| **`providers.py`** | `EMBEDDING_PROVIDERS` — which providers can embed at all, and their base URL + default model. Only **OpenAI**, **Gemini**, and **OpenRouter** (proxying OpenAI's model) are in here; **Groq has no embeddings endpoint**, full stop. `build_embedder(provider, api_key, ...)` builds a `CompatibleEmbedder` pointed at the right URL. |
| **`resolver.py`** | `get_embedder_for_user(user)` — the actual decision: use the user's own provider if it supports embeddings, else the server-wide default (`EMBEDDING_API_KEY`), else `None`. Called both when a question is asked *and* when a document is ingested, so both sides use the same provider. |
| **`__init__.py`** | `get_embedder()` — the single server-wide default embedder, built once from `.env` (`EMBEDDING_PROVIDER`/`EMBEDDING_API_KEY`/`EMBEDDING_MODEL`) and reused. |

**Why one class for every provider:** OpenAI, Gemini (via its OpenAI-compatibility
endpoint) and OpenRouter (proxying OpenAI's model) all speak the same wire
format, so `CompatibleEmbedder` just gets a different `base_url` and model name per
provider — no per-provider client code.

**The one thing to remember:** a Pinecone index has one fixed vector
dimension. Whatever provider embedded a document is the only provider whose
queries can find it. Switching provider doesn't re-embed old documents.

## `llm/` — turning context + question into an answer

| File | What it does |
|---|---|
| **`base.py`** | The `LLM` protocol (`generate(system, prompt)`) and `LLMError`. |
| **`compatible_llm.py`** | `CompatibleLLM` — the one implementation, same "one client, many providers via base_url" trick as the embedder. Retries 3x on any failure. |
| **`providers.py`** | `PROVIDERS` — all four chat providers (OpenAI, Gemini, OpenRouter, Groq) with base URL + default model. `build_llm(...)` builds a `CompatibleLLM` pointed at the right one. |
| **`resolver.py`** | `get_llm_for_user(user)` — user's own config wins, else the server default, else `None`. |
| **`model_catalog.py`** | `list_models(provider, api_key)` — asks the *provider's own* `/models` endpoint what that key can actually use, so the Settings UI can offer a real dropdown instead of a hardcoded (and occasionally deprecated) model name. Gemini is the one that matters most here — its native API is the only one that reports what's actually available to a given key. |
| **`__init__.py`** | `get_llm()` — the single server-wide default LLM, built once from `.env` (`LLM_PROVIDER`/`LLM_API_KEY`/`LLM_MODEL`). |

## `vectorstore/` — where the vectors live

| File | What it does |
|---|---|
| **`base.py`** | The `VectorStore` protocol (`upsert`, `delete`, `query`, `list_for_document`), `VectorItem`, and `VectorStoreError`. |
| **`pinecone_store.py`** | `PineconeStore` — the one implementation, backed by a single shared Pinecone serverless index. Chunk ids are deterministic (`{document_id}_chunk_{n}`), which matters because **Pinecone serverless has no delete-by-metadata-filter** — deleting or listing "a document's chunks" is done by listing ids with that prefix and acting on those, not by a metadata query. |
| **`__init__.py`** | `get_vectorstore()` (the one shared instance) and `init_vectorstore()` (creates the index on startup if it doesn't exist yet — skipped if `PINECONE_API_KEY` isn't set). |

## Two things that will bite you if forgotten

1. **Dimension/provider mismatch.** One Pinecone index, one fixed dimension.
   A workspace's documents were embedded with whatever provider indexed them;
   a user querying with a *different* provider gets `409 embedding_mismatch`
   or silently empty results. See `embeddings/providers.py`.
2. **Workspace isolation lives in `retrieval.py`, not the API layer.** Every
   vector search goes through `retrieve_chunks()`, which injects `workspace_id`
   itself from the authorized route — never trust a filter built anywhere else.
