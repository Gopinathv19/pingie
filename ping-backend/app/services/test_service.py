"""Test retrieval: run the real pipeline for one question, store nothing.

The dashboard shows what Memora returned (every chunk, with its score and
whether it cleared the threshold) next to the answer Ping would give.
"""

import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Bot
from app.reasoning.pipeline import Reasoner
from app.services import bot_service, source_service


def run_test(db: Session, bot: Bot, reasoner: Reasoner, query: str, top_k: int, threshold: float | None) -> dict:
    profile = bot_service.profile(bot)
    floor = threshold if threshold is not None else (
        bot.min_similarity if bot.min_similarity is not None else get_settings().reasoning_min_similarity
    )
    if profile.subject_id is None:
        return {
            "query": query, "standalone_query": query, "threshold": floor, "chunks": [],
            "answer": reasoner.fallback_text(profile), "outcome": "fallback", "citations": [],
            "retrieval_ms": 0, "generation_ms": 0, "chunks_in_context": 0,
        }

    started = time.monotonic()
    result = reasoner.memora.retrieve(query, profile.subject_id, top_k)
    retrieval_ms = int((time.monotonic() - started) * 1000)

    names = source_service.names_by_memora_id(db, bot.id, [c.source_id for c in result.chunks])

    # Reuse the retrieval for the answer instead of querying Memora twice.
    prepared = reasoner.prepare(
        profile, [], query, threshold=floor, top_k=top_k, allow_small_talk=False, retrieved=result,
        names=lambda ids: names,
    )
    started = time.monotonic()
    reply = reasoner.generate(profile, prepared)
    generation_ms = int((time.monotonic() - started) * 1000)

    chunks = [
        {
            "rank": i,
            "source": names.get(c.source_id, c.source_filename or "document"),
            "location": c.location,
            "score": round(c.similarity, 4),
            "rerank_score": c.rerank_score,
            "above_threshold": c.similarity >= floor,
            "text": c.content,
        }
        for i, c in enumerate(result.chunks, start=1)
    ]
    citations = [{**c.as_dict(), "source_name": names.get(c.source_id, c.source_name)} for c in reply.citations]
    return {
        "query": query,
        "standalone_query": prepared.standalone or query,
        "threshold": floor,
        "chunks": chunks,
        "answer": reply.text,
        "outcome": reply.outcome,
        "citations": citations,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "chunks_in_context": len(prepared.evidence),
    }
