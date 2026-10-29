---
title: Deployment
description: What to set and check before running Pingie in production.
---

> **Note** Internal. The repository doesn't include deployment configuration (Docker, CI) yet; this page lists what any deployment needs.

## Backend

Run it as a standard ASGI app:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers
```

Run migrations on every release, before starting the new version.

### Production checklist

- [ ] `ENVIRONMENT=production`
- [ ] Long random `AUTH_JWT_SECRET` and `ADMIN_JWT_SECRET`, different from each other
- [ ] `AUTH_COOKIE_SECURE=true` (serve over HTTPS)
- [ ] `GOOGLE_CLIENT_ID` set, with every production origin added to the OAuth client
- [ ] `CORS_ORIGINS`: the dashboard's production origin
- [ ] `APP_URL`: the dashboard's production URL (used in invite links)
- [ ] `WIDGET_SCRIPT_URL`: where `widget.js` is served (the backend's `/widget.js` or a CDN)
- [ ] `ADMIN_EMAILS`: only the team members who need it
- [ ] `MEMORA_*` and `VIZHI_*` tokens for production instances
- [ ] SMTP configured, if you want handoff, missed-chat and invitation emails sent
- [ ] `CRAWL_ALLOW_PRIVATE_HOSTS` left at `false`

### Behind a proxy or CDN

- Pass `X-Forwarded-For`. Rate limits key on the visitor's IP.
- Visitor location comes from CDN geo headers when present (Cloudflare and Vercel are supported).
- Don't buffer streamed responses: answers use server-sent events (the backend sends `X-Accel-Buffering: no` for nginx).
- `/widget.js` is served with a 5-minute cache.

### Scaling notes

Some state lives inside each backend process today:

| Component | Current behaviour | When you run more than one process |
| --- | --- | --- |
| Rate limiter | In-memory sliding window | Each process counts separately. Move it to Redis. |
| Crawls and the indexing sweeper | Background threads in the API process | Run the sweeper in one process only (`STATUS_SWEEPER_ENABLED=false` elsewhere). Crawls interrupted by a restart are marked failed and can be re-synced. |
| Live chat | Database plus polling | Already works across processes. |

## Dashboard, admin and docs

All three are Next.js apps:

```bash
npm ci
npm run build
npm run start      # or deploy to Vercel or any Node host
```

- **ping-frontend**: set `BACKEND_URL` (server-side, used by the `/api/v1` rewrite) and `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.
- **ping-admin**: same two variables. Keep it on a separate, private hostname (e.g. `admin.pingie.app`).
- **ping-doc**: no variables. Run `npm run gen:api` before building whenever the API changed.

## Widget

```bash
cd ping-widget
npm ci
npm run build:backend     # copies dist/widget.js into the backend (served at /widget.js)
# or: npm run build and upload dist/widget.js to your CDN, then set WIDGET_SCRIPT_URL
```

Changes to the widget reach customer sites as soon as the new file is served; there's no per-site install step.
