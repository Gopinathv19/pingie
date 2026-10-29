---
title: Knowledge sources
description: Give a bot something to answer from (files, pages and sitemaps), keep it fresh, and check what it retrieves.
---

A bot answers **only** from its sources. Anything that isn't in them, it won't make up. It falls back instead.

## Add sources

Open **Knowledge → Sources**.

### Upload files

Drag files onto the drop zone or click to choose. Supported types are **PDF, DOCX, TXT, MD and CSV**, up to **25 MB** each. Files go straight to the retrieval engine, which extracts the text, chunks it and embeds it.

### Add a URL

Choose **URL**, paste a page address, and Pingie fetches that one page, converts it to clean text, and indexes it.

### Crawl a sitemap

Choose **Sitemap** and paste a `sitemap.xml` address (sitemap index files work too). Pingie:

- fetches up to **200 pages**, four at a time, with a 15-second timeout and a 5 MB limit per page,
- follows `robots.txt` and identifies itself as `PingieBot/1.0`,
- refuses private and loopback addresses to prevent server-side request forgery,
- adds each page as a child of the sitemap source, so you can track progress per page.

> **Note** Each top-level source (a file, a URL or a sitemap) counts against your plan's **sources per bot** limit. Pages inside a sitemap don't count separately.

## Source status

| Status | Meaning |
| --- | --- |
| `queued` | Waiting to be fetched (URLs and sitemaps). |
| `indexing` | Being extracted, chunked and embedded. The page refreshes progress on its own. |
| `ready` | Searchable. The table shows the chunk count. |
| `failed` | Something went wrong; the error is shown on the row. Fix it and choose **Re-sync**. |

## Keep sources fresh

- **Re-sync** fetches a URL or sitemap again (or re-extracts a file) and replaces the indexed version. Do this after you change a page.
- **Delete** removes the source and its chunks from retrieval straight away.

## Test retrieval

**Knowledge → Test retrieval** runs the same search the bot runs, without saving anything:

1. Enter a question, and optionally change **Top K** (how many chunks to fetch) and the **threshold**.
2. See the rewritten **standalone query**, the ranked **chunks** with similarity and rerank scores, the **answer** that would be sent, and the **timings** for each stage.

If the right passage isn't in the results, the bot can't use it. Add a source that states it plainly. If the right passage is there but below the threshold, consider lowering the bot's **similarity threshold** (Bot settings, default 0.30).

## Team answers

Answers your team writes with **Teach the bot** (from an unanswered chat) or **Add answer** (on the Sources page) are stored together in one text source called **Team answers**. Every change rebuilds and re-indexes it, and it counts as a single source for your plan. See [Teach the bot](/guides/live-chat#teach-the-bot).

## Writing sources that answer well

- One topic per page or section, with a clear heading. The heading is often what gets matched.
- State facts plainly: "Refunds are available within 30 days of purchase", not "We're flexible on refunds!".
- Keep prices, limits and policies in text, not only in images.
- Remove outdated pages. Pingie can't tell which of two contradicting pages is current.
