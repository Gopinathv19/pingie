---
title: Teams & sharing
description: Invite teammates into a workspace, share a single bot with someone outside it, and control what each person can do.
---

There are two ways to give someone access:

| | Workspace member | Shared bot |
| --- | --- | --- |
| Access to | Every bot in the workspace | One bot |
| Where it shows for them | A workspace in their top-bar switcher | **Shared with me**, below their own bots |
| Counts against | The workspace's **members** limit (seats) | The bot's **people per shared bot** limit |
| Invite from | Top bar → workspace menu → **Members & invites** | Bot → **Manage → Sharing** |

Only the **owner** can invite, change roles and remove people.

## Roles

| Role | Workspace member | Shared bot |
| --- | --- | --- |
| **Editor** | Change any bot's settings, knowledge, appearance and domains; create bots; reply in live chat. | Change this bot's settings, knowledge, appearance and domains; reply in live chat. |
| **Viewer** | Read everything: overview, conversations, sources, test retrieval. | Read this bot. |

Only owners can delete bots, clear conversation history, rename the workspace and manage sharing. Viewers see a *View only* banner, and editing controls are disabled. The API enforces the same rules: a change by a viewer gets `403`, and someone without access gets `404`.

## Invite someone

1. Enter their email and choose **Editor** or **Viewer**.
2. Pingie creates an invitation that's valid for **7 days** and emails it if SMTP is configured.
3. A **Copy** button shows the invite link. Send it yourself if email isn't set up.

The invited person opens the link, signs in with Google **using the invited email**, and chooses **Accept** or **Decline**. Pending invites also appear as a banner on their **Bots** page.

- Inviting an email that already has access, or already has a pending invite, is refused.
- **New link** issues a fresh link and another 7 days; the old link stops working.
- **Revoke** cancels a pending invite.
- Forwarded links don't work for anyone else: the signed-in email must match.

## Manage access

From the same pages, the owner can change a person's role or remove them. Removing takes effect immediately.

People can also remove themselves:

- **Leave workspace** on the Members page,
- **Remove** on a bot card under *Shared with me*.

## Switching workspaces

The workspace menu in the top bar lists every workspace you belong to, with your role in each. Your own workspace is always first and is the default. The dashboard remembers the last one you picked in this browser.

## Limits

| Plan | Workspace members (seats) | People per shared bot |
| --- | --- | --- |
| Free | 1 (just you) | 3 |
| Pro | 5 | Unlimited |
| Enterprise | Unlimited | Unlimited |

Seats count current members plus pending invites, and are checked again when someone accepts. On Free you can still share individual bots. See [Plans & limits](/guides/plans).
