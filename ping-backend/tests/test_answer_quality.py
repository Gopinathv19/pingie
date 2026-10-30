"""Answer quality: grounded answers, honest citations, unanswerable questions,
strictness, follow-ups, cache keys and team-answer matching.

Pure logic with stub Memora and LLM clients: no database, no network.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.clients.llm import ChatResult
from app.clients.memora import RetrievalResult, RetrievedChunk
from app.db.models import BotAnswer
from app.reasoning import prompts
from app.reasoning.output import AnswerFilter, filter_answer
from app.reasoning.pipeline import BotProfile, Reasoner, Turn, rerank_floor_for, usable_rewrite
from app.services import answer_service, chat_service


# --- stubs -------------------------------------------------------------------------

def chunk(i, content, source="handbook.pdf", sim=0.8, rerank=None, section="Billing"):
    return RetrievedChunk(
        chunk_id=f"c{i}", source_id=f"s{i}", source_filename=source, content=content,
        section_path=[section], page_start=i, page_end=i, similarity=sim, rerank_score=rerank,
    )


PRICING = chunk(1, "The Pro plan costs $29 per month and includes 10 seats and priority support.", "pricing.pdf")
EXPORT = chunk(2, "To export invoices open Settings, then Billing, then Invoices and click Export.", "billing.pdf")


class Memora:
    """Returns the same passages for every query, or per query when given a dict."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def retrieve(self, query, subject_id, top_k):
        self.queries.append(query)
        chunks = self.chunks.get(query, []) if isinstance(self.chunks, dict) else self.chunks
        return RetrievalResult(chunks=list(chunks))


class LLM:
    """`answer` for the answering model, `condensed` for the follow-up rewrite."""

    def __init__(self, answer="", condensed=""):
        self.answer = answer
        self.condensed = condensed
        self.calls = []

    def chat(self, messages, tier="balanced", max_tokens=None, temperature=0.2, timeout=None):
        self.calls.append((tier, messages))
        if tier == "fast":
            return ChatResult(content=self.condensed)
        return ChatResult(content=self.answer, prompt_tokens=10, completion_tokens=5)

    def chat_stream(self, messages, meta, tier="balanced", max_tokens=None, temperature=0.2):
        for i in range(0, len(self.answer), 3):
            yield self.answer[i:i + 3]


def bot(**kw):
    return BotProfile(name="Acme", subject_id=uuid.uuid4(), **kw)


def ask(answer, chunks=(PRICING, EXPORT), question="How much is the Pro plan?", **bot_kw):
    r = Reasoner(Memora(list(chunks)), LLM(answer))
    b = bot(**bot_kw)
    return r.generate(b, r.prepare(b, [], question))


def stream(raw, size):
    f = AnswerFilter()
    shown = "".join(f.push(raw[i:i + size]) for i in range(0, len(raw), size))
    return shown, f.finish()


# --- 1. answers and citations -----------------------------------------------------

def test_answer_from_a_document_cites_that_document():
    reply = ask("The Pro plan costs $29 per month [1].")
    assert reply.outcome == "answered"
    assert reply.text == "The Pro plan costs $29 per month."
    assert [c.source_name for c in reply.citations] == ["pricing.pdf"]


def test_explicit_citation_picks_the_cited_passage_not_the_top_one():
    reply = ask("Open Settings, then Billing, then Invoices [2].", question="How do I export invoices?")
    assert [c.source_name for c in reply.citations] == ["billing.pdf"]


def test_uncited_answer_cites_the_passage_it_drew_on():
    # The top passage is pricing; the answer clearly came from the export passage.
    reply = ask("Open Settings, then Billing, then Invoices and click Export.", question="How do I export invoices?")
    assert [c.source_name for c in reply.citations] == ["billing.pdf"]


def test_uncited_answer_with_no_visible_support_gets_no_citation():
    reply = ask("Yes, that works fine for most teams.")
    assert reply.outcome == "answered"
    assert reply.citations == []


def test_out_of_range_citation_never_cites_a_wrong_document():
    reply = ask("Yes, that works fine for most teams [7].")
    assert reply.citations == []
    assert "[7]" not in reply.text


@pytest.mark.parametrize("raw,cited", [
    ("Costs $29 [1, 2].", [1, 2]),
    ("Costs $29 [1,2].", [1, 2]),
    ("Costs $29 [1-3].", [1, 2, 3]),
    ("Costs $29 [1–2].", [1, 2]),
    ("Costs $29 [^1].", [1]),
    ("Costs $29 【2】.", [2]),
])
@pytest.mark.parametrize("size", [1, 2, 5, 1000])
def test_citation_forms_are_parsed_and_never_shown(raw, cited, size):
    shown, result = stream(raw, size)
    assert result.text == "Costs $29."
    assert shown.strip() == "Costs $29."
    assert result.cited == cited


def test_zero_and_ordinary_brackets_are_not_citations():
    result = filter_answer("Use a[0] and see [docs] here [3].")
    assert result.text == "Use a[0] and see [docs] here."
    assert result.cited == [3]


# --- 2. unanswerable questions ------------------------------------------------------

def test_question_with_no_evidence_falls_back_without_calling_the_model():
    llm = LLM("should not be used")
    r = Reasoner(Memora([chunk(1, "unrelated", sim=0.1)]), llm)
    b = bot()
    reply = r.generate(b, r.prepare(b, [], "Do you sell pizza?"))
    assert reply.outcome == "fallback" and reply.citations == []
    assert all(tier == "fast" for tier, _ in llm.calls)  # never asked the answering model


@pytest.mark.parametrize("raw", [
    "NO_ANSWER",
    "Sorry, I couldn't find that. NO_ANSWER",
    "I don't know. NO_ANSWER.",
])
@pytest.mark.parametrize("size", [1, 3, 1000])
def test_refusals_anywhere_become_the_fallback(raw, size):
    shown, result = stream(raw, size)
    assert "NO_ANSWER" not in shown
    assert result.outcome == "fallback"


@pytest.mark.parametrize("size", [1, 2, 4, 1000])
def test_late_no_answer_after_a_real_answer_is_partial_and_hidden(size):
    raw = "The Pro plan costs $29 per month and includes 10 seats [1]. Volume discounts: NO_ANSWER"
    shown, result = stream(raw, size)
    assert "NO_ANSWER" not in shown and "NO_ANS" not in result.text
    assert result.outcome == "partial"
    assert result.text == "The Pro plan costs $29 per month and includes 10 seats. Volume discounts"


def test_model_refusal_uses_the_configured_fallback_message():
    reply = ask("NO_ANSWER", fallback_message="Please email support@acme.com.")
    assert reply.outcome == "fallback"
    assert reply.text == "Please email support@acme.com."
    assert reply.citations == []


@pytest.mark.parametrize("collect_email,expected", [
    (True, prompts.DEFAULT_FALLBACK),
    (False, "I couldn't find that in our documentation."),
])
def test_default_fallback_and_email_ask_follow_collect_email(collect_email, expected):
    reply = ask("NO_ANSWER", collect_email=collect_email)
    assert reply.text == expected
    assert reply.asks_for_email is collect_email


# --- 3. strict / balanced / helpful ---------------------------------------------------

PARTIAL_ANSWER = "The Pro plan costs $29 per month [1]. I couldn't find volume discounts. [[PARTIAL]]"


def test_strict_turns_a_partial_answer_into_the_fallback():
    reply = ask(PARTIAL_ANSWER, strictness="strict")
    assert reply.outcome == "fallback"
    assert reply.text == prompts.DEFAULT_FALLBACK
    assert reply.trace["route"] == "strict_partial"


@pytest.mark.parametrize("mode", ["balanced", "helpful"])
def test_balanced_and_helpful_keep_partial_answers(mode):
    reply = ask(PARTIAL_ANSWER, strictness=mode)
    assert reply.outcome == "partial"
    assert reply.text.endswith("volume discounts.")
    assert [c.source_name for c in reply.citations] == ["pricing.pdf"]


def test_strictness_moves_the_rerank_floor_and_filters_evidence():
    assert rerank_floor_for("strict") > rerank_floor_for("balanced") > rerank_floor_for("helpful")
    # Reranked between the strict and helpful floors: only helpful keeps it.
    borderline = chunk(1, PRICING.content, "pricing.pdf", rerank=rerank_floor_for("balanced") - 0.5)
    kinds = {}
    for mode in ("strict", "balanced", "helpful"):
        r = Reasoner(Memora([borderline]), LLM("The Pro plan costs $29 [1]."))
        prepared = r.prepare(bot(strictness=mode), [], "How much is Pro?")
        kinds[mode] = prepared.kind
        assert prepared.trace["rerank_floor"] == rerank_floor_for(mode)
    assert kinds == {"strict": "fallback", "balanced": "fallback", "helpful": "generate"}


def test_strict_prompt_overrides_the_partial_rule():
    system = prompts.answer_system_prompt("Acme", "", "friendly", "auto", "strict")
    assert "NO_ANSWER rather than a partial answer" in system and "overrides rule 4" in system
    assert "11." not in prompts.answer_system_prompt("Acme", "", "friendly", "auto", "balanced")


# --- 4. follow-ups ---------------------------------------------------------------------

def test_follow_up_is_condensed_and_both_queries_are_searched():
    memora = Memora({
        "what does the pro plan cost": [PRICING],
        "and how much is it?": [EXPORT],
    })
    r = Reasoner(memora, LLM("The Pro plan costs $29 per month [1].", condensed="what does the pro plan cost"))
    history = [Turn("user", "Tell me about the Pro plan"), Turn("assistant", "Pro has 10 seats.")]
    prepared = r.prepare(bot(), history, "and how much is it?")
    assert set(memora.queries) == {"what does the pro plan cost", "and how much is it?"}
    assert prepared.standalone == "what does the pro plan cost"
    reply = r.generate(bot(), prepared)
    assert [c.source_name for c in reply.citations] == ["pricing.pdf"]


def test_a_zero_rerank_score_is_a_real_score_when_merging():
    good = chunk(1, PRICING.content, "pricing.pdf", rerank=0.0)
    worse = chunk(2, EXPORT.content, "billing.pdf", rerank=-3.0)
    memora = Memora({"what does pro cost": [worse], "and pro?": [good]})
    r = Reasoner(memora, LLM("", condensed="what does pro cost"))
    prepared = r.prepare(bot(), [Turn("user", "plans?"), Turn("assistant", "Free and Pro.")], "and pro?")
    assert [c.chunk_id for c in prepared.evidence][0] == "c1"


@pytest.mark.parametrize("rewrite,ok", [
    ("what does the pro plan cost", True),
    ("NO_ANSWER", False),
    ("The Pro plan costs $29. It has 10 seats. Support is included. Upgrade any time.", False),
    ("", False),
])
def test_condense_output_must_be_a_query(rewrite, ok):
    assert usable_rewrite("and how much is it?", rewrite) is ok


def test_rejected_rewrite_falls_back_to_the_visitors_words():
    memora = Memora([PRICING])
    r = Reasoner(memora, LLM("", condensed="NO_ANSWER"))
    prepared = r.prepare(bot(), [Turn("user", "hi"), Turn("assistant", "Hello!")], "and the pro one?")
    assert prepared.standalone == "and the pro one?"
    assert prepared.trace["condense_rejected"] == "NO_ANSWER"
    assert memora.queries == ["and the pro one?"]


# --- 5. cache keys ----------------------------------------------------------------------

def _orm_bot(**kw):
    base = dict(
        name="Acme", instructions="", tone="friendly", reply_language="auto", model_tier="balanced",
        min_similarity=0.3, fallback_message="", collect_email=True, answer_strictness="balanced",
        topic_guard=False, blocked_topics="", off_topic_message="",
    )
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize("change", [
    {"name": "Acme Support"}, {"collect_email": False}, {"answer_strictness": "strict"},
    {"fallback_message": "Email us."}, {"instructions": "Be brief."},
])
def test_answer_affecting_settings_change_the_cache_key(change):
    assert chat_service.settings_signature(_orm_bot()) != chat_service.settings_signature(_orm_bot(**change))


# --- 6. team-taught answers -----------------------------------------------------------

def taught(question, answer="Taught.", kind="answer"):
    return BotAnswer(id=uuid.uuid4(), question=question, answer=answer, kind=kind)


REFUND = taught("Can I get a refund on the annual policy after 60 days?", "Annual plans can be refunded within 60 days.")
PRICE = taught("What is the price?", "Pro is $29 a month.")
DELETE = taught("How do I delete my account?", "Settings → Account → Delete.")
HOURS = taught("What are your support hours on weekends?", "Weekends 10–4.")
ALL = [REFUND, PRICE, DELETE, HOURS]


@pytest.mark.parametrize("question,expected", [
    ("How do I delete my account?", DELETE),          # exact
    ("how can i delete my account", DELETE),          # same words
    ("pricing?", PRICE),                              # stemming: pricing ~ price
    ("Prices", PRICE),
    ("refund policy?", None),                         # 2 of 5 taught key words: not the same question
    ("my account", None),                             # one shared generic word
    ("Do you sell pizza?", None),
])
def test_taught_answer_matches_only_the_same_question(question, expected):
    assert answer_service.pick_taught([question], ALL) is expected


def test_summary_and_conversation_notes_are_never_sent_word_for_word():
    note = taught("How do I delete my account?", kind="summary")
    assert answer_service.pick_taught(["How do I delete my account?"], [note]) is None


def test_the_answer_sent_must_be_the_one_retrieval_found():
    passage = "## What is the price?\n\nPro is $29 a month."
    assert answer_service.pick_taught(["How do I delete my account?"], ALL, passage) is None
    assert answer_service.pick_taught(["pricing?"], ALL, passage) is PRICE


def test_follow_up_is_matched_on_its_condensed_question(monkeypatch):
    monkeypatch.setattr(answer_service, "list_answers", lambda db, b: ALL)
    team = chunk(1, "## What are your support hours on weekends?\n\nWeekends 10–4.", answer_service.SOURCE_NAME, rerank=2.0)
    prepared = SimpleNamespace(
        kind="generate", evidence=[team], trace={},
        question="and on weekends?", standalone="what are the support hours on weekends",
    )
    reply = chat_service._taught_reply(None, SimpleNamespace(), prepared)
    assert reply is not None and reply.text == "Weekends 10–4."
    assert reply.trace["route"] == "taught_answer"
    # Without the condensed question, "and on weekends?" alone matches nothing.
    prepared.standalone = prepared.question
    assert chat_service._taught_reply(None, SimpleNamespace(), prepared) is None


def test_taught_answer_is_not_used_when_a_document_ranks_first(monkeypatch):
    monkeypatch.setattr(answer_service, "list_answers", lambda db, b: ALL)
    team = chunk(1, "## How do I delete my account?\n\nSettings → Account → Delete.", answer_service.SOURCE_NAME, rerank=0.5)
    doc = chunk(2, "Accounts can be deleted from Settings.", "handbook.pdf", rerank=3.0)
    prepared = SimpleNamespace(kind="generate", evidence=[team, doc], trace={}, question="How do I delete my account?", standalone="")
    assert chat_service._taught_reply(None, SimpleNamespace(), prepared) is None
