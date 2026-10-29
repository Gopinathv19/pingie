---
title: Answer pipeline
description: What happens between a visitor's question and the bot's answer, and the settings that change it.
---

Pingie separates **finding** passages from **deciding** what to say. Memora finds candidate passages; Pingie's reasoning layer decides whether they are good enough, writes the answer with the LLM, and checks the result.

```text
 visitor message
      │
      ▼
 small talk? ──yes──▶ canned reply (no search, no LLM)
      │ no
      ▼
 condense ─── follow-ups become a standalone query (fast tier, skipped on turn one)
      │
      ▼
 retrieve ─── Memora: vector search → MMR → rerank, top 5
      │
      ▼
 ground  ──── drop passages below the similarity floor ── none left? ──▶ fallback
      │
      ▼
 generate ─── LLM on the bot's tier, with its instructions, tone and language
      │
      ▼
 verify  ──── [n] citations, NO_ANSWER and [[PARTIAL]] markers → outcome
```

## 1. Small talk

Greetings ("hi", "good morning", "vanakkam") and thanks ("thanks!", "perfect, thanks") get a short canned reply. This saves a search and an LLM call, and keeps them from being logged as unanswered.

## 2. Condense follow-ups

"What about the Pro one?" means nothing on its own. From the second message on, Pingie rewrites the latest message into a **standalone query** using the recent conversation (the last 6 turns), with the fast model tier. You can see this query in **Test retrieval**.

## 3. Retrieve

The standalone query goes to Memora, which searches only this bot's sources and returns the top **5** passages after diversity (MMR) and reranking. Pingie asks Memora for passages only; it never lets Memora write the answer.

## 4. Ground: the similarity floor

Each passage has a similarity score. Passages below the bot's **similarity threshold** (default **0.30**, set in Bot settings) are dropped. If nothing is left, the bot doesn't call the LLM at all. It replies with its **fallback message** and, if *collect email* is on, asks for the visitor's email, or offers [a person](/guides/live-chat) when an agent is available.

> **Tip** Raise the threshold if the bot answers from loosely related pages. Lower it if good passages are being thrown away (check the scores in Test retrieval).

## 5. Generate

The remaining passages, the conversation history and the question go to the LLM through VizhiOps, on the bot's **model tier**. The system prompt includes:

- the bot's **instructions**. The default is to answer only from the sources, keep answers under 120 words, and use numbered steps for procedures,
- its **tone**: friendly, professional or concise,
- its **reply language**: `auto` (match the visitor), English, Hindi or Tamil,
- the rule to cite passages as `[1]`, `[2]`… and to reply `NO_ANSWER` when the passages don't contain the answer.

The answer streams back token by token. Answers are capped at 700 tokens, with a low temperature (0.2) for consistency.

## 6. Verify

Before anything reaches the visitor, the output is filtered as it streams:

| Model output | Result |
| --- | --- |
| Cites passages with `[n]` | `answered`. Only the passages actually cited become source chips. |
| Contains `[[PARTIAL]]` | `partial`. Some of the question wasn't covered. |
| Says `NO_ANSWER` | `fallback`. The fallback message is shown instead. |

Markers are never shown to visitors. If the model declines after its first words were held back, the visitor only sees the fallback.

## What's recorded

Every bot reply stores its outcome, the cited passages, a **trace** (standalone query, retrieval scores, which passages were kept and timings), latency, time to first token, token counts and the model used. This powers the inbox badges, the analytics on **Overview**, *knowledge gaps* (questions that keep falling back) and *top questions*.

## Settings that affect answers

| Setting | Where | Effect |
| --- | --- | --- |
| Sources | Knowledge | What can be found at all. |
| Similarity threshold | Bot settings | How relevant a passage must be to count. |
| Instructions | Bot settings | Style, scope, length and persona. |
| Tone / reply language | Bot settings | Voice and language of answers. |
| Model tier | Bot settings | Speed and quality of the writing model (plan dependent). |
| Fallback message / collect email | Bot settings | What happens when nothing is found. |
| Team answers | Inbox / Sources | Exact answers for questions your docs don't cover. |
