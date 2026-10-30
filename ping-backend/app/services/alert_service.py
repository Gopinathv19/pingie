"""Alerts to Slack or any webhook: someone wants a person, a lead was
captured, an answer was disliked. Per bot (`alert_slack_url`,
`alert_webhook_url`, `alert_events`).

Posting runs on a daemon thread with a short timeout, so a slow or broken
endpoint never delays a visitor's reply. Failures are logged, not retried.
"""

import logging
import threading
from datetime import UTC, datetime

import httpx

from app.core import netguard
from app.core.config import get_settings
from app.db.models import Bot

log = logging.getLogger(__name__)

_TIMEOUT = 5.0
EVENTS = ("wants_person", "lead", "disliked")
_HEADLINE = {
    "wants_person": "{visitor} wants to talk to a person",
    "lead": "New lead: {visitor} left their email",
    "disliked": "{visitor} disliked an answer",
    "test": "Test alert from Pingie: alerts for this bot are working",
}


def visitor_label(visitor) -> str:
    if visitor is None:
        return "A visitor"
    return visitor.name or visitor.email or f"Visitor #{visitor.number}"


def _conversation_url(bot: Bot, conversation_id) -> str:
    base = get_settings().app_url.rstrip("/")
    return f"{base}/bots/{bot.public_id}/conversations" + (f"?c={conversation_id}" if conversation_id else "")


def _payloads(
    bot: Bot, event: str, visitor: str, conversation_id, email: str | None, text: str, headline: str | None = None,
) -> tuple[dict, dict]:
    url = _conversation_url(bot, conversation_id)
    headline = headline or _HEADLINE[event].format(visitor=visitor or "A visitor")
    detail = f"\n> {text[:300]}" if text else ""
    slack = {"text": f"*{bot.name}*: {headline}{detail}\n<{url}|Open in Pingie>"}
    webhook = {
        "event": event,
        "headline": headline,
        "bot_id": bot.public_id,
        "bot_name": bot.name,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "visitor": visitor,
        "email": email,
        "text": text,
        "url": url,
        "at": datetime.now(UTC).isoformat(),
    }
    return slack, webhook


def _post(url: str, body: dict) -> int | str:
    # The URL is the bot owner's; it must not reach Pingie's own network (and
    # the test alert's status code must not become a port scanner).
    if netguard.private_host_reason(url):
        return "blocked"
    try:
        return httpx.post(url, json=body, timeout=_TIMEOUT, follow_redirects=False).status_code
    except httpx.HTTPError as exc:
        return type(exc).__name__


def _targets(bot: Bot, slack: dict, webhook: dict) -> list[tuple[str, str, dict]]:
    out = []
    if bot.alert_slack_url:
        out.append(("slack", bot.alert_slack_url, slack))
    if bot.alert_webhook_url:
        out.append(("webhook", bot.alert_webhook_url, webhook))
    return out


def fire(
    bot: Bot, event: str, *, visitor: str = "", conversation_id=None, email: str | None = None, text: str = "",
    headline: str | None = None,
) -> None:
    """Post `event` to the bot's alert URLs in the background, if it's turned on."""
    if event not in (bot.alert_events or []):
        return
    targets = _targets(bot, *_payloads(bot, event, visitor, conversation_id, email, text, headline))
    if not targets:
        return

    def send() -> None:
        for kind, url, body in targets:
            status = _post(url, body)
            if status not in (200, 201, 202, 204):
                log.warning("alert %s to %s for bot %s failed: %s", event, kind, bot.public_id, status)

    threading.Thread(target=send, name="alert", daemon=True).start()


def test(bot: Bot) -> dict[str, int | str]:
    """Send a test alert now (not in the background) and report each URL's result."""
    targets = _targets(bot, *_payloads(bot, "test", "", None, None, ""))
    return {kind: _post(url, body) for kind, url, body in targets}
