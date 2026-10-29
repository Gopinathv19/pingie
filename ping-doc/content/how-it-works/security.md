---
title: Security & privacy
description: How Pingie authenticates people and widgets, isolates workspaces, and protects your servers and visitors.
---

## Dashboard sign-in

- **Google is the only sign-in.** The dashboard sends Google's ID token to `POST /auth/google`. The backend verifies it with Google and checks that the token was issued for Pingie's client ID and that the email is verified.
- The backend then sets an **HttpOnly** `ping_session` cookie containing a signed JWT that's valid for 7 days. The same JWT is also accepted as `Authorization: Bearer`.
- The dashboard calls the API through its own origin, so the cookie is first-party and `SameSite=Lax`.

## Access control

- Every bot route resolves the bot through **your membership of its workspace** or **a direct share**, never from the ID alone.
- **No access** returns `404` (*Bot not found*), so outsiders can't learn which IDs exist. **Too low a role** returns `403`.
- Roles rank `viewer` < `editor` < `owner`. Reads need viewer, changes need editor, and destructive or sharing actions need owner.
- Invitation links contain a random token; only its SHA-256 hash is stored. Accepting requires being signed in with the **invited email**.

## The widget

The widget can't use a session: it runs on your customers' sites. Instead:

- **Origin check.** Every widget request's `Origin` header must match one of the bot's **allowed domains** (`help.acme.com` or `*.acme.com`). Localhost works only when *Allow localhost* is on, and draft bots work only on localhost.
- **Conversation token.** Starting a conversation returns a signed token bound to that conversation and bot, valid for 30 days. Every later call for that conversation must send it as `X-Conversation-Token`, so one visitor can't read or write another's chat even if a conversation ID leaks.
- **Rate limits.** Each bot accepts 20 messages per minute per visitor IP, and 60 live-chat polls per minute.
- **Monthly quota.** When the workspace's message allowance is used up, the widget stops answering (`402`).
- **Rendering.** The widget escapes all text before applying Markdown, and runs inside a Shadow DOM.

## Crawling your sites

Fetching user-supplied URLs from a server is a classic SSRF risk, so the crawler:

- refuses private, loopback and link-local addresses (only a local-development setting turns this off),
- follows `robots.txt` and identifies itself as `PingieBot/1.0 (+https://pingie.app/bot)`,
- caps crawls at 200 pages, a 15-second timeout and 5 MB per page.

## What's stored

| Data | Purpose |
| --- | --- |
| Your Google name, email and avatar | Sign-in and team features. |
| Sources | Text and embeddings in Memora; metadata in Pingie. Deleting a source or bot deletes them in Memora too. |
| Conversations and messages | The inbox, analytics and live chat. Owners can clear a bot's history at any time. |
| Visitors | An anonymous ID from the widget, plus an email or name only if the visitor gives one or your site calls `Pingie.identify()`. Approximate location comes from your CDN's geo headers when present. |
| Leads | The email and question captured on fallback. |

## Admin access

The Pingie team's admin console uses a separate sign-in: Google accounts on an **allow-list**, issued a short-lived admin token signed with its own secret. A leaked dashboard secret can't mint admin tokens.

> **Important** If you self-host, set strong `AUTH_JWT_SECRET` and `ADMIN_JWT_SECRET` values and `AUTH_COOKIE_SECURE=true` in production. See [Configuration](/internal/configuration).
