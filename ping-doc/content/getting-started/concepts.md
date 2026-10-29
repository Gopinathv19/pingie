---
title: Core concepts
description: The objects Pingie works with and the words used across the dashboard and API.
---

## Workspace

A **workspace** (called an *organization* in the API) owns bots and holds the plan and its limits. Everyone gets a personal workspace on first sign-in. You can also be a member of workspaces other people invited you to, and switch between them from the top bar.

Each member has a **role**:

| Role | Can do |
| --- | --- |
| `owner` | Everything, including deleting bots, clearing history, renaming the workspace and managing members and sharing. |
| `editor` | Change bots: settings, knowledge, appearance and domains. Reply in live chat. Create bots in the workspace. |
| `viewer` | Read only: overview, conversations, sources and test retrieval. |

## Bot

A **bot** is one assistant with its own sources, settings, appearance and allowed domains. Its public ID looks like `bot_7f3k2a9`, and you put it in the widget snippet.

A bot has a **status**:

| Status | Behaviour |
| --- | --- |
| `draft` | The widget loads only on `localhost`, and only with *Allow localhost* on. Use it to try things out. |
| `live` | The widget loads on the allowed domains and answers visitors. |
| `paused` | The widget shows *Offline* and every message gets the bot's offline message. |

## Source

A **source** is a piece of knowledge: an uploaded file, a single web page, or a sitemap (which becomes many page sources). Sources are chunked and embedded for retrieval. Their status goes `queued` → `indexing` → `ready`, or ends as `failed` with an error.

**Team answers** is a special text source that holds the answers your team taught the bot from the inbox. See [Live chat](/guides/live-chat#teach-the-bot).

## Conversation, message and visitor

- A **visitor** is an anonymous person on your site. The widget remembers them with an ID in `localStorage`, and they appear as "Visitor #4821" until they share an email or you call [`Pingie.identify()`](/guides/javascript-api).
- A **conversation** is one chat. It has a **status** that says who is answering: `bot`, `waiting` (the visitor asked for a person), `human` (an agent is replying) or `closed`.
- A **message** has a **role**: `visitor`, `bot`, `agent` (a person on your team) or `system` (a short note such as "Zara joined the chat").

## Outcome

Every bot reply gets an **outcome**:

| Outcome | Meaning |
| --- | --- |
| `answered` | Answered from your sources, with citations. |
| `partial` | Part of the question was answered; the rest wasn't in the sources. |
| `fallback` | Nothing relevant was found, so the bot said it doesn't know. |
| `smalltalk` | A greeting or thanks, answered without searching. |
| `lead` | The visitor left their email after a fallback. |
| `offline` | The bot is paused. |

A conversation's outcome is the **worst** answer outcome in it (`answered` < `partial` < `fallback`). The inbox's *Unanswered* filter is conversations whose outcome is `fallback`.

## Lead and handoff

When the bot can't answer, it can ask for the visitor's email. That email becomes a **lead**: it's saved with the unanswered question and emailed to the bot's **handoff email**. With [live chat](/guides/live-chat), the visitor can instead ask to talk to a person straight away.

## Model tier

Each bot uses a **model tier** for writing answers: `fast` (lowest latency), `balanced` (the default) or `best` (highest quality). Which tiers you can pick depends on your [plan](/guides/plans).
