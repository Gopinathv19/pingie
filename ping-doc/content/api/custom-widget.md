---
title: Build a custom chat UI
description: Use the public widget API directly to put Pingie inside your own interface, step by step, including streaming and live chat.
---

The standard widget covers most sites. If you want the chat inside your own UI (a help panel in your app, a native-looking component), call the same public **widget API** it uses. All requests go from the visitor's browser, so the `Origin` check applies. Make sure your site's hostname is in the bot's **allowed domains**.

```js
const API = "https://api.pingie.app/api/v1/widget/bot_xxxxxxx";
```

## 1. Load the configuration

```js
const config = await fetch(`${API}/config`).then((r) => r.json());
// {
//   bot_id: "bot_xxxxxxx", name: "Acme Help", status: "live",
//   online: true,              // false when paused (or draft off localhost)
//   agents_online: false,      // someone is available for live chat
//   appearance: { title, welcome, placeholder, accent, theme, position,
//                 launcher, suggestions: [...], show_sources, show_branding }
// }
```

A `403` means this origin isn't allowed, or the bot is a draft and you're not on localhost. A `404` means the bot ID is wrong.

## 2. Start a conversation

Create one on the visitor's first message. Keep a stable `visitor_id` per browser (8–64 characters, letters, digits, `_` or `-`), so returning visitors are recognised.

```js
const visitorId = localStorage.visitorId ??= crypto.randomUUID().replaceAll("-", "");
const { conversation_id, token } = await fetch(`${API}/conversations`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ visitor_id: visitorId, page_url: location.href }),
}).then((r) => r.json());
```

Store both. Every later call for this conversation sends `X-Conversation-Token: <token>`. The token lasts 30 days; if you get a `401` or `404`, start a new conversation.

## 3. Send a message and stream the answer

```js
async function ask(text, onDelta) {
  const res = await fetch(`${API}/conversations/${conversation_id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Conversation-Token": token },
    body: JSON.stringify({ text, stream: true }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", done = null;
  for (;;) {
    const { value, done: end } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const event = /^event: (\w+)/m.exec(block)?.[1];
      const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] ?? "null");
      if (event === "delta") onDelta(data.text);
      if (event === "done") done = data;
    }
    if (end) break;
  }
  return done; // { message_id, text, outcome, citations, asks_for_email, offer_human, status }
}
```

What to do with `done`:

| Field | Use |
| --- | --- |
| `outcome` | `answered`, `partial`, `fallback`, `smalltalk`, `lead`, `offline`, or `human` (a person has the chat and will reply by polling; there's no bot text). |
| `citations` | Show them as sources: `source_name`, plus `location` (a URL for web pages). |
| `asks_for_email` | Show an email field. Send the email as the **next message**; the backend saves it as a lead. |
| `offer_human` | Show a "Talk to a person" button (see [live chat](#live-chat)). |
| `message_id` | Needed for feedback. |

## 4. Feedback and identity

```js
// thumbs up / down on a bot answer
await fetch(`${API}/conversations/${conversation_id}/messages/${messageId}/feedback`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Conversation-Token": token },
  body: JSON.stringify({ value: "down" }),
});

// attribute the chat to a signed-in user
await fetch(`${API}/conversations/${conversation_id}/identify`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Conversation-Token": token },
  body: JSON.stringify({ email: "jane@acme.com", name: "Jane Doe" }),
});
```

## Live chat

When `done.offer_human` is `true`, let the visitor ask for a person:

```js
const { status } = await fetch(`${API}/conversations/${conversation_id}/handoff`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Conversation-Token": token },
  body: "{}",
}).then((r) => r.json());
// "waiting": an agent was online, start polling
// "unavailable": nobody online, a system message asking for the email follows
```

Then poll for agent and system messages, passing the newest `created_at` you've seen:

```js
let after;
async function poll() {
  const q = after ? `?after=${encodeURIComponent(after)}` : "";
  const u = await fetch(`${API}/conversations/${conversation_id}/updates${q}`, {
    headers: { "X-Conversation-Token": token },
  }).then((r) => r.json());
  // u.status: "bot" | "waiting" | "human" | "closed"
  // u.agent:  { name, avatar_url } | null
  for (const m of u.messages) {        // role: "agent" | "system"
    render(m);                         // m.asks_for_email → show the email field
    after = m.created_at;
  }
  const live = u.status === "waiting" || u.status === "human";
  setTimeout(poll, live ? 3000 : 15000);
}
```

While the status is `waiting` or `human`, visitor messages are delivered to the agent and `POST …/messages` returns `outcome: "human"` with no text. If nobody joins within about 2 minutes, the status goes back to `bot` and a system message with `asks_for_email: true` arrives.

> **Tip** Poll every 3 seconds only while the chat is live and visible, and slow down or stop when the tab is hidden. The poll endpoint allows 60 requests per minute per visitor.

## Full endpoint list

See [Widget (public)](/api-reference/widget) in the API reference.
