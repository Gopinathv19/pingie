---
title: Configuration
description: Every backend setting, read from the environment or ping-backend/.env.
---

Settings are read from environment variables, or from `ping-backend/.env`. Names are case-insensitive, and the defaults are shown below.

## Core

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `local` | `local` or `production`. |
| `DATABASE_URL` | — | PostgreSQL URL with the `postgresql+psycopg://` driver prefix. For Neon, keep `?sslmode=require`. |
| `CORS_ORIGINS` | `http://localhost:3000,…` | Dashboard origins allowed to call the API directly. The widget uses allowed domains instead. |
| `WIDGET_SCRIPT_URL` | `https://cdn.pingie.app/widget.js` | The script URL shown in install snippets. |
| `APP_URL` | `http://localhost:3000` | Dashboard base URL, used in invitation links. |
| `SUPPORT_EMAIL` | `support@pingie.app` | Shown in upgrade and quota messages. |

## Dashboard auth

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | — | The OAuth client whose ID tokens are accepted. Required for sign-in. |
| `AUTH_JWT_SECRET` | `change-me-in-production` | Signs session and conversation tokens. **Set a long random value.** |
| `AUTH_JWT_ISSUER` | `ping` | Issuer claim in tokens. |
| `AUTH_TOKEN_TTL_MINUTES` | `10080` (7 days) | Session lifetime. |
| `AUTH_COOKIE_NAME` | `ping_session` | Session cookie name. |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS only). |
| `AUTH_COOKIE_SAMESITE` | `lax` | Cookie SameSite policy. |

## Admin console

| Variable | Default | Purpose |
| --- | --- | --- |
| `ADMIN_EMAILS` | — | Comma-separated Google emails allowed into ping-admin. Empty means nobody. |
| `ADMIN_JWT_SECRET` | `change-me-admin-secret` | Signs admin tokens (separate from `AUTH_JWT_SECRET`). |
| `ADMIN_TOKEN_TTL_MINUTES` | `480` (8 hours) | Admin session lifetime. |

## Retrieval and LLM

| Variable | Default | Purpose |
| --- | --- | --- |
| `MEMORA_BASE_URL` | `http://localhost:8000` | Memora API. |
| `MEMORA_API_TOKEN` | — | A `memora_…` credential for the Memora application that represents Pingie. |
| `MEMORA_TIMEOUT_SECONDS` | `180` | Memora can be slow on cold starts and reranking. |
| `MODEL_PROVIDER` | `vizhi` | Where LLM calls go: `vizhi` (the gateway), `nebius` or `build-nvidia` (direct). |
| `LLM_TIMEOUT_SECONDS` | `180` | LLM call timeout for any provider. `VIZHI_TIMEOUT_SECONDS` is still accepted. |
| `VIZHI_BASE_URL` | `http://localhost:8001` | VizhiOps gateway. |
| `VIZHI_TOKEN_BALANCED` | — | `vz_live_…` token for the balanced tier. Unset tiers fall back to this one. |
| `VIZHI_TOKEN_FAST` | — | Token for the fast tier (also used to condense follow-up questions). |
| `VIZHI_TOKEN_BEST` | — | Token for the best tier. |
| `NVIDIA_API_KEY` | — | build.nvidia.com key (`nvapi-…`), used when `MODEL_PROVIDER=build-nvidia`. |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | build.nvidia.com API. |
| `NEBIUS_API_KEY` | — | Nebius Token Factory key, used when `MODEL_PROVIDER=nebius`. |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` | Nebius API. |
| `LLM_MODEL_BALANCED` | `nvidia/nemotron-3-super-120b-a12b` | Model for the balanced tier on direct providers. Unset tiers fall back to this one. |
| `LLM_MODEL_FAST` | — | Model for the fast tier on direct providers. |
| `LLM_MODEL_BEST` | — | Model for the best tier on direct providers. |
| `LLM_DISABLE_THINKING` | `true` | Ask direct providers to skip the model's thinking phase. Turn off if a model rejects it. |

## Reasoning

| Variable | Default | Purpose |
| --- | --- | --- |
| `REASONING_TOP_K` | `5` | Passages requested per question. |
| `REASONING_MIN_SIMILARITY` | `0.30` | Default similarity floor (each bot can override it). |
| `REASONING_HISTORY_TURNS` | `6` | Prior turns sent with each question. |
| `REASONING_MAX_ANSWER_TOKENS` | `700` | Answer length cap. |
| `REASONING_TEMPERATURE` | `0.2` | Generation temperature. |

## Knowledge ingestion

| Variable | Default | Purpose |
| --- | --- | --- |
| `UPLOAD_MAX_BYTES` | `26214400` (25 MB) | Maximum upload size. |
| `CRAWL_MAX_PAGES` | `200` | Pages per sitemap crawl. |
| `CRAWL_CONCURRENCY` | `4` | Parallel page fetches. |
| `CRAWL_TIMEOUT_SECONDS` | `15` | Per-page timeout. |
| `CRAWL_MAX_PAGE_BYTES` | `5242880` (5 MB) | Per-page size cap. |
| `CRAWL_USER_AGENT` | `PingieBot/1.0 (+https://pingie.app/bot)` | Crawler user agent. |
| `CRAWL_ALLOW_PRIVATE_HOSTS` | `false` | Allow crawling private/loopback addresses. **Local development only.** |
| `STATUS_SWEEPER_ENABLED` | `true` | Background check of sources still indexing. |
| `STATUS_SWEEPER_INTERVAL_SECONDS` | `20` | How often it runs. |

## Widget and live chat

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIDGET_RATE_LIMIT_PER_MINUTE` | `20` | Messages per visitor IP per bot. |
| `WIDGET_POLL_RATE_LIMIT_PER_MINUTE` | `60` | Live-chat polls per visitor IP per bot. |
| `WIDGET_CONVERSATION_TTL_HOURS` | `720` (30 days) | Conversation token lifetime. |
| `HANDOFF_WAIT_SECONDS` | `120` | How long a visitor waits for a person before being asked for an email. |

## Email (optional)

Used for handoff, missed-chat and invitation emails. When `SMTP_HOST` is unset, emails are only logged.

| Variable | Default |
| --- | --- |
| `SMTP_HOST` | — |
| `SMTP_PORT` | `587` (STARTTLS) |
| `SMTP_USERNAME` | — |
| `SMTP_PASSWORD` | — |
| `SMTP_FROM` | `Pingie <no-reply@pingie.app>` |

## Front-end apps

| App | Variable | Purpose |
| --- | --- | --- |
| ping-frontend | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google sign-in button. |
| ping-frontend | `BACKEND_URL` | Where `/api/v1/*` is proxied (default `http://localhost:8080`). |
| ping-frontend | `NEXT_PUBLIC_DOCS_URL` | Where the top bar's **Docs** link points (default `http://localhost:3003`). |
| ping-admin | `BACKEND_URL`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Same as above. |
| ping-widget | `VITE_API_BASE` | API origin baked into the build (otherwise the script's own origin). |
