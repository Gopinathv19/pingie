---
title: Architecture
description: The apps that make up Pingie, the services they rely on, and how a request flows through them.
---

## The pieces

Pingie is five small apps in one repository, plus two external services.

| App | What it is | Stack |
| --- | --- | --- |
| `ping-backend` | The API: auth, workspaces, bots, knowledge ingestion, the answer pipeline, the inbox, live chat, sharing and plans. It also serves `widget.js`. | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (Neon) |
| `ping-frontend` | The customer dashboard. | Next.js 16 (App Router), React 19, TypeScript, plain CSS |
| `ping-widget` | The embeddable chat widget: one IIFE file, no dependencies, Shadow DOM. | TypeScript, Vite |
| `ping-admin` | The Pingie team's console for workspaces and plans. | Next.js 16 |
| `ping-doc` | This documentation. | Next.js 16, Markdown |

| External service | Role |
| --- | --- |
| **Memora** | The retrieval engine. Pingie is one Memora *application*; every bot is a Memora *subject* and every source a Memora *source*. Memora does text extraction, chunking, embeddings, HNSW search, MMR diversification and reranking. |
| **VizhiOps** | The LLM gateway (OpenAI-compatible). Each model tier (`fast`, `balanced`, `best`) is a Vizhi model token; which model sits behind a tier is configured in Vizhi, not in Pingie. |

```text
                    ┌──────────────── ping-backend ─────────────────┐
 widget.js ──────▶  │ /api/v1/widget/*   Origin + conversation token│
 (your website)     │                                               │──▶ Memora   (retrieve)
                    │ reasoning pipeline ─────────────────────────────▶ VizhiOps (generate, SSE)
 dashboard ──────▶  │ /api/v1/*          session cookie (Google)    │
 (ping-frontend)    │                                               │──▶ PostgreSQL
 ping-admin ─────▶  │ /api/v1/admin/*    admin token                │──▶ SMTP (optional)
                    └───────────────────────────────────────────────┘
```

## Request paths

### A visitor asks a question

1. The widget loads `GET /widget/{bot}/config`. The backend checks the page's `Origin` against the bot's allowed domains.
2. On the first message it calls `POST /widget/{bot}/conversations` and gets a conversation ID and a signed **conversation token**.
3. `POST …/messages` with `stream: true` runs the [answer pipeline](/how-it-works/answer-pipeline) and streams the reply as server-sent events.
4. The reply is stored with its outcome, citations, latency, token counts and a reasoning trace. The inbox and analytics read from these rows.

### Your team uses the dashboard

The dashboard calls `/api/v1/*` through its own origin (`next.config.ts` rewrites to the backend), so the session cookie is first-party and no CORS setup is needed. Every bot route resolves the bot through your membership or a share; an ID in the URL is never trusted on its own.

### Knowledge ingestion

- **Files** are sent straight to Memora.
- **URLs and sitemaps** are fetched by the backend's crawler (robots.txt aware, SSRF-protected), converted from HTML to Markdown, and pushed to Memora as text.
- A background **sweeper** checks every 20 seconds which sources are still indexing and updates their progress.

### Live chat

There's no websocket layer. The conversation's `status` (`bot`, `waiting`, `human`, `closed`) lives in PostgreSQL, and both the widget and the dashboard poll small "updates since" endpoints. Agent presence is a heartbeat row per user. Because the database is the source of truth, this works across any number of API processes.

## Data model

```text
User ──< OrganizationMember >── Organization (plan + limits)
                                    │
                                    └──< Bot ──< BotSource (──> Memora source)
                                          ├──< AllowedDomain
                                          ├──< BotShare >── User
                                          ├──< BotAnswer       (team answers)
                                          └──< Visitor ──< Conversation ──< Message
                                                                └──< Lead
Plan (catalogue)    Invitation (workspace | bot)    AgentPresence (per user)
```

- **Plan limits are copied onto the organization row** when a plan is applied, so quota checks never join the plan table and a custom deal can override any single limit.
- Message rows keep `bot_id` denormalised, so analytics queries filter by bot and time without joins.
- Statuses and roles are plain strings, not database enums: adding a new value is a code change, not a migration.

## Repository layout

```text
ping-backend/
  app/
    api/routes/       one router per area (widget, bots, sources, conversations, sharing, live, …)
    services/         business logic (chat_service, live_service, sharing_service, plan_service, …)
    reasoning/        the answer pipeline: prompts, output parsing, small talk
    ingestion/        crawler and HTML → Markdown
    clients/          Memora and VizhiOps HTTP clients
    db/models/        SQLAlchemy models
  migrations/         Alembic revisions
  tests/              pytest, with in-memory fakes of Memora and Vizhi
ping-frontend/src/    app routes, components, lib/api.ts (typed client)
ping-widget/src/      index.ts (boot + window.Pingie), ui.ts, api.ts, storage.ts
ping-admin/src/       login, orgs, plans
ping-doc/             content/*.md, src/ (this site), scripts/export_openapi.py
```
