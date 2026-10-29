# ping-widget

The embeddable Pingie chat widget: one self-contained file, `dist/widget.js`
(~22 kB, ~8 kB gzipped), that customers add to their site with a script tag.
It talks only to the public widget API of [ping-backend](../ping-backend)
(`/api/v1/widget/{bot_id}/*`). Vanilla TypeScript, no runtime dependencies,
bundled by Vite in library mode.

```html
<script src="https://cdn.pingie.app/widget.js" data-bot-id="bot_xxxxxxx" defer></script>
```

| Attribute | Purpose |
| --- | --- |
| `data-bot-id` | Required. The bot's public ID (Install page). |
| `data-api` | Optional. Backend origin; overrides `VITE_API_BASE` baked in at build time. |
| `data-open="true"` | Optional. Open the chat on page load. |

## What it supports

Everything the dashboard configures:

- **Appearance:** title, welcome message, placeholder, accent colour,
  left/right position, launcher icon (chat / spark / help), up to 4
  suggested questions, show sources, "Powered by Pingie" branding, dark/light theme.
- **Bot status:** live, paused (shown as Offline; the backend replies with the
  offline message), draft (works on localhost only).
- **Chat:** streamed answers (SSE), Markdown in replies (escaped first), citations
  as source chips (links for web pages), thumbs up/down, email capture when the
  bot can't answer (the backend saves a lead and sends the handoff email).
- **Persistence:** visitor ID and conversation are kept in localStorage, so the
  chat survives page navigation; an expired conversation is replaced silently.
- **Errors:** wrong domain, unknown bot or unreachable backend means the widget
  stays hidden and logs one console warning. Rate limit and quota errors show a
  short notice in the chat.
- **Isolation:** the UI is in a Shadow DOM, so the host page's CSS can't break
  it. It goes full screen on phones (≤ 480 px) and closes with Esc.

### JavaScript API

```js
Pingie.open();  Pingie.close();  Pingie.toggle();
Pingie.identify({ email: "jane@acme.com", name: "Jane Doe" }); // attribute the chat
Pingie.ask("How do refunds work?");                            // open + send a question
Pingie.reset();                                                // start a new conversation
Pingie.destroy();                                              // remove the widget
```

Calls made before the widget has loaded are queued.


## Develop

```bash
cp .env.example .env     # VITE_API_BASE=http://localhost:8080
npm install
npm run dev              # http://localhost:5173/?bot=bot_xxxxxxx
```

The bot needs **Allow localhost** turned on (Allowed domains page). Add
`&build=1` to test the built `dist/widget.js` instead of the source.

## Serve from ping-backend (current setup on Render)

```bash
npm run build:backend    # builds and copies to ../ping-backend/app/static/widget.js
```

Commit `ping-backend/app/static/widget.js`; the backend serves it at
`GET /widget.js` (5-minute cache). Built this way, the widget calls the origin it
was loaded from, so no API URL is baked in. Set `WIDGET_SCRIPT_URL` on the
backend to `https://<your-service>.onrender.com/widget.js`. Rebuild and commit
whenever the widget changes.

## Build and publish to a CDN (later)

```bash
VITE_API_BASE=https://api.pingie.app npm run build    # -> dist/widget.js

wrangler r2 object put pingie-widget/widget.js \
  --file=dist/widget.js \
  --content-type="application/javascript; charset=utf-8" \
  --cache-control="public, max-age=300" \
  --remote
```

Then set `WIDGET_SCRIPT_URL` in `ping-backend/.env` to the public URL so the
dashboard's Install page shows it.
