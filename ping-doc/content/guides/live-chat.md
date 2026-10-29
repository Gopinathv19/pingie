---
title: Live chat & handoff
description: Let a person take over when the bot can't answer, get alerted when visitors are waiting, and teach the bot the answer for next time.
---

## How handoff works

```text
 bot ── visitor clicks "Talk to a person" ──▶ waiting ── agent joins ──▶ human
  ▲                                            │                          │
  └──────── nobody joins within 2 minutes ─────┘    hand back / end chat ─┘
```

1. The bot can't answer a question (a **fallback**).
2. If someone on your team is **available**, the widget shows a **Talk to a person** button under the reply. If nobody is, the bot asks for the visitor's email instead (see [Leads](/guides/conversations#leads)).
3. The visitor clicks it. The conversation becomes **waiting**, and the widget says *Connecting you to a person…*.
4. Every available agent is alerted. The first to reply or press **Join chat** takes it, and the conversation becomes **human**.
5. While a person is on the chat, the bot stays quiet. The visitor's messages go only to the agent, and the widget header shows *Zara from the team*.
6. When done, the agent chooses **Hand back to bot** (the bot answers again) or **End chat**. If the visitor writes after the chat ended, the bot picks up as usual.

If nobody joins within **2 minutes**, the widget apologises and asks for the visitor's email. A lead is saved, and the bot's handoff email gets a *Missed live chat* message.

## Be available

In the dashboard top bar, open **Live** and switch on **Available for live chat**.

- Allow notifications when the browser asks, so you hear and see new chats even in another tab.
- Keep a dashboard tab open while you're available. The tab checks in every 30 seconds, and you count as away about a minute after the last check-in.
- Anyone who can edit the bot can take its chats: workspace **owners and editors**, and people the bot is **shared with as editor**. Viewers can read but not reply.

## Alerts

When a visitor starts waiting, every available agent gets:

- a **browser notification** and a short **chime**,
- an amber **Live** button in the top bar with the count. Its menu lists waiting chats and *your chats*,
- **N waiting** on the bot's *Conversations* item in the sidebar,
- the count in the browser tab title, e.g. `(2) Conversations · Pingie`.

Click any of them to open the chat.

## Reply

In **Conversations**, the **Live** filter shows waiting and active chats. Open one and type in the reply box at the bottom: **Enter** sends and **Shift+Enter** adds a new line. Your reply reaches the widget within about three seconds.

You can also **Take over** any conversation, even one the bot is handling well, for example to help a high-value customer. Sending a reply takes over automatically.

| Action | Effect |
| --- | --- |
| **Join chat** / **Take over** | You're assigned; the bot stops answering; the visitor sees "*Your name* from the team joined the chat". |
| **Hand back to bot** | The bot answers again; the visitor sees "You're chatting with the assistant again". |
| **End chat** | The chat closes; the visitor's next message starts with the bot again. |

> **Note** Agent replies don't count against your plan's monthly message limit. Visitor messages do, as usual.

## Teach the bot

Under every fallback or thumbs-down answer in a transcript there's a **Teach the bot the right answer** link:

1. The visitor's question is filled in; adjust it if needed.
2. Write the answer the way you want the bot to say it.
3. Optionally tick **Also send this answer to the visitor now**. It's ticked by default during a live chat.
4. Save.

The answer is added to the bot's **Team answers** source and re-indexed, so the bot uses it within a minute or so. You can review, add and delete team answers on **Knowledge → Sources**. All of them together count as one source on your plan.

## How it works underneath

Both the widget and the dashboard **poll** for updates: every 3 seconds while a person is on the chat and the panel is open, and less often otherwise. Polling pauses while the tab is hidden. There's no websocket server to run, and it works with any number of API processes. For the endpoints involved, see [Build a custom chat UI](/api/custom-widget#live-chat) and the [Conversations API](/api-reference/conversations).
