---
title: Conversations & leads
description: Review every chat, find what the bot couldn't answer, export transcripts, and follow up on leads.
---

Open a bot and go to **Conversations**. The inbox lists every chat, newest first, 50 at a time, with **Load more** at the bottom.

## Filters

| Filter | Shows |
| --- | --- |
| **All** | Every conversation. |
| **Live** | Chats where a visitor is waiting for a person, or an agent is replying. Waiting chats come first. This filter opens by default when someone is waiting. |
| **Unanswered** | Conversations where at least one answer was a fallback. |
| **Disliked** | Conversations with at least one thumbs-down. |
| **Handoffs** | Conversations where the visitor left an email (a lead). |

The search box matches message text, visitor name and visitor email.

## Reading a transcript

Click a conversation to see:

- the visitor, when it started, how long it lasted, the page it started on and the visitor's location (from your CDN's geo headers when available),
- every message with its time, the bot's **outcome badge** (partial, fallback, lead…), the **sources it cited** and the visitor's **feedback**,
- system notes such as "Zara from the team joined the chat".

Opening a conversation marks it as read; unread chats show a dot in the list. The list refreshes every few seconds.

## Act on unanswered questions

Under each fallback or thumbs-down answer, **Teach the bot the right answer** lets you write the correct answer once. The bot uses it from then on. See [Teach the bot](/guides/live-chat#teach-the-bot).

You can also **Take over** any conversation and reply as a person. See [Live chat](/guides/live-chat).

## Leads

When the bot can't answer and no agent is available, it asks the visitor for their email. The next message is checked for one, and if there is one, Pingie:

1. saves a **lead** with the email and the question that went unanswered,
2. shows the conversation under **Handoffs**, with the email at the top of the transcript,
3. emails the bot's **handoff email** (Bot settings) with the question; the visitor's address is set as Reply-To, so you can answer by replying.

> **Note** Emails are sent only when SMTP is configured on the server. Otherwise the lead is still saved and visible in the inbox.

## Export

**Export CSV** downloads every message of every conversation for the bot, one row per message, with these columns: `conversation_id`, `started_at`, `visitor`, `page`, `role`, `message`, `outcome`, `feedback`, `sources` and `sent_at`.

## Clear history

Owners can delete all conversations, visitors and leads for a bot from **Bot settings → Danger zone → Clear history**. This can't be undone.
