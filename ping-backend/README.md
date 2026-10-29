# ping-backend

The API behind the Pingie dashboard and the embeddable chat widget. Built the
same way as Memora's backend: FastAPI, sync SQLAlchemy 2.0 over Neon
PostgreSQL (psycopg 3), Alembic migrations, thin routes over a service layer,
and Google sign-in with an HttpOnly session cookie.

## How a question is answered

```
Visitor: "Can I get a refund?"
   │
   ▼
Memora  (retrieval only)   POST /query  generate=false
   │                       HNSW → MMR → rerank → ranked passages + filenames
   ▼
Ping    (reasoning)        small talk? → condense follow-up → similarity floor
   │                       → prompt with the bot's instructions, tone, language
   ▼
LLM provider               /chat/completions, streamed
(MODEL_PROVIDER)           vizhi (default) · nebius · build-nvidia
   │
   ▼
Ping    (verify)           [n] citations → sources · NO_ANSWER → fallback + ask
                           for email · [[PARTIAL]] → partial
   ▼
"Yes! Annual plans can be refunded within 30 days.   📄 refund-policy.docx"
```

- **Memora never writes answers for Ping.** Each bot is a Memora *subject*
  (`external_id` = the bot's public id) and each source a Memora *source*.
  Ping calls `/query` with `generate: false` (a small, backwards-compatible
  addition to Memora; see "Memora change" below).
- **All reasoning is in `app/reasoning/`**: `pipeline.py` (the steps),
  `prompts.py` (every prompt), `output.py` (marker parsing, streaming-safe).
- **Every LLM call goes through `app/clients/llm.py`**, to the provider named
  by `MODEL_PROVIDER`. With `vizhi` (the default), cost, latency, fallback and
  budgets show up in the Vizhi dashboard and `messages.gateway_query_id` links
  a reply to its Vizhi log. With `nebius` or `build-nvidia`, Ping calls the
  provider directly with its API key and the `LLM_MODEL_*` for each tier; there
  is no gateway log, so `gateway_query_id` stays empty.

## Running it

You need Python 3.12+, a Neon database, a running Memora, and an LLM provider:
a running VizhiOps, or a Nebius / build.nvidia.com API key.

```bash
cp .env.example .env            # fill in DATABASE_URL, AUTH_JWT_SECRET, GOOGLE_CLIENT_ID,
                                # MEMORA_API_TOKEN, and VIZHI_TOKEN_BALANCED
                                # (or MODEL_PROVIDER + its API key)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Docs: http://localhost:8080/docs. Memora and Vizhi both default to port 8000;
the example config puts Vizhi on 8001.

### One-time setup in the other services

1. **Memora:** in the Memora console, create a tenant, an application
   (e.g. `ping`), and an API credential for it. Put the `memora_...` token in
   `MEMORA_API_TOKEN`. Ping discovers the application id via `/whoami`.
2. **VizhiOps:** start it with `INFERENCE_BACKEND=auto`. Create one model token
   per tier you want (`fast` for query rewriting, `balanced` for answers,
   optionally `best`) and put them in `VIZHI_TOKEN_*`. Skip this when
   `MODEL_PROVIDER` is `nebius` or `build-nvidia`.

## Tables (migration `0001_initial`)

| Table | What it holds |
| --- | --- |
| `users`, `authenticated_user` | Dashboard users and their Google identities (same shape as Memora) |
| `organizations`, `organization_members` | Workspaces with plan limits; every bot query joins membership |
| `bots` | Public id, settings (instructions, tier, tone, language, similarity floor, fallback, handoff), widget appearance (JSONB), Memora subject id |
| `bot_sources` | Files, pages and sitemaps (sitemap pages are child rows), with indexing status mirrored from Memora |
| `allowed_domains` | Hosts the widget may load on; `last_seen_at` powers the install check |
| `visitors`, `conversations`, `messages` | Chats. Bot messages store outcome, citations, a reasoning trace, tokens, latency and the Vizhi query id |
| `leads` | Emails captured when the bot could not answer |

## API

Dashboard routes need the session cookie (`POST /api/v1/auth/google` sets it).
Widget routes are public, authorised by the page's `Origin` against the bot's
allowed domains and, inside a conversation, by `X-Conversation-Token`.

| Screen | Endpoints |
| --- | --- |
| Login | `POST /auth/google` `{id_token}` · `GET /auth/me` · `POST /auth/logout` |
| All bots | `GET /orgs` · `GET /orgs/{id}/bots` · `POST /orgs/{id}/bots` `{name, domain, sitemap_url?}` |
| Overview | `GET /bots/{bot_id}/overview?range=24h\|7d\|30d\|90d` |
| Conversations | `GET /bots/{bot_id}/conversations?filter=all\|unanswered\|down\|handoff&q=&before=` · `GET …/conversations/{id}` · `GET …/conversations/export.csv` · `DELETE …/conversations` · `GET /bots/{bot_id}/leads` |
| Sources | `GET /bots/{bot_id}/sources` · `POST …/sources/upload` (multipart) · `POST …/sources/url` `{url, kind: url\|sitemap}` · `POST …/sources/{id}/resync` · `DELETE …/sources/{id}` |
| Test retrieval | `POST /bots/{bot_id}/test` `{query, top_k, threshold}` |
| Appearance | `GET/PUT /bots/{bot_id}/appearance` |
| Install & embed | `GET /bots/{bot_id}/install` |
| Allowed domains | `GET/POST /bots/{bot_id}/domains` · `DELETE …/domains/{id}` |
| Bot settings | `GET/PATCH/DELETE /bots/{bot_id}` |
| Widget | `GET /widget/{bot_id}/config` · `POST /widget/{bot_id}/conversations` · `POST …/conversations/{id}/messages` `{text, stream}` (SSE when streaming) · `POST …/messages/{mid}/feedback` · `POST …/conversations/{id}/identify` |

All paths are under `/api/v1`, except `GET /widget.js`: the embeddable widget,
built from `ping-widget/` into `app/static/widget.js` (`npm run build:backend`). Errors are always `{"detail": "...", "code": "..."}`.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://…/ping_test .venv/bin/pytest
```

Integration tests need a throwaway PostgreSQL (`TEST_DATABASE_URL`). Memora
and VizhiOps are replaced by in-memory fakes that speak their HTTP contracts
(`tests/fakes.py`). Without a database only the unit tests run.

## Memora change

Ping needs retrieval without generation. Memora's `POST /api/v1/query` gained:

- `generate: bool = true`: `false` returns the ranked chunks, an empty
  `answer`, and makes no LLM call.
- `top_k: int | null` (1–20): chunks returned after reranking.
- `source_filename` on each chunk, so citations need no extra lookup.
- Embedding and LLM provider failures now return 503 instead of 500.

Existing callers are unaffected (defaults keep the old behaviour). Files:
`app/schemas/retrieval.py`, `app/api/routes/retrieval.py`,
`app/services/retrieval_service.py`.

## Known limits

- Crawls, status refresh and rate limiting run in-process (like Memora's
  extraction). With several workers, move them to a queue and Redis.
- Widget authorisation by `Origin` stops other websites, not scripts that
  forge headers; the per-visitor rate limit and monthly quota bound the cost.
- The embeddable `widget.js` itself is not part of this repo yet.
