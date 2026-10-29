"""Pure reasoning logic: no database, no network."""

import uuid

import pytest

from app.clients.memora import RetrievalResult, RetrievedChunk
from app.reasoning.output import AnswerFilter, filter_answer
from app.reasoning.pipeline import BotProfile, Reasoner, Turn, small_talk


def stream(raw: str, size: int):
    f = AnswerFilter()
    shown = "".join(f.push(raw[i:i + size]) for i in range(0, len(raw), size))
    return shown, f.finish()


@pytest.mark.parametrize("size", [1, 2, 3, 7, 1000])
def test_citations_are_stripped_and_recorded_at_any_chunk_size(size):
    shown, result = stream("Go to Settings → Billing [1]. Exports are emailed [2][1].", size)
    assert result.text == "Go to Settings → Billing. Exports are emailed."
    assert shown.strip() == result.text
    assert result.cited == [1, 2]
    assert result.outcome == "answered"


@pytest.mark.parametrize("raw", ["NO_ANSWER", "  NO_ANSWER", "NO_ANSWER.", ""])
def test_no_answer_becomes_fallback_and_shows_nothing(raw):
    for size in (1, 4, 100):
        shown, result = stream(raw, size)
        assert shown == ""
        assert result.outcome == "fallback"


def test_partial_marker_sets_outcome_and_is_hidden():
    shown, result = stream("Pro has 10 seats [1]. I couldn't find volume discounts. [[PARTIAL]]", 3)
    assert "PARTIAL" not in shown
    assert result.outcome == "partial"
    assert result.text.endswith("volume discounts.")


def test_ordinary_brackets_survive():
    assert filter_answer("Use a[0] and see [docs] here [3].").text == "Use a[0] and see [docs] here."
    assert filter_answer("Nothing about [[x]] here").text == "Nothing about [[x]] here"


def test_a_reply_that_merely_starts_like_no_answer_is_kept():
    assert filter_answer("No, refunds are not offered [1].").text == "No, refunds are not offered."


@pytest.mark.parametrize("message,kind", [
    ("hi", "greeting"), ("Hello!", "greeting"), ("thanks", "thanks"), ("Perfect, thanks!", "thanks"),
    ("bye", "bye"), ("hi, how do I export invoices?", None), ("How do I reset my password?", None), ("ok", None),
])
def test_small_talk(message, kind):
    reply = small_talk(message)
    assert (reply is None) == (kind is None)


def _chunk(i, sim, source="handbook.pdf"):
    return RetrievedChunk(
        chunk_id=f"c{i}", source_id=f"s{i}", source_filename=source, content=f"passage {i}",
        section_path=["Billing"], page_start=4, page_end=4, similarity=sim, rerank_score=None,
    )


class _Memora:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def retrieve(self, query, subject_id, top_k):
        self.queries.append(query)
        return RetrievalResult(chunks=self.chunks)


class _Vizhi:
    def __init__(self, condensed="what does the pro plan cost"):
        self.condensed = condensed
        self.calls = []

    def chat(self, messages, tier="balanced", max_tokens=None, temperature=0.2):
        from app.clients.llm import ChatResult

        self.calls.append((tier, messages))
        if tier == "fast":
            return ChatResult(content=self.condensed)
        return ChatResult(content="It costs $29 [2].", prompt_tokens=10, completion_tokens=5)


def _bot(**kw):
    return BotProfile(name="Acme", subject_id=uuid.uuid4(), **kw)


def test_low_similarity_chunks_are_not_evidence():
    r = Reasoner(_Memora([_chunk(1, 0.1), _chunk(2, 0.2)]), _Vizhi())
    prepared = r.prepare(_bot(min_similarity=0.5), [], "What is the refund policy?")
    assert prepared.kind == "fallback"
    reply = r.finish(_bot(), prepared, None)
    assert reply.outcome == "fallback" and reply.asks_for_email


def test_follow_up_is_condensed_before_retrieval_and_citation_maps_to_chunk():
    memora, vizhi = _Memora([_chunk(1, 0.8), _chunk(2, 0.7, "pricing.pdf")]), _Vizhi()
    r = Reasoner(memora, vizhi)
    history = [Turn("user", "Tell me about the Pro plan"), Turn("assistant", "Pro has 10 seats.")]
    prepared = r.prepare(_bot(), history, "and how much is it?")
    assert memora.queries == ["what does the pro plan cost"]
    reply = r.generate(_bot(), prepared)
    assert reply.text == "It costs $29."
    assert [c.source_name for c in reply.citations] == ["pricing.pdf"]
    assert reply.outcome == "answered"


def test_first_turn_skips_condensing():
    memora, vizhi = _Memora([_chunk(1, 0.8)]), _Vizhi()
    Reasoner(memora, vizhi).prepare(_bot(), [], "How do I export invoices?")
    assert all(tier != "fast" for tier, _ in vizhi.calls)
    assert memora.queries == ["How do I export invoices?"]


def test_bot_instructions_tone_and_language_reach_the_prompt():
    vizhi = _Vizhi()
    r = Reasoner(_Memora([_chunk(1, 0.9)]), vizhi)
    prepared = r.prepare(_bot(instructions="You are Acme's billing helper.", tone="concise", language="ta"), [], "price?")
    system = prepared.messages[0]["content"]
    assert system.startswith("You are Acme's billing helper.")
    assert "As short as possible" in system and "Tamil" in system
