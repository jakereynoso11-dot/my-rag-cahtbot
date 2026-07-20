# Migrate RAG chatbot from Supabase to Powabase

## Context

The existing FastAPI app in `app/` implements a simple RAG chatbot:

- **Ingest** (`POST /ingest/file`): loads a PDF with `PyPDFLoader`, splits it with
  LangChain's `CharacterTextSplitter`, embeds chunks with `OpenAIEmbeddings`, and
  writes them into a Supabase Postgres table (`chunks`) via
  `langchain_community.vectorstores.SupabaseVectorStore`.
- **Chat** (`POST /chat`): embeds the query, calls a Supabase RPC (`match_chunks`)
  for pgvector similarity search, then calls OpenAI's chat completions API
  directly with the retrieved chunks as context, returning one JSON
  `{answer, sources}` response.

Supabase is being replaced with **Powabase**, a multi-tenant AI Backend-as-a-Service
that provides Sources/Knowledge-Base RAG primitives and hosted Agents (LLM + system
prompt + tools + KB, run as a ReAct loop over SSE) on top of a Supabase-style
Postgres+pgvector backend. This rebuild leans fully into Powabase's Agent module
rather than just swapping the vector store: Powabase owns ingestion, chunking,
embedding, retrieval, *and* the chat completion itself. The FastAPI app becomes a
thin, trusted proxy in front of Powabase's `/api/*` surface.

This decision was made explicitly over the alternative (using Powabase only as a
pgvector/PostgREST replacement while keeping our own OpenAI chat-completion call)
because it removes LangChain and direct OpenAI usage entirely, in favor of Powabase
managing the LLM call (via BYOK or its own provider management).

## Architecture

```
Client -> FastAPI (this app) -> Powabase /api/*
                                   - Sources (upload, extraction)
                                   - Knowledge Base (indexing, retrieval)
                                   - Agent (ReAct loop, linked to the KB)
```

- FastAPI holds the Powabase **Service Role (Secret) key** server-side only. This
  is required: Powabase does not forward end-user identity into agent tool calls,
  so any surface that lets a client call `/api/agents/{id}/run/stream` directly
  with their own token would grant them the agent's full tool/DB access. Routing
  through our own backend keeps the Service Role key off the client and lets us
  control what's exposed.
- One **Knowledge Base** is created once (indexing strategy `chunk_embed`,
  retrieval method `hybrid` — Powabase's recommended default for general mixed
  documents, matching the current chunk+embed+similarity-search behavior).
- One **Agent** is created once, linked to that KB (auto-provisions a
  `knowledge_search` tool scoped to it), with a system prompt equivalent to the
  current `chat_service._build_messages` prompt ("use the provided context;
  say so if insufficient").
- The KB ID and Agent ID are fixed configuration (not created per-request) —
  analogous to how `supabase_table`/`supabase_match_fn` were fixed names before.
  They're provisioned by a one-time setup script (see below), not by the running
  app.

## Components

### Config (`app/core/config.py`)

Remove: `openai_api_key`, `supabase_url`, `supabase_key`, `supabase_table`,
`supabase_match_fn`, `default_max_output_tokens`.

Add: `powabase_base_url`, `powabase_api_key` (Service Role key), `powabase_kb_id`,
`powabase_agent_id`.

Change in meaning: `chunk_size`/`chunk_overlap` become the KB's
`indexing_config` at *creation* time (set once by the setup script), not
per-ingest-request parameters — Powabase chunks server-side during indexing.
`default_k`/`max_k` become the Agent's KB-link `top_k` override rather than a
per-search parameter passed straight to a similarity RPC.

`default_max_output_tokens` has no equivalent in Powabase's run API (`/run` and
`/run/stream` accept `message`, `session_id`, `temperature`, `response_format`,
`max_context_tokens`, `citations_enabled` — no max-output-tokens field) and is
dropped rather than faked.

### Clients (`app/clients/`)

- Delete `supabase_client.py`, `openai_client.py`, `embeddings.py`.
- Add `powabase_client.py`: a thin async wrapper (`httpx.AsyncClient`) providing
  the base URL, the two required headers (`apikey`, `Authorization: Bearer`) on
  every call, and a streaming-POST helper for SSE endpoints. No retry/business
  logic lives here — just the authenticated transport.

### Services (`app/services/`)

- **`ingest_service.py`** (rewritten): given uploaded file bytes,
  1. `POST /api/sources/upload` (multipart). Treat `201` and `409
     duplicate_source` both as success — on `409`, reuse the existing source id
     from the response body rather than erroring.
  2. Poll `GET /api/sources/{id}` until `extraction_status` reaches a terminal
     state (`extracted`, `attention_required`, `failed`, `cancelled`), bounded by
     a timeout budget (e.g. 120s; polling interval ~2s).
  3. If the terminal state is `attention_required` or `failed`, return an error
     to the caller explaining extraction did not produce usable text (no
     automatic OCR re-extract attempt in v1 — that's a manual follow-up via
     `/api/sources/{id}/reextract`, out of scope here).
  4. If `extracted`, `POST /api/knowledge-bases/{kb_id}/sources {source_id}` to
     index it, then poll `GET /api/knowledge-bases/{kb_id}/sources` for that
     `indexed_source_id`'s `index_status` until `indexed`/`failed`/`cancelled`
     (same timeout-budget pattern).
  5. Return the source id, indexed-source id, and final status.
- **`retrieval_service.py`**: deleted. The Agent performs retrieval internally
  (via its linked-KB `knowledge_search` tool) during a `/run/stream` call — the
  app no longer calls KB search directly for chat.
- **`chat_service.py`** (rewritten): given a query and optional `session_id`,
  opens a streaming POST to `/api/agents/{agent_id}/run/stream` with
  `{message, session_id}` and yields the raw SSE lines through as an async
  generator (buffering partial lines per the platform's SSE contract: split on
  `\n`, drop `:`-prefixed keepalive comments). No event reshaping — event names
  (`start`, `content_delta`, `tool_call`, `tool_result`, `complete`, `error`,
  etc.) are forwarded as Powabase defines them.

### Routes (`app/api/routes/`)

- **`ingest.py`**: same upload contract as today (`multipart/form-data` file),
  but the response reports `source_id`, `indexed_source_id`, `status` instead of
  `table_name`/`match_function`. A polling timeout surfaces as `504`.
- **`chat.py`**: request body drops `filter`, `match_threshold`, `model`,
  `max_output_tokens` (retrieval and model choice now live on the KB/Agent
  config in Powabase, not per-request) and gains an optional `session_id` for
  multi-turn conversations. The endpoint returns a `StreamingResponse` with
  `media_type="text/event-stream"` that forwards the Agent's SSE stream live.
  A mid-stream Powabase `error` event is forwarded as-is (not raised as an
  HTTP exception, since the response has already started streaming).

### Schemas (`app/models/schemas.py`)

`ChatRequest`: `query` (required), `session_id: Optional[str]`, `temperature:
Optional[float]` (kept — Powabase's run body accepts a top-level `temperature`
per-run override). Remove `k`, `filter`, `match_threshold`, `model`,
`max_output_tokens` — these no longer have a per-request equivalent; retrieval
tuning and model choice now live on the KB/Agent config in Powabase.
`IngestResponse`: `source_id`,
`indexed_source_id`, `status`. `SourceChunk`/`ChatResponse` (the old
single-JSON-answer shape) are removed since chat is now a raw SSE stream, not a
single JSON body.

### One-time setup script

`scripts/setup_powabase.py`: a standalone script (not invoked by the running
app) that creates the Knowledge Base (`chunk_embed` + `hybrid`) and the Agent
(linked to that KB, with the ported system prompt), and prints the resulting
`powabase_kb_id` / `powabase_agent_id` for the developer to paste into `.env`.
Mirrors the role the original SQL migration (creating the `chunks` table +
`match_chunks` function) played for Supabase — a one-time provisioning step, run
manually, not part of app startup.

### Dependencies (`requirements.txt`)

Remove: `supabase`, `openai`, `langchain-openai`, `langchain-community`,
`langchain-text-splitters`, `pypdf`.
Add: `httpx`.
Keep: `fastapi`, `uvicorn`, `python-dotenv`, `pydantic`, `pydantic-settings`,
`python-multipart`.

## Error handling

- Powabase's `409 duplicate_source` on upload is treated as success (reuse
  existing source), not surfaced as an error.
- `attention_required`/`failed` extraction terminal states surface as a client
  error (400/422) explaining the document needs OCR re-extraction — not a silent
  retry loop.
- Polling timeouts (extraction or indexing taking too long) surface as `504`
  with a message the caller can retry against later.
- Powabase billing errors (`402 insufficient_credits`, `503` billing
  unreachable) during ingest are passed through with their status/detail rather
  than retried blindly (`402` must not be retried; `503` may be retried with
  backoff by the caller).
- A mid-stream `error` SSE event from the Agent run is forwarded to the client
  inside the stream (the HTTP response is already 200 and streaming by that
  point) rather than raised as an exception.

## Testing

- Unit tests for `ingest_service` and `chat_service` against a mocked Powabase
  HTTP layer (e.g. `respx` against `httpx`), covering: normal upload+extract+
  index happy path, `409 duplicate_source` reuse, `attention_required` handling,
  indexing-poll timeout, and SSE forwarding including a mid-stream `error`
  event.
- No live-credential integration test in CI (Powabase project credentials are
  developer-specific and provisioned by hand). A manual smoke-test path (upload
  a sample PDF through `/ingest/file`, then ask a question through `/chat` and
  confirm a streamed answer) is the real end-to-end check once a Powabase
  project and Agent/KB exist.

## Human handoff required before this runs end-to-end

- Create a Powabase project and get the **Project URL** + **Service Role
  (Secret) key** from the Studio's Connect modal (project header → Connect, or
  `?showConnect=true`).
- Configure a BYOK provider key (e.g. OpenAI) for the Agent's model under
  **Settings → LLM Provider Keys**, unless AI-on-us is active for that provider.

These are Studio-only steps; the implementation plan will pause at the point
they're needed and ask for the specific values.
