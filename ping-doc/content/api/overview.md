---
title: API overview
description: Base URL, the three ways to authenticate, error format, pagination and streaming, and the conventions every endpoint follows.
---

The Pingie API is a JSON REST API. The dashboard, the widget and the admin console all use it. Everything on this page applies to every endpoint in the [API reference](/api-reference).

## Base URL

```text
https://api.pingie.app/api/v1
```

When self-hosting, it's your backend's origin plus `/api/v1` (locally `http://localhost:8080/api/v1`). Interactive Swagger docs are served by the backend at `/docs`.

## Authentication

There are three kinds of caller, and each endpoint accepts exactly one.

| Kind | Used by | How to authenticate |
| --- | --- | --- |
| **Dashboard session** | The dashboard, scripts acting as a user | The `ping_session` cookie set by `POST /auth/google`, or the same JWT as `Authorization: Bearer <token>`. |
| **Widget** | The embedded widget or your own chat UI | The browser's `Origin` header must be on the bot's allowed domains. Conversation routes also need `X-Conversation-Token`, returned when the conversation is started. |
| **Admin** | ping-admin (internal) | `Authorization: Bearer <admin token>` from `POST /admin/auth/google`, for allow-listed Google accounts only. |

The reference marks each endpoint with **session**, **widget**, **admin** or **public**.

### Getting a session token

`POST /auth/google` takes a Google ID token (from Google Identity Services, using Pingie's OAuth client) and returns the user while setting the cookie:

```bash
curl -i -X POST https://api.pingie.app/api/v1/auth/google \
  -H "Content-Type: application/json" \
  -d '{"id_token": "<google id token>"}'
```

Sessions last 7 days. `POST /auth/logout` clears the cookie.

## Errors

Errors return a JSON body with a human-readable `detail` and a stable machine-readable `code`:

```json
{ "detail": "Your plan allows 3 bots. Email support@pingie.app to upgrade your plan.", "code": "quota_exceeded" }
```

| Status | `code` | When |
| --- | --- | --- |
| 400 | `bad_request` | Malformed request. |
| 401 | `unauthenticated` | No session, or it's invalid or expired. |
| 402 | `quota_exceeded` | A plan limit was reached (messages, bots, sources, members, shares). |
| 402 | `plan_restriction` | The feature isn't on your plan (e.g. a model tier). |
| 403 | `forbidden` | Signed in but not allowed: a viewer making a change, a domain not allowed for the widget, a wrong email for an invite. |
| 404 | `not_found` | It doesn't exist, **or you have no access to it**. |
| 409 | `conflict` | Already exists or already done (duplicate domain, pending invite, accepted invite). |
| 422 | `validation_error` | The body or query failed validation. `detail` is a list of `{loc, msg}` for schema errors. |
| 429 | `rate_limited` | Too many requests; slow down and retry. |
| 503 | `service_unavailable` | Retrieval or the LLM gateway is temporarily unreachable. |

## Conventions

- **IDs.** Bots use short public IDs like `bot_7f3k2a9`. Everything else uses UUIDs.
- **Times** are ISO 8601 in UTC, e.g. `2026-10-14T09:21:07.512Z`.
- **Pagination.** Lists that can grow (conversations) return `{ items, next_before }`. Pass `next_before` back as `?before=` to get the next page; it's `null` on the last page.
- **Partial updates.** `PATCH` changes only the fields you send.
- **Empty successes** return `204 No Content`.
- **Roles.** Reads need viewer, changes need editor, and deleting a bot, clearing history and managing sharing need owner. See [Teams & sharing](/guides/sharing#roles).

## Streaming answers

`POST /widget/{bot_id}/conversations/{conversation_id}/messages` with `"stream": true` responds with `text/event-stream`:

```text
event: delta
data: {"text": "Go to Settings → Billing"}

event: delta
data: {"text": " → Invoices and click Export."}

event: done
data: {"message_id": "6f0c…", "text": "Go to Settings → Billing → Invoices and click Export.", "outcome": "answered",
       "citations": [{"source_name": "Billing handbook.pdf", "location": "p. 3"}],
       "asks_for_email": false, "offer_human": false, "status": "bot"}
```

- Append each `delta.text` to the visible answer, then use `done` for the stored message ID, outcome and citations.
- `EventSource` can't send a POST or custom headers, so read the stream from `fetch()`. See [Build a custom chat UI](/api/custom-widget).
- Without `stream`, the same `done` object is returned as plain JSON.

## Rate limits

| Scope | Limit |
| --- | --- |
| Widget messages | 20 per minute per visitor IP, per bot |
| Widget live-chat polls | 60 per minute per visitor IP, per bot |
| Monthly messages | Your plan's allowance, per workspace |

## Keeping this reference current

The [API reference](/api-reference) is generated from the backend's OpenAPI schema. After changing routes, regenerate it from `ping-doc` with `npm run gen:api`.
