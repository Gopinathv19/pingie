---
title: Widget JavaScript API
description: Open the chat, ask questions and attribute conversations to signed-in users from your own code.
---

Once the script loads, it exposes `window.Pingie`. Calls made **before** the widget has finished loading are queued and replayed, so you can call them straight away.

```js
Pingie.open();                     // open the chat panel
Pingie.close();                    // close it
Pingie.toggle();                   // open if closed, close if open

Pingie.ask("How do refunds work?"); // open and send this question as the visitor

Pingie.identify({                  // attribute the chat to a known user
  email: "jane@acme.com",
  name: "Jane Doe",
});

Pingie.reset();                    // forget this conversation and start a new one
Pingie.destroy();                  // remove the widget from the page

Pingie.version;                    // e.g. "1.0.0"
```

## `Pingie.identify({ email, name })`

Use this when the visitor is signed in to your product. The conversation then shows their name and email in the inbox instead of "Visitor #N", and the bot won't ask for an email it already has.

- Both fields are optional; an invalid email is ignored with a console warning.
- It's safe to call before the visitor has said anything: it's applied when the conversation starts.

```html
<script>
  // after your app knows who the user is
  Pingie.identify({ email: currentUser.email, name: currentUser.fullName });
</script>
```

## `Pingie.ask(text)`

Opens the chat and sends `text` as the visitor's message. It's handy for "Ask about this" buttons:

```html
<button onclick="Pingie.ask('What does the Pro plan include?')">Ask about Pro</button>
```

## `Pingie.reset()`

Clears the stored conversation and starts fresh. Call it when a user signs out of your product, so the next person on the same browser doesn't see their chat.

## Examples

### Open the chat from your own button

```html
<a href="#" onclick="Pingie.open(); return false;">Chat with support</a>
```

### Open automatically on a help page

```html
<script src="https://cdn.pingie.app/widget.js" data-bot-id="bot_xxxxxxx" data-open="true" defer></script>
```

### React

```tsx
declare global {
  interface Window { Pingie?: { open(): void; ask(t: string): void; identify(i: { email?: string; name?: string }): void } }
}

export function HelpButton() {
  return <button onClick={() => window.Pingie?.ask("I need help with billing")}>Get help</button>;
}
```

> **Note** Building your own chat interface instead of using the widget? See [Build a custom chat UI](/api/custom-widget), which uses the same public widget API.
