---
title: Plans & limits
description: What each plan includes, what happens at a limit, and how to upgrade.
---

## Plans

| | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Price | $0 | $49 / month | Custom |
| Bots | 3 | 10 | Unlimited |
| Messages / month | 100 | 100,000 | Unlimited (custom) |
| Sources per bot | 5 | 25 | Unlimited |
| Workspace members | 1 | 5 | Unlimited |
| People per shared bot | 3 | Unlimited | Unlimited |
| Model tiers | Fast | Fast, Balanced | Fast, Balanced, Best |
| Remove "Powered by Pingie" | — | ✓ | ✓ |

The current plans and prices are always on the **Pricing** page in the dashboard. Plans are managed by the Pingie team and can change; the dashboard reads them live.

> **Note** Custom deals are possible: a workspace's individual limits can be raised without changing its plan. Contact support.

## What counts

- **Messages**: visitor messages and bot replies in the current calendar month (UTC), across all of a workspace's bots. Agent replies and system notes don't count.
- **Bots**: every bot in the workspace, whatever its status.
- **Sources**: top-level sources per bot. Pages inside a sitemap and individual team answers don't count separately.
- **Members**: current members plus pending workspace invites.

## At a limit

| Limit reached | What happens |
| --- | --- |
| Monthly messages | The widget shows *This assistant isn't available right now*, and the API returns `402 quota_exceeded` until the month resets or you upgrade. |
| Bots | **New bot** becomes **Upgrade to add more**. |
| Sources | Adding a source is refused with an upgrade message. |
| Members / shares | New invites are refused with an upgrade message. |
| Model tier | Tiers outside your plan are disabled in Bot settings; the API returns `402 plan_restriction`. |

Usage is on the **Bots** page (message and bot meters) and on **Plan & billing**.

## Upgrade

Open **Upgrade** in the top bar (or **Plan & billing**) to compare plans, then email **support@pingie.app**. The team moves your workspace to the new plan, usually within 24 hours, and the new limits apply immediately.
