"""Ping's reasoning pipeline. Memora finds the passages; this decides the reply.

For one visitor message:

    small talk?  --yes-->  canned reply, no retrieval, no LLM
        | no
    condense     follow-ups ("what about the Pro one?") become a standalone
        |        query using the conversation (fast tier, skipped on turn one)
    retrieve     Memora /query/stream: hybrid search -> MMR -> rerank; only the evidence is kept
        |
    ground       drop passages under the bot's similarity floor;
        |        nothing left  -->  fallback (+ ask for an email)
    generate     the LLM provider (app/clients/llm.py), with the bot's instructions, tone and language;
        |        the model cites [n] and may answer NO_ANSWER / [[PARTIAL]]
    verify       markers -> outcome (answered | partial | fallback),
                 citations -> only the passages the model actually used

`prepare()` does everything up to generation; `generate()` and `stream()`
finish it, so streaming and non-streaming replies share one code path.
"""

import logging
import re
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from app.clients.memora import MemoraClient, RetrievalResult, RetrievedChunk
from app.clients.llm import LLMClient, StreamMeta
from app.core.cache import TTLCache, normalise
from app.core.config import get_settings
from app.core.errors import PingError
from app.reasoning import prompts
from app.reasoning.output import AnswerFilter, FilteredAnswer

log = logging.getLogger(__name__)


@dataclass
class BotProfile:
    """The slice of a bot the reasoning needs, decoupled from the ORM row."""

    name: str
    subject_id: uuid.UUID | None
    instructions: str = ""
    tone: str = "friendly"
    language: str = "auto"
    tier: str = "balanced"
    min_similarity: float | None = None
    fallback_message: str = ""
    collect_email: bool = True
    # Changes whenever the bot's knowledge changes; keys the caches. Empty = don't cache.
    knowledge_version: str = ""
    strictness: str = "balanced"  # strict | balanced | helpful


@dataclass
class Turn:
    role: str  # user | assistant
    content: str


@dataclass
class Prepared:
    kind: str  # smalltalk | fallback | generate
    question: str
    standalone: str = ""
    evidence: list[RetrievedChunk] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    canned: str = ""
    trace: dict = field(default_factory=dict)
    tier: str = "balanced"
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class Citation:
    source_id: str  # Memora source id; the service maps it to a Ping source
    source_name: str
    location: str
    chunk_id: str
    score: float

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "location": self.location,
            "chunk_id": self.chunk_id,
            "score": round(self.score, 4),
        }


@dataclass
class Reply:
    text: str
    outcome: str  # answered | partial | fallback | smalltalk
    citations: list[Citation] = field(default_factory=list)
    asks_for_email: bool = False
    trace: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str | None = None
    gateway_query_id: str | None = None
    first_token_ms: int | None = None
    offer_human: bool = False  # show "Talk to a person" under this reply


# --- small talk ---------------------------------------------------------------

_GREETING = re.compile(r"^(hi+|hey+|hello+|hiya|yo|good (morning|afternoon|evening)|namaste|vanakkam)\b", re.I)
_THANKS = re.compile(r"^(thanks?|thank you|thx|ty|cheers|great,? thanks?|perfect,? thanks?|awesome|cool|ok(ay)?,? thanks?)\b", re.I)
_BYE = re.compile(r"^(bye|goodbye|see you|that'?s all|no,? that'?s it)\b", re.I)


def small_talk(message: str) -> str | None:
    """A canned reply for greetings and thanks, or None for a real question.

    Saves a retrieval and an LLM call on a large share of widget traffic.
    Only short messages qualify: "hi, how do I export invoices?" is a question.
    """
    text = message.strip().rstrip("!.? ")
    if len(text.split()) > 4 or "?" in message:
        return None
    if _GREETING.match(text):
        return "Hi! What can I help you with today?"
    if _THANKS.match(text):
        return "You're welcome! Is there anything else I can help with?"
    if _BYE.match(text):
        return "Thanks for chatting. Have a great day!"
    return None


_HUMAN_WORD = (
    r"(human|humans|person|people|agent|representative|rep|operator|staff|executive|team member|"
    r"real person|live (agent|chat|person)|customer (care|support|service)|support (team|staff)|someone)"
)
_HUMAN_ASK = re.compile(
    rf"\b((talk|speak|chat|connect|transfer|escalate|put me through)\b.{{0,25}}\b{_HUMAN_WORD}\b"
    # "alot me a human", "arrange a person", "assign an agent": typos included
    rf"|(need|want|get|give|call|contact|allot|alot|allott?ed|allocate|arrange|assign|book|send|bring|provide)\b"
    rf".{{0,15}}\b{_HUMAN_WORD}\b"
    rf"|{_HUMAN_WORD}\b.{{0,12}}\b(please|plz|pls|now|needed|required)"
    # the whole message is just "human" / "an agent please"
    rf"|^\s*(an? )?{_HUMAN_WORD}\s*[.!?]*\s*$)",
    re.I,
)


def wants_human(message: str) -> bool:
    """True when a short message asks for a person ("need person", "talk to an agent").

    This is a request for a handover, not a knowledge question, so it never
    goes through retrieval. Long messages are left to the reasoner:
    "how do I talk to a person on the Team plan?" is a question.
    """
    text = message.strip()
    return len(text.split()) <= 10 and bool(_HUMAN_ASK.search(text))


# How far below "balanced" (settings.reasoning_min_rerank) a passage may score
# and still count: strict keeps only clearly relevant ones, helpful a few more.
_STRICTNESS_OFFSET = {"strict": 1.0, "balanced": 0.0, "helpful": -1.0}


def rerank_floor_for(strictness: str) -> float:
    return get_settings().reasoning_min_rerank + _STRICTNESS_OFFSET.get(strictness, 0.0)


def is_evidence(chunk: RetrievedChunk, floor: float, min_rerank: float) -> bool:
    """Evidence if it clears the similarity floor and, when Memora reranked it, the rerank floor."""
    if chunk.similarity < floor:
        return False
    return chunk.rerank_score is None or chunk.rerank_score >= min_rerank


_FOLLOW_UP = re.compile(
    r"\b(it|its|that|this|those|these|they|them|he|she|one|ones|same|also|too|instead|again|more|other|another|previous|above|"
    r"first|second|third|last)\b|^(and|but|so|what about|how about|why|ok|okay|yes|yeah|no)\b",
    re.I,
)


def needs_condense(message: str) -> bool:
    """Only short follow-ups ("and the Pro one?", "yes") need the conversation to
    be searched. A self-contained question is searched as written; rewriting it
    only adds words the visitor never said."""
    text = message.strip()
    return len(text.split()) <= 8 and bool(_FOLLOW_UP.search(text))


_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="retrieve")
_retrieval_cache: TTLCache | None = None


def retrieval_cache() -> TTLCache:
    global _retrieval_cache
    if _retrieval_cache is None:
        s = get_settings()
        _retrieval_cache = TTLCache(s.retrieval_cache_entries, s.retrieval_cache_ttl_seconds)
    return _retrieval_cache


# --- pipeline -----------------------------------------------------------------

class Reasoner:
    def __init__(self, memora: MemoraClient, llm: LLMClient):
        self.memora = memora
        self.llm = llm
        self.settings = get_settings()

    def prepare(
        self,
        bot: BotProfile,
        history: list[Turn],
        question: str,
        *,
        threshold: float | None = None,
        top_k: int | None = None,
        allow_small_talk: bool = True,
        retrieved: RetrievalResult | None = None,
        names: Callable[[list[str]], dict[str, str]] | None = None,
    ) -> Prepared:
        question = question.strip()
        settings = self.settings
        trace: dict = {}

        if allow_small_talk:
            canned = small_talk(question)
            if canned:
                return Prepared(kind="smalltalk", question=question, canned=canned, trace={"route": "smalltalk"})

        prepared = Prepared(kind="generate", question=question, tier=bot.tier)

        # Condense a follow-up into a standalone query. Retrieval sees one
        # query string; "and the Pro one?" retrieves nothing on its own.
        standalone = question
        recent = history[-settings.reasoning_history_turns:]
        k = top_k or settings.reasoning_top_k
        raw_future = None
        if recent and needs_condense(question):
            # Search the visitor's own words while the rewrite runs, instead of after it.
            if retrieved is None and bot.subject_id is not None:
                raw_future = _POOL.submit(self._fetch, question, bot.subject_id, k, bot.knowledge_version)
            started = time.monotonic()
            try:
                result = self.llm.chat(
                    [
                        {"role": "system", "content": prompts.CONDENSE_SYSTEM},
                        {"role": "user", "content": prompts.condense_user_prompt(
                            [{"role": t.role, "content": t.content} for t in recent], question
                        )},
                    ],
                    tier="fast",
                    max_tokens=120,
                    temperature=0.0,
                    timeout=settings.reasoning_condense_timeout_seconds,
                )
                rewrite = (result.content or "").strip().strip('"')
                if usable_rewrite(question, rewrite):
                    standalone = rewrite
                elif rewrite:
                    trace["condense_rejected"] = rewrite[:200]
                prepared.prompt_tokens += result.prompt_tokens
                prepared.completion_tokens += result.completion_tokens
            except PingError as exc:
                # Condensing is an enhancement: retrieve with the raw message.
                log.warning("condense failed, using raw question: %s", exc.message)
            trace["condense_ms"] = int((time.monotonic() - started) * 1000)
        prepared.standalone = standalone
        trace["standalone"] = standalone

        # Retrieve from Memora (no generation there).
        floor = threshold if threshold is not None else (
            bot.min_similarity if bot.min_similarity is not None else settings.reasoning_min_similarity
        )
        trace["threshold"] = floor
        rerank_floor = rerank_floor_for(bot.strictness)
        trace["rerank_floor"] = rerank_floor
        chunks: list[RetrievedChunk] = []
        if retrieved is not None:
            result = retrieved
        elif bot.subject_id is not None:
            started = time.monotonic()
            result = self._retrieve(standalone, question, bot.subject_id, k, bot.knowledge_version, raw_future)
            trace["retrieval_ms"] = int((time.monotonic() - started) * 1000)
        else:
            result = None
        if result is not None:
            trace["memora"] = result.trace
            chunks = _named(result.chunks, names)
        trace["retrieved"] = [
            {
                "source": c.source_filename,
                "location": c.location,
                "similarity": round(c.similarity, 4),
                "rerank": c.rerank_score,
                "kept": is_evidence(c, floor, rerank_floor),
            }
            for c in chunks
        ]

        # Ground: only passages above the floor count as evidence.
        evidence = [c for c in chunks if is_evidence(c, floor, rerank_floor)]
        prepared.evidence = evidence
        prepared.trace = trace
        if not evidence:
            prepared.kind = "fallback"
            trace["route"] = "no_evidence"
            return prepared

        trace["route"] = "generate"
        system = prompts.answer_system_prompt(bot.name, bot.instructions, bot.tone, bot.language, bot.strictness)
        messages = [{"role": "system", "content": system}]
        for turn in recent:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": prompts.answer_user_prompt(question, standalone, evidence)})
        prepared.messages = messages
        return prepared

    def _fetch(self, query: str, subject_id: uuid.UUID, top_k: int, version: str) -> RetrievalResult:
        """One Memora retrieval, served from the cache when the same query was
        asked of the same knowledge recently."""
        key = (subject_id, normalise(query), top_k, version) if version else None
        if key is not None:
            hit = retrieval_cache().get(key)
            if hit is not None:
                return RetrievalResult(chunks=hit.chunks, trace={**hit.trace, "cache": "hit"})
        result = self.memora.retrieve(query, subject_id, top_k)
        if key is not None:
            retrieval_cache().set(key, result)
        return RetrievalResult(chunks=result.chunks, trace={**result.trace, "cache": "miss"})

    def _retrieve(
        self,
        standalone: str,
        raw: str,
        subject_id: uuid.UUID,
        top_k: int,
        version: str = "",
        raw_future: Future | None = None,
    ) -> RetrievalResult:
        """Retrieve for the rewritten query and, when the rewrite changed it, for the
        visitor's own words too, in parallel, keeping each passage's best score.

        The rewrite can drift ("chocolate milk shake plz" became "...recipe") and
        then miss the very note the team wrote for that question. `raw_future`
        is the raw-words search already started while the rewrite ran."""
        same = normalise(standalone) == normalise(raw)
        if same:
            return raw_future.result() if raw_future else self._fetch(raw, subject_id, top_k, version)
        rewritten = _POOL.submit(self._fetch, standalone, subject_id, top_k, version)
        second = raw_future.result() if raw_future else self._fetch(raw, subject_id, top_k, version)
        first = rewritten.result()
        best: dict[str, RetrievedChunk] = {}
        for c in [*first.chunks, *second.chunks]:
            cur = best.get(c.chunk_id)
            if cur is None or _rank(c) > _rank(cur):
                best[c.chunk_id] = c
        merged = sorted(best.values(), key=_rank, reverse=True)
        return RetrievalResult(
            chunks=merged[:top_k],
            trace={**first.trace, "also_raw_query": True, "raw_query_chunks": len(second.chunks)},
        )

    # --- finishing --------------------------------------------------------------

    def generate(self, bot: BotProfile, prepared: Prepared) -> Reply:
        """Non-streaming completion of a prepared answer."""
        if prepared.kind != "generate":
            return self.finish(bot, prepared, None)
        result = self.llm.chat(
            prepared.messages,
            tier=prepared.tier,
            max_tokens=self.settings.reasoning_max_answer_tokens,
            temperature=self.settings.reasoning_temperature,
        )
        f = AnswerFilter()
        f.push(result.content)
        reply = self.finish(bot, prepared, f.finish())
        reply.prompt_tokens += result.prompt_tokens
        reply.completion_tokens += result.completion_tokens
        reply.model = result.model
        reply.gateway_query_id = result.query_id
        reply.first_token_ms = result.latency_ms
        return reply

    def stream(self, bot: BotProfile, prepared: Prepared, meta: StreamMeta, f: AnswerFilter) -> Iterator[str]:
        """Yield visitor-safe text as the model writes it. Afterwards call
        `finish(bot, prepared, f.finish())` and copy usage from `meta`."""
        for delta in self.llm.chat_stream(
            prepared.messages,
            meta,
            tier=prepared.tier,
            max_tokens=self.settings.reasoning_max_answer_tokens,
            temperature=self.settings.reasoning_temperature,
        ):
            safe = f.push(delta)
            if safe:
                yield safe

    def finish(self, bot: BotProfile, prepared: Prepared, filtered: FilteredAnswer | None) -> Reply:
        base = dict(
            trace=prepared.trace,
            prompt_tokens=prepared.prompt_tokens,
            completion_tokens=prepared.completion_tokens,
        )
        if prepared.kind == "smalltalk":
            return Reply(text=prepared.canned, outcome="smalltalk", **base)

        if prepared.kind == "fallback" or filtered is None or filtered.outcome == "fallback":
            if filtered is not None and filtered.outcome == "fallback":
                prepared.trace["route"] = "model_declined"
            return Reply(
                text=self.fallback_text(bot),
                outcome="fallback",
                asks_for_email=bot.collect_email,
                **base,
            )

        if filtered.outcome == "partial" and bot.strictness == "strict":
            # Strict: a half answer is a fallback (prompt rule 11 asks for NO_ANSWER;
            # this holds even when the model answers part anyway).
            prepared.trace["route"] = "strict_partial"
            return Reply(
                text=self.fallback_text(bot),
                outcome="fallback",
                asks_for_email=bot.collect_email,
                **base,
            )

        return Reply(
            text=filtered.text,
            outcome=filtered.outcome,
            citations=_citations(prepared.evidence, filtered.cited, filtered.text),
            **base,
        )

    @staticmethod
    def fallback_text(bot: BotProfile) -> str:
        if bot.fallback_message.strip():
            return bot.fallback_message.strip()
        if bot.collect_email:
            return prompts.DEFAULT_FALLBACK
        return "I couldn't find that in our documentation."


def usable_rewrite(question: str, rewrite: str) -> bool:
    """Whether a condensed follow-up is a search query, not an answer or a
    refusal the fast model wrote instead (then the raw words are searched)."""
    if not rewrite or prompts.NO_ANSWER in rewrite:
        return False
    if len(rewrite) > 3 * len(question) + 150:
        return False
    return len(re.findall(r"[.!?](?:\s|$)", rewrite)) <= 2


def _named(chunks: list[RetrievedChunk], names: Callable[[list[str]], dict[str, str]] | None) -> list[RetrievedChunk]:
    """Memora's chunks carry a source id but no filename; `names` maps ids to
    Ping's source names ("Team answers", "pricing.pdf") for the prompt,
    citations and the taught-answer check. Copies, so cached results stay as Memora sent them.
    Ping's name wins when it has one: Memora's filename for pushed markdown is
    "Team answers.md", which would hide that the passage is a team answer."""
    if not names or not chunks:
        return chunks
    found = names(list({c.source_id for c in chunks}))
    return [replace(c, source_filename=found.get(c.source_id) or c.source_filename) for c in chunks]


def _rank(c: RetrievedChunk) -> float:
    """Rerank score for ordering; a passage without one sorts last (0.0 is a real score)."""
    return c.rerank_score if c.rerank_score is not None else -99.0


_WORD = re.compile(r"[a-z0-9]+")
# Words that say nothing about which passage an answer came from.
_FILLER = set(
    "the and for are was were you your our with this that from have has can will not but all any its into "
    "about there their them they then than when what which where who how also just more some such only "
    "here very each other use used using get go see click".split()
)


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _FILLER}


def _supporting(evidence: list[RetrievedChunk], answer: str) -> list[RetrievedChunk]:
    """For an answer that cited nothing: the passage it visibly drew on, if any.

    Overlap of content words between the answer and each passage. Citing the
    top search result blindly can point at a document the answer didn't use;
    with no clear support, no citation is better than a wrong one."""
    said = _content_words(answer)
    if not said:
        return []
    best, best_shared = None, 0
    for c in evidence:
        shared = len(said & _content_words(c.content))
        if shared > best_shared:
            best, best_shared = c, shared
    if best is None or best_shared < 3 or best_shared < 0.2 * len(said):
        return []
    return [best]


def _citations(evidence: list[RetrievedChunk], cited: list[int], answer: str = "") -> list[Citation]:
    """The passages the model cited, deduplicated by document and location.

    When the model cited nothing usable, the passage the answer visibly drew
    on is cited instead (see `_supporting`), or nothing.
    """
    picked = [evidence[i - 1] for i in cited if 1 <= i <= len(evidence)] or _supporting(evidence, answer)
    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for c in picked:
        key = (c.source_id, c.location)
        if key in seen:
            continue
        seen.add(key)
        out.append(Citation(
            source_id=c.source_id,
            source_name=c.source_filename or "document",
            location=c.location,
            chunk_id=c.chunk_id,
            score=c.similarity,
        ))
    return out
