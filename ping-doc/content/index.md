---
title: Introduction
description: Pingie gives your website an AI support assistant that answers only from your own documentation, and hands the conversation to a person when it can't.
---

Pingie is a support chatbot you train on your own content: help-center pages, PDFs, policies, product docs. Visitors ask questions in a small chat widget on your site. Pingie answers from your sources, shows which document each answer came from, and admits when it doesn't know instead of making something up.

When the bot can't answer, your team takes over. Visitors can ask for a person, an agent replies live from the dashboard, and the answer can be taught back to the bot so the same question is answered next time.

<div class="cards">
  <a class="card" href="/getting-started/quickstart"><strong>Quickstart →</strong>Go from sign-in to a live bot on your site in about ten minutes.</a>
  <a class="card" href="/guides/widget"><strong>Install the widget →</strong>One script tag, allowed domains, and going live.</a>
  <a class="card" href="/how-it-works/answer-pipeline"><strong>How answers work →</strong>Retrieval, the similarity floor, citations and fallbacks.</a>
  <a class="card" href="/api-reference"><strong>API reference →</strong>Every REST endpoint, generated from the backend.</a>
</div>

## What you can do with Pingie

| Area | What it gives you |
| --- | --- |
| **Knowledge** | Crawl a sitemap (up to 200 pages), add single URLs, or upload PDF, DOCX, TXT, MD and CSV files up to 25 MB. Test retrieval before going live. |
| **Widget** | A lightweight chat widget (~10 kB gzipped) that streams answers with source chips. Change the colours, text, launcher icon, position and theme. |
| **Inbox** | Every conversation with outcome badges, filters for unanswered, disliked and handed-off chats, search, and CSV export. |
| **Live chat** | "Talk to a person" when the bot can't answer, agent presence, browser alerts, and taking over any chat. |
| **Teach the bot** | Turn an unanswered question into a saved answer the bot uses from then on. |
| **Analytics** | Conversations, resolution rate, first-response time, thumbs-down rate, knowledge gaps and top questions. |
| **Teams** | Invite editors and viewers to a workspace, or share a single bot with someone outside it. |

## How the pieces fit

```text
 Your website                       Pingie
┌───────────────┐   widget API   ┌──────────────────────────────┐
│ <script> tag  │ ─────────────▶ │ ping-backend (FastAPI)       │
│ chat widget   │ ◀── answers ── │  ├─ retrieval: Memora        │
└───────────────┘   (streamed)   │  └─ generation: VizhiOps LLM │
                                 └──────────────┬───────────────┘
 Your team                                      │
┌───────────────┐   dashboard API               │
│ Dashboard     │ ◀─────────────────────────────┘
│ (inbox, live  │
│  chat, setup) │
└───────────────┘
```

See [Architecture](/how-it-works/architecture) for the full picture.

## Where to go next

- New here? Start with the [Quickstart](/getting-started/quickstart), then read [Core concepts](/getting-started/concepts).
- Embedding on a site? [Install the widget](/guides/widget) and look at the [JavaScript API](/guides/javascript-api).
- Building an integration? Read the [API overview](/api/overview) and the [API reference](/api-reference).
