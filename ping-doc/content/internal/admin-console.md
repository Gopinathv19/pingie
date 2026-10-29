---
title: Admin console
description: ping-admin, the Pingie team's tool for managing workspaces and plans without SQL.
---

> **Note** Internal. Customers never see this app.

## Signing in

ping-admin runs separately (port 3001 locally). Sign-in is **Google, restricted to an allow-list**:

1. Add the team's Google emails to `ADMIN_EMAILS` in `ping-backend/.env` (comma-separated) and restart the backend.
2. Add the admin console's origin to the Google OAuth client's **Authorized JavaScript origins**.
3. Open the console and **Continue with Google**. Allowed accounts get an 8-hour admin session; anyone else sees *"you@example.com is not an admin"*.

The admin token is signed with `ADMIN_JWT_SECRET`, separate from the dashboard's secret.

## Organizations

**Organizations** lists every workspace with its owner, plan, messages used this month and bots, plus a search box (name, slug, owner name or email).

Open one to change its plan:

- **Plan**: any active plan. Saving applies that plan's limits.
- **Use custom limits**: tick it to override messages, bots, sources per bot, members, people per shared bot, and branding for this workspace only (for custom deals).

Changes take effect immediately.

## Plans

**Plans** is the catalogue. Plans live in the database, so changes need no deploy.

| Field | Meaning |
| --- | --- |
| Key | Internal ID stored on workspaces (`free`, `pro`, `startup`…). Can't be changed. |
| Name, description | Shown on the pricing page. |
| Monthly price / price label | e.g. `49` / `$49`; leave the price empty for "Custom". |
| Limits | Messages per month, bots, sources per bot, members, people per shared bot. Use `9999` for unlimited. |
| Model tiers | Which of fast / balanced / best bots on this plan may use. |
| Remove branding | Whether the "Powered by Pingie" badge can be hidden. |
| Feature bullets | One per line; shown on pricing cards. |
| Sort order | Display order, and what counts as an upgrade (higher = bigger plan). |
| Show to customers | Listed on the pricing page and upgrade modal. |
| Popular | Highlights the card. |
| Default for new signups | Exactly one plan; new workspaces start on it. |
| Active | Untick to archive. Archived plans can't be assigned; the default can't be archived. |

When editing a plan that workspaces already use, **Apply the new limits to the N organizations on this plan** pushes the new limits to them. This overwrites their custom limits. Without it, existing workspaces keep their current limits until their plan is changed again.

## Upgrade workflow

There's no self-serve payment yet:

1. A customer clicks **Upgrade** and emails support@pingie.app.
2. Find their workspace under **Organizations** (search by email).
3. Change the plan and save. Their dashboard shows the new limits on the next page load.

## Admin API

The console uses the [Admin API](/api-reference/admin) with `Authorization: Bearer <admin token>`.
