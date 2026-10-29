---
title: Local development
description: Run the whole Pingie stack on your machine.
---

> **Note** This section is for the Pingie team and anyone self-hosting.

## Prerequisites

- Python **3.12** and Node.js **20+**
- A PostgreSQL database. Neon works, and so does a local Postgres; the schema uses `gen_random_uuid()`.
- Access to a **Memora** instance (retrieval) and a **VizhiOps** gateway (LLM), with tokens.
- A Google OAuth client ID (Google Cloud Console → Credentials) with these **Authorized JavaScript origins**: `http://localhost:3000` for the dashboard and `http://localhost:3001` for admin.

## Ports

| App | Port | Command |
| --- | --- | --- |
| ping-backend | 8080 | `.venv/bin/uvicorn app.main:app --reload --port 8080` |
| ping-frontend | 3000 | `npm run dev` |
| ping-admin | 3001 | `npm run dev` |
| ping-doc | 3003 | `npm run dev` |
| ping-widget (playground) | 5173 | `npm run dev` |

## 1. Backend

```bash
cd ping-backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill DATABASE_URL, AUTH_JWT_SECRET, GOOGLE_CLIENT_ID, MEMORA_*, VIZHI_*
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Check it: `curl localhost:8080/health`. Interactive API docs are at `http://localhost:8080/docs`.

Generate secrets with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

To crawl sites running on your own machine, set `CRAWL_ALLOW_PRIVATE_HOSTS=true`. Use it only in local development.

## 2. Dashboard

```bash
cd ping-frontend
cp .env.example .env.local    # NEXT_PUBLIC_GOOGLE_CLIENT_ID, BACKEND_URL (default http://localhost:8080)
npm install
npm run dev
```

The dashboard proxies `/api/v1/*` to `BACKEND_URL`, so the session cookie is first-party.

## 3. Widget

```bash
cd ping-widget
npm install
npm run build:backend         # builds dist/widget.js and copies it to ping-backend/app/static/
```

The backend now serves it at `http://localhost:8080/widget.js`. To try it on a page, create a bot, turn on **Allow localhost** under Allowed domains, and add:

```html
<script src="http://localhost:8080/widget.js" data-bot-id="bot_xxxxxxx" defer></script>
```

For widget development with hot reload: `cp .env.example .env` (`VITE_API_BASE=http://localhost:8080`), then `npm run dev` and open `http://localhost:5173/?bot=bot_xxxxxxx`.

## 4. Admin console

```bash
cd ping-admin
# .env: BACKEND_URL=http://localhost:8080, NEXT_PUBLIC_GOOGLE_CLIENT_ID=<same client id>
npm install
npm run dev
```

Add your Google email to `ADMIN_EMAILS` in `ping-backend/.env` and restart the backend. See [Admin console](/internal/admin-console).

## 5. Docs (this site)

```bash
cd ping-doc
npm install
npm run gen:api               # regenerate src/data/openapi.json from the backend
npm run dev
```

Pages are Markdown files in `content/`; the sidebar is `src/lib/nav.ts`.

## Tests and checks

```bash
# backend: needs a throwaway database; every test truncates the tables
cd ping-backend
.venv/bin/pip install pytest
TEST_DATABASE_URL=postgresql+psycopg://…/ping_test .venv/bin/python -m pytest

# front-end apps type-check with:
npm run lint
```

> **Warning** Never point `TEST_DATABASE_URL` at a real database. The fixtures `TRUNCATE` every table before each test.

The tests replace Memora and VizhiOps with in-memory fakes (`tests/fakes.py`), so they need no external services.

## Database migrations

```bash
cd ping-backend
.venv/bin/alembic revision -m "describe the change"   # write upgrade()/downgrade() by hand
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Tables are created only by Alembic, never at app start-up.
