---
title: Quickstart
description: Create a bot, give it knowledge, check its answers, and put it on your website.
---

## 1. Sign in

Open the Pingie dashboard and choose **Continue with Google**. Your first sign-in creates a personal **workspace** on the Free plan. You can create bots right away.

## 2. Create a bot

On **Bots**, click **New bot**. The wizard has three steps:

1. **Basics.** Enter a name (visitors see it in the widget header) and your website, for example `help.acme.com`. The website is added to the bot's allowed domains automatically.
2. **Knowledge.** Choose one:
   - **Crawl a sitemap.** Pingie suggests `https://<your site>/sitemap.xml`.
   - **Upload files.** PDF, DOCX, TXT, MD or CSV.
   - **Add sources later.**
3. **Launch.** Review and create. The bot starts as a **draft**.

## 3. Wait for indexing

Open **Knowledge → Sources**. Each source moves from *queued* to *indexing* to *ready*, and the table shows progress and chunk counts. Sitemap crawls fetch up to 200 pages, four at a time, and respect `robots.txt`.

> **Tip** Answers are only as good as the sources. A focused set of help articles beats an entire marketing site.

## 4. Test before you go live

Open **Knowledge → Test retrieval** and ask a real customer question. You'll see:

- the **standalone query** Pingie searched for,
- the **retrieved chunks** with similarity and rerank scores,
- the **generated answer** with its citations, and timings.

If the right passage isn't retrieved, add or improve a source. If good passages score below the threshold, lower the **similarity threshold** in **Bot settings**. The default is 0.30.

## 5. Make it yours

- **Widget → Appearance.** Title, welcome message, placeholder, up to four suggested questions, accent colour, dark or light theme, launcher icon and position. The preview updates as you type.
- **Manage → Bot settings.** Instructions, tone (friendly, professional or concise), reply language, model tier, fallback message and handoff email.

## 6. Install the widget

Copy the snippet from **Widget → Install & embed** and paste it before `</body>` on every page where you want the chat:

```html
<script
  src="https://cdn.pingie.app/widget.js"
  data-bot-id="bot_xxxxxxx"
  defer
></script>
```

While the bot is a draft, the widget only loads on `localhost`, and only after you turn on **Allow localhost** in **Widget → Allowed domains**. Press **Check again** on the Install page to confirm the widget was seen.

## 7. Go live

In **Bot settings**, change the status to **Live**. The widget now loads on every hostname in **Allowed domains**. Make sure each one is listed: `help.acme.com`, or `*.acme.com` for all subdomains.

## Next steps

- Turn on [live chat](/guides/live-chat) so a person can step in when the bot can't answer.
- Invite teammates in [Teams & sharing](/guides/sharing).
- Check what your plan includes in [Plans & limits](/guides/plans).
