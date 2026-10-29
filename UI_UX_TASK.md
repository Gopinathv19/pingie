# Task: UI/UX redesign for Pingie

You are a senior product designer and frontend engineer working in this repository. The goal is to make Pingie look and feel like a polished, trustworthy SaaS that businesses are happy to pay for, **without changing backend API contracts**.

Work in this order:

1. **Ask me questions first.** Before proposing anything, ask me up to 8 clarifying questions. Cover:
   - brand feel
   - target customers
   - whether a light theme is wanted
   - mobile priority
   - any reference products I like
   - anything else you need
2. **Audit.** Go through every screen listed below. For each one, report:
   - what works
   - what is confusing or unpolished
   - concrete improvements, each tagged with impact (High/Med/Low) and effort (S/M/L)
3. **Propose.** Give me a prioritised plan grouped into phases. Wait for my approval before coding.
4. **Implement phase by phase.** Keep each phase PR-sized and reviewable. After each phase:
   - run `npm run lint` in every app you touched
   - start the dev server and check every changed screen in a browser, at desktop width and at 390px wide
   - tell me what changed and what to look at

---

## 1. Product

Pingie (pingie.app) is an AI customer-support chatbot SaaS.

- **Setup:** a business signs in with Google, creates a bot, and adds knowledge: a sitemap crawl, URLs, or uploaded PDF / DOCX / TXT / MD / CSV files. It then embeds a one-line `<script>` widget on its site.
- **Answers:** visitors ask questions. The bot answers only from those sources, with citations.
- **Fallback:** when the bot can't answer, it asks for the visitor's email, which creates a lead and a handoff.
- **Users:** small and medium businesses, mostly non-technical support or marketing people. A first-time user should get from signup to a live bot in under 10 minutes.

**Plans** are stored in the database and edited from the admin console. They are shown on `/pricing` and in the Upgrade modal.

| Plan | Price | Messages/mo | Bots | Sources/bot | Team members | Model tiers | Branding badge |
|---|---|---|---|---|---|---|---|
| Free | $0 | 100 | 3 | 5 | 1 | Fast | Always shown |
| Pro | $49 | 100k | 10 | 25 | 5 | Fast, Balanced | Can be removed |
| Enterprise | Custom | Unlimited | Unlimited | Unlimited | Unlimited | All | Can be removed |

There is no self-serve payment. To upgrade, the customer emails support@pingie.app and an admin changes the plan in ping-admin.

## 2. Repo layout

| Folder | What it is |
|---|---|
| `ping-frontend/` | Customer dashboard. Next.js 16 (App Router), React 19, TypeScript, plain CSS. **Main target of this task.** |
| `ping-widget/` | The embeddable chat widget: vanilla TypeScript, Shadow DOM, built with Vite into a single `widget.js` of about 8 kB gzipped. |
| `ping-admin/` | Internal admin console on port 3001: Google sign-in for allow-listed emails, organization list, plan management. |
| `ping-backend/` | FastAPI API. **Do not change it** unless I agree. |

## 3. Current design system (`ping-frontend`)

- Dark theme only (`color-scheme: dark`). The background is `#0a0a0b` and the accent is violet `#8b5cf6`, with ok/warn/danger colours.
- Global design tokens and utility classes live in `src/app/globals.css`: `.btn`, `.btn-primary`, `.badge`, `.panel`, `.field`, `.segmented`, `.kpi`, `.page`.
- Each feature has its own CSS module (`*.module.css`).
- Fonts are Geist Sans and Geist Mono.
- Icons are a custom set of about 30 single-path SVG line icons in `src/components/Icon.tsx`.
- Charts are hand-built SVG in `src/components/charts/` (LineChart, Donut).
- Shared UI pieces are in `src/components/ui/`: Panel, PageHeader, KpiGrid, StatusBadge, Toggle, and States (Loading, ErrorState, InlineError).

## 4. Screens

### Top-level dashboard pages (top bar only)

- `/login`: Google sign-in.
- `/bots`: grid of bot cards showing status, domain, conversations in the last 30 days, resolution rate and source count. A bot-limit banner opens the Upgrade modal.
- `/bots/new`: a 3-step wizard (Basics → Knowledge → Launch). Knowledge offers a sitemap crawl, file upload, or "skip for now".
- `/pricing`: plan cards loaded from the API, plus a copy-email contact block.
- `/settings/billing`: current plan, usage bars, limits table, upgrade prompts.

### Inside a bot: `/bots/[botId]/...` (top bar and sidebar)

- **Overview:** KPIs, a 24h/7d/30d/90d range picker, a conversations line chart, an answer-outcomes donut, messages per day, top pages, knowledge gaps and top questions.
- **Conversations:** an inbox with All / Unanswered / Disliked / Handoffs filters, search, "load more" and CSV export. The transcript shows outcome badges, citations and thumbs feedback.
- **Knowledge → Sources:** upload, add a URL or sitemap, and a table with status, progress, chunk count, re-sync and delete.
- **Knowledge → Test retrieval:** run a query with Top-K and threshold. Shows the rewritten query, ranked chunks with scores, the answer with citations, and timings.
- **Widget → Appearance:** title, welcome message, placeholder, suggested questions, accent colour, theme, launcher icon, position, show sources, branding badge (locked on Free). A live preview is drawn on a mock page.
- **Widget → Install & embed:** setup steps, the snippet, an install check, IDs, and the JS API.
- **Widget → Allowed domains:** add or remove hostnames, last seen, and an allow-localhost toggle.
- **Manage → Bot settings:**
  - General: name, website, status, offline message.
  - Answering: instructions, model tier (locked by plan), tone, reply language, similarity threshold.
  - Fallback & handoff.
  - Danger zone.

### Top bar

Breadcrumb (Pingie / org switcher with plan tag / bot switcher), ⌘K command palette, Docs, Support, Upgrade (opens the Upgrade modal), and an account menu.

### Widget (`ping-widget/`)

- Launcher button, header, welcome message and suggestion chips.
- Streamed Markdown answers with source chips and thumbs up/down.
- Email capture on fallback, and an offline state.
- "Powered by Pingie" badge.
- Full-screen on phones, plus dark and light themes.

## 5. UX problems already spotted (verify these, and find more)

- The **Docs** and **Support** links in the top bar are `href="#"`.
- `/pricing` and `/settings/billing` aren't linked from the sidebar, the account menu or the ⌘K palette.
- There is **no leads screen**, even though the API call `api.conversations.leads` already exists. Leads only appear through the Handoffs filter.
- The **account menu** only has "Log out": no profile, billing or plan entry.
- The **org switcher** only ever shows one org, so it looks broken.
- **Onboarding:** the wizard drops the user on the Sources page with no "what next" checklist (add knowledge → test → customise → install → go live).
- **Empty states** are thin: for example "No conversations yet." has no illustration and no call to action.
- **Upgrade prompts** are inconsistent across screens: banners, badges and the modal.
- **Mobile and tablet layouts** of the dashboard are unverified.
- **No light theme** in the dashboard, though the widget has one.
- The **admin console** (`ping-admin/`) is functional but bare. Lower priority.

## 6. Constraints

- Keep Next.js, React 19 and plain CSS modules. **Ask me before adding any UI library** (Tailwind, shadcn, Radix, Framer, etc.).
- Reuse and extend the existing tokens and components in `globals.css` and `src/components/ui/` rather than adding one-off styles.
- **Don't change API request or response shapes.** The types are in `ping-frontend/src/lib/types.ts`.
- **Accessibility:** use semantic elements and aria labels, make everything keyboard-reachable with visible focus, and keep colour contrast at AA or better.
- **Widget:** must stay small (well under 15 kB gzipped) and isolated in Shadow DOM.
- Never commit secrets, and don't touch `.env` files.

## 7. Running locally

```bash
# backend (port 8080)
cd ping-backend && .venv/bin/uvicorn app.main:app --reload --port 8080
# dashboard (port 3000)
cd ping-frontend && npm run dev
# admin console (port 3001)
cd ping-admin && npm run dev
# widget
cd ping-widget && npm run build:backend
```

Type-check each app with `npm run lint`.
