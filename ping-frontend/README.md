# ping-frontend

Dashboard UI for Pingie: AI support bots that answer from your docs and embed on your websites.
Built with Next.js 16 (App Router), React 19 and TypeScript. Styling is plain CSS with design tokens
taken from the design reference (`src/app/globals.css`), with no UI framework. All data comes from
[ping-backend](../ping-backend); sign-in is Google only.

## Run

Start ping-backend first (port 8080 by default), then:

```bash
cp .env.example .env.local   # set NEXT_PUBLIC_GOOGLE_CLIENT_ID (and BACKEND_URL if not :8080)
npm install
npm run dev                  # http://localhost:3000
```

The browser only ever talks to this app: `next.config.ts` forwards `/api/v1/*` to `BACKEND_URL`,
so the session cookie is first-party and there is no CORS setup. In Google Cloud Console, add
`http://localhost:3000` (and your production origin) as an authorized JavaScript origin of the OAuth
client; the same client id goes in `ping-backend/.env` as `GOOGLE_CLIENT_ID`.

## Routes

| Route | Screen |
| --- | --- |
| `/login` | Log in / sign up |
| `/bots` | All bots, plan usage |
| `/bots/new` | Create-a-bot wizard |
| `/bots/[botId]` | Overview (KPIs, charts, gaps, top questions) |
| `/bots/[botId]/conversations` | Inbox with filters and transcripts |
| `/bots/[botId]/knowledge` | Sources: upload, add URL / sitemap, index status |
| `/bots/[botId]/test` | Test retrieval: chunks, scores, generated answer |
| `/bots/[botId]/appearance` | Widget customization with live preview |
| `/bots/[botId]/install` | Embed snippets, verification, identifiers |
| `/bots/[botId]/domains` | Allowed domains |
| `/bots/[botId]/settings` | Instructions, model, fallback, danger zone |

Signed-out visits to any dashboard page go to `/login`. Press `⌘K` / `Ctrl+K` anywhere to search.

## Structure

```
src/
  app/
    (auth)/login           login page
    (org)/bots             org-scoped pages (top bar only)
    (bot)/bots/[botId]     bot-scoped pages (top bar + sidebar)
  components/
    shell/                 Topbar, Sidebar, CommandPalette
    ui/                    Panel, PageHeader, KpiGrid, StatusBadge, Toggle
    charts/                LineChart, Donut
    overview/ conversations/ knowledge/ widget/ settings/   page views
  components/session/      SessionProvider (user + org), BotProvider (current bot)
  lib/
    api.ts                 typed client for ping-backend
    use-api.ts             data-loading + mutation hooks (401 → /login)
    types.ts               API response types
    format.ts              dates, sizes, durations
    nav.ts                 sidebar config
```
