"""The Overview page, computed from conversations and messages.

Every number is one grouped query over `messages` / `conversations`, which are
indexed by (bot_id, created_at). Deltas compare the selected range with the
same-length period just before it. Times are bucketed in UTC.
"""

import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import Bot, BotSource, Conversation, Lead, Message
from app.services import help_service

_RANGES = {
    # range: (length, bucket unit, bucket step, label format)
    "24h": (timedelta(hours=24), "hour", timedelta(hours=1), "%H:00"),
    "7d": (timedelta(days=7), "day", timedelta(days=1), "%b %d"),
    "30d": (timedelta(days=30), "day", timedelta(days=1), "%b %d"),
    "90d": (timedelta(days=91), "week", timedelta(weeks=1), "%b %d"),
}
_REASONED = ("answered", "partial", "fallback")
_OUTCOME_LABELS = {
    "answered": "Answered from sources",
    "partial": "Partially answered",
    "fallback": "Fallback / no answer",
}


def _floor(dt: datetime, unit: str) -> datetime:
    dt = dt.replace(minute=0, second=0, microsecond=0)
    if unit == "hour":
        return dt
    dt = dt.replace(hour=0)
    if unit == "week":
        dt -= timedelta(days=dt.weekday())  # date_trunc('week') starts on Monday
    return dt


def _normalize(text: str) -> str:
    return re.sub(r"[\s?!.]+$", "", re.sub(r"\s+", " ", text.strip().lower()))


def _pct_delta(cur: float, prev: float) -> tuple[str, str]:
    if prev == 0:
        return ("—", "flat") if cur == 0 else ("new", "up")
    change = 100 * (cur - prev) / prev
    if abs(change) < 0.05:
        return "—", "flat"
    return f"{'↑' if change > 0 else '↓'} {abs(change):.1f}%", "up" if change > 0 else "down"


def _pts_delta(cur: float, prev: float, higher_is_good: bool = True) -> tuple[str, str]:
    diff = cur - prev
    if abs(diff) < 0.05:
        return "—", "flat"
    good = (diff > 0) == higher_is_good
    return f"{'↑' if diff > 0 else '↓'} {abs(diff):.1f} pts".replace(".0 pts", " pts"), "up" if good else "down"


def overview(db: Session, bot: Bot, range_: str) -> dict:
    length, unit, step, fmt = _RANGES[range_]
    now = datetime.now(UTC)
    start = now - length
    prev_start = start - length

    def period_stats(lo: datetime, hi: datetime) -> dict:
        in_range = and_(Message.bot_id == bot.id, Message.created_at >= lo, Message.created_at < hi)
        msg = db.execute(
            select(
                func.count(Message.id),
                func.sum(case((and_(Message.role == "bot", Message.outcome.in_(_REASONED)), 1), else_=0)),
                func.sum(case((and_(Message.role == "bot", Message.outcome.in_(("answered", "partial"))), 1), else_=0)),
                func.avg(case((Message.outcome.in_(("answered", "partial")), func.coalesce(Message.first_token_ms, Message.latency_ms)))),
                func.sum(case((Message.feedback.is_not(None), 1), else_=0)),
                func.sum(case((Message.feedback == "down", 1), else_=0)),
            ).where(in_range)
        ).one()
        conv = db.execute(
            select(func.count(Conversation.id), func.count(distinct(Conversation.visitor_id))).where(
                Conversation.bot_id == bot.id, Conversation.created_at >= lo, Conversation.created_at < hi
            )
        ).one()
        leads = db.scalar(
            select(func.count(Lead.id)).where(Lead.bot_id == bot.id, Lead.created_at >= lo, Lead.created_at < hi)
        ) or 0
        csat = db.execute(
            select(
                func.count(Conversation.id),
                func.sum(case((Conversation.csat == 3, 1), else_=0)),
                func.sum(case((Conversation.csat == 1, 1), else_=0)),
            ).where(
                Conversation.bot_id == bot.id, Conversation.csat.is_not(None),
                Conversation.csat_at >= lo, Conversation.csat_at < hi,
            )
        ).one()
        reasoned, resolved = int(msg[1] or 0), int(msg[2] or 0)
        rated, down = int(msg[4] or 0), int(msg[5] or 0)
        csat_n, happy, unhappy = (int(x or 0) for x in csat)
        return {
            "csat_n": csat_n,
            "csat": 100 * happy / csat_n if csat_n else 0.0,
            "unhappy": unhappy,
            "messages": int(msg[0] or 0),
            "reasoned": reasoned,
            "resolution": 100 * resolved / reasoned if reasoned else 0.0,
            "first_ms": float(msg[3]) if msg[3] is not None else None,
            "down_pct": 100 * down / rated if rated else 0.0,
            "conversations": int(conv[0] or 0),
            "visitors": int(conv[1] or 0),
            "leads": int(leads),
        }

    cur = period_stats(start, now)
    prev = period_stats(prev_start, start)

    # --- KPIs ---
    kpis = []

    def kpi(key, label, value, delta_tone, sub):
        kpis.append({"key": key, "label": label, "value": value, "delta": delta_tone[0], "tone": delta_tone[1], "sub": sub})

    kpi("conversations", "Conversations", f"{cur['conversations']:,}", _pct_delta(cur["conversations"], prev["conversations"]), "Chats started by visitors")
    # Satisfaction replaced the Messages KPI; message volume is on the Messages chart.
    kpi("satisfaction", "Satisfaction", f"{round(cur['csat'])}%" if cur["csat_n"] else "—",
        _pts_delta(cur["csat"], prev["csat"]) if cur["csat_n"] and prev["csat_n"] else ("—", "flat"),
        f"{cur['csat_n']} rating{'s' if cur['csat_n'] != 1 else ''} · {cur['unhappy']} unhappy" if cur["csat_n"] else "Happy ratings of chats")
    kpi("resolution", "Resolution rate", f"{round(cur['resolution'])}%" if cur["reasoned"] else "—",
        _pts_delta(cur["resolution"], prev["resolution"]) if prev["reasoned"] and cur["reasoned"] else ("—", "flat"),
        "Answered without fallback")
    if cur["first_ms"] is not None:
        first = f"{cur['first_ms'] / 1000:.1f}s"
        if prev["first_ms"] is not None and abs(cur["first_ms"] - prev["first_ms"]) >= 50:
            d = (cur["first_ms"] - prev["first_ms"]) / 1000
            first_delta = (f"{'↑' if d > 0 else '↓'} {abs(d):.1f}s", "down" if d > 0 else "up")
        else:
            first_delta = ("—", "flat")
    else:
        first, first_delta = "—", ("—", "flat")
    kpi("first_response", "Avg. first response", first, first_delta, "Time to first token")

    src = db.execute(
        select(
            func.count(BotSource.id),
            func.sum(case((BotSource.status == "ready", 1), else_=0)),
            func.sum(case((BotSource.status == "failed", 1), else_=0)),
            func.coalesce(func.sum(case((BotSource.status == "ready", BotSource.chunk_count), else_=0)), 0),
        ).where(BotSource.bot_id == bot.id, BotSource.parent_id.is_(None))
    ).one()
    total_src, ready_src, failed_src, chunks = (int(x or 0) for x in src)
    kpi("sources", "Sources ready", f"{ready_src} / {total_src}",
        (f"{failed_src} failed", "down") if failed_src else ("—", "flat"), f"{chunks:,} chunks indexed")
    kpi("visitors", "Unique visitors", f"{cur['visitors']:,}", _pct_delta(cur["visitors"], prev["visitors"]), "On allowed domains")
    kpi("thumbs_down", "Thumbs down", f"{cur['down_pct']:.1f}%",
        _pts_delta(cur["down_pct"], prev["down_pct"], higher_is_good=False), "Of rated answers")
    kpi("handoffs", "Handoffs to email", f"{cur['leads']:,}", _pct_delta(cur["leads"], prev["leads"]), "Leads captured on fallback")

    # --- conversations series, zero-filled ---
    bucket = func.date_trunc(unit, func.timezone("UTC", Conversation.created_at))
    conv_rows = dict(db.execute(
        select(bucket, func.count(Conversation.id))
        .where(Conversation.bot_id == bot.id, Conversation.created_at >= start)
        .group_by(bucket)
    ).all())
    mbucket = func.date_trunc(unit, func.timezone("UTC", Message.created_at))
    unans_rows = dict(db.execute(
        select(mbucket, func.count(Message.id))
        .where(Message.bot_id == bot.id, Message.created_at >= start, Message.outcome == "fallback")
        .group_by(mbucket)
    ).all())
    series = []
    t = _floor(start, unit)
    while t <= now:
        key = t.replace(tzinfo=None)
        series.append({
            "label": t.strftime(fmt),
            "conversations": int(conv_rows.get(key, 0)),
            "unanswered": int(unans_rows.get(key, 0)),
        })
        t += step

    # --- outcomes ---
    outcome_counts = dict(db.execute(
        select(Message.outcome, func.count(Message.id))
        .where(Message.bot_id == bot.id, Message.created_at >= start, Message.outcome.in_(_REASONED))
        .group_by(Message.outcome)
    ).all())
    reasoned_total = sum(outcome_counts.values())
    outcomes = [
        {"key": k, "label": _OUTCOME_LABELS[k], "pct": round(100 * outcome_counts.get(k, 0) / reasoned_total) if reasoned_total else 0}
        for k in _REASONED
    ]

    # --- messages per day, last 14 days ---
    day = func.date_trunc("day", func.timezone("UTC", Message.created_at))
    since14 = _floor(now, "day") - timedelta(days=13)
    per_day = dict(db.execute(
        select(day, func.count(Message.id)).where(Message.bot_id == bot.id, Message.created_at >= since14).group_by(day)
    ).all())
    messages_per_day = [int(per_day.get((since14 + timedelta(days=i)).replace(tzinfo=None), 0)) for i in range(14)]

    # --- top pages ---
    top_pages = [
        {"path": path, "value": int(n)}
        for path, n in db.execute(
            select(Conversation.page_path, func.count(Conversation.id))
            .where(Conversation.bot_id == bot.id, Conversation.created_at >= start)
            .group_by(Conversation.page_path)
            .order_by(func.count(Conversation.id).desc())
            .limit(5)
        ).all()
    ]

    # --- questions: each visitor message paired with the reply to it ---
    reply = aliased(Message)
    pairs = db.execute(
        select(Message.content, reply.outcome, reply.citations)
        .join(reply, reply.reply_to_id == Message.id)
        .where(Message.bot_id == bot.id, Message.role == "visitor", Message.created_at >= start, reply.outcome.in_(_REASONED))
        .limit(20_000)
    ).all()
    groups: dict[str, dict] = {}
    gaps: Counter = Counter()
    gap_text: dict[str, str] = {}
    for content, outcome, citations in pairs:
        key = _normalize(content)
        g = groups.setdefault(key, {"text": content.strip(), "count": 0, "resolved": 0, "sources": Counter()})
        g["count"] += 1
        if outcome != "fallback":
            g["resolved"] += 1
            for cit in citations or []:
                if cit.get("source_name"):
                    g["sources"][cit["source_name"]] += 1
        else:
            gaps[key] += 1
            gap_text.setdefault(key, content.strip())
    top_questions = [
        {
            "text": g["text"],
            "count": g["count"],
            "rate": f"{round(100 * g['resolved'] / g['count'])}%",
            "source": g["sources"].most_common(1)[0][0] if g["sources"] else None,
        }
        for g in sorted(groups.values(), key=lambda g: g["count"], reverse=True)[:5]
    ]

    return {
        "range": range_,
        "kpis": kpis,
        "series_total": cur["conversations"],
        "series": series,
        "outcomes": outcomes,
        "resolved_pct": outcomes[0]["pct"] + outcomes[1]["pct"] if reasoned_total else 0,
        "messages_per_day": messages_per_day,
        "messages_14d": sum(messages_per_day),
        "top_pages": top_pages,
        "knowledge_gaps": [gap_text[k] for k, _ in gaps.most_common(5)],
        "unhelpful_articles": help_service.most_unhelpful(db, bot),
        "unanswered_count": outcome_counts.get("fallback", 0),
        "top_questions": top_questions,
    }
