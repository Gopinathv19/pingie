"""Outgoing email: handoffs and invitations. Logged only when SMTP is not configured."""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, reply_to: str | None = None) -> None:
    settings = get_settings()
    if not to:
        return
    if not settings.smtp_host:
        log.info("email to %s: %r (SMTP not configured, not sent)", to, subject)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("could not send email to %s", to)


def send_handoff(to: str, bot_name: str, visitor_email: str, question: str) -> None:
    send_email(
        to,
        f"[{bot_name}] A visitor needs help",
        f"{bot_name} couldn't answer a visitor's question and collected their email.\n\n"
        f"Visitor: {visitor_email}\nQuestion: {question}\n\nReply to this email to answer them.",
        reply_to=visitor_email,
    )


def send_invitation(to: str, inviter: str, target: str, role: str, url: str) -> None:
    send_email(
        to,
        f"{inviter} invited you to {target} on Pingie",
        f"{inviter} invited you to {target} on Pingie as {'an editor' if role == 'editor' else 'a viewer'}.\n\n"
        f"Accept or decline here (the link works for 7 days):\n{url}\n\n"
        f"Sign in with this email address ({to}) to accept.",
    )
