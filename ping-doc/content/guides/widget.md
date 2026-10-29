---
title: Install the widget
description: Add the chat to your site with one script tag, control where it may load, and customise how it looks.
---

## The snippet

Copy it from **Widget → Install & embed** and paste it before `</body>`:

```html
<script
  src="https://cdn.pingie.app/widget.js"
  data-bot-id="bot_xxxxxxx"
  defer
></script>
```

| Attribute | Required | Purpose |
| --- | --- | --- |
| `data-bot-id` | Yes | The bot's public ID, shown on the Install page. |
| `data-api` | No | The Pingie API origin. Set it only when self-hosting, e.g. `https://api.example.com`. |
| `data-open="true"` | No | Open the chat as soon as the page loads. |

The script is one file of about 10 kB gzipped with no dependencies. It renders inside a **Shadow DOM**, so your site's CSS can't affect it and its CSS can't leak into your page. If something goes wrong (unknown bot, domain not allowed, API unreachable), it stays hidden and logs one console warning. It never breaks your page.

### Single-page apps

Load the script once in your app shell. The widget survives route changes. To control it from your code, use the [JavaScript API](/guides/javascript-api).

## Allowed domains

The widget only loads on hostnames listed under **Widget → Allowed domains**. The browser's `Origin` header is checked on every request.

| Entry | Matches |
| --- | --- |
| `help.acme.com` | Exactly `help.acme.com`. |
| `*.acme.com` | `acme.com` and every subdomain, such as `www.acme.com` and `docs.acme.com`. |

- Enter hostnames only. A scheme, path or port is stripped if you paste one.
- **Allow localhost** lets the widget run on `localhost` and `127.0.0.1` for testing. Draft bots work only there.
- The list shows when each domain last loaded the widget, so you can see which sites it's actually running on.

> **Warning** If the widget doesn't appear on your live site, check that the bot is **Live**, that the exact hostname (including `www.` if used) is on the list, and look for a `[Pingie]` warning in the browser console.

## Check the install

On **Install & embed**, press **Check again**. Pingie reports the most recent hostname it saw the widget on, and when.

## Appearance

**Widget → Appearance** changes everything visitors see, with a live preview:

| Group | Options |
| --- | --- |
| Content | Header title, welcome message, input placeholder, up to 4 suggested questions (shown as tappable chips until the visitor sends a message). |
| Style | Accent colour (presets or any `#RRGGBB`), dark or light theme, launcher icon (chat, spark or help), bottom-left or bottom-right. |
| Behaviour | Show cited sources under answers; show the "Powered by Pingie" badge. |

The badge can only be turned off on plans that include **remove branding**. On the Free plan it's always shown.

## What visitors get

- **Streamed answers** that appear word by word, with Markdown formatting (escaped for safety).
- **Source chips** under answers; web-page sources link to the page.
- **Thumbs up / down** on every answer. Thumbs-down chats appear under the inbox's *Disliked* filter.
- **Email capture** when the bot can't answer and no agent is available.
- **Talk to a person** when someone on your team is available. See [Live chat](/guides/live-chat).
- **Memory across pages**: the conversation is kept in `localStorage` for 7 days, so it survives navigation.
- **Mobile layout**: full screen on screens 480 px wide or less. Esc closes the chat.
