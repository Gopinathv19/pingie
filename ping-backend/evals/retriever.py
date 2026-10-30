"""Knowledge for the evaluation suite, behind the same `retrieve()` the
reasoning pipeline calls on `MemoraClient`.

  LocalKnowledge   the fixture docs in evals/knowledge/, searched in memory.
                   Deterministic and free; a stand-in for Memora like
                   tests/fakes.py, not a second RAG pipeline.
  PinnedKnowledge  exact passages and scores a case asks for ("retrieval" in
                   dataset.json), for cases about Ping's own logic: the
                   strictness floors, the taught-answer gate, merging.
  MemoraKnowledge  the same docs pushed to a throwaway Memora subject, so the
                   real retrieval and reranker are evaluated. Deleted after.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.clients.memora import MemoraClient, RetrievalResult, RetrievedChunk
from app.db.models import BotAnswer
from app.services import answer_service

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
TEAM_ANSWERS = answer_service.SOURCE_NAME


@dataclass
class Section:
    source: str   # "pricing.md", or "Team answers"
    title: str    # the "## " heading
    text: str     # heading + body, as a passage

    @property
    def key(self) -> str:
        return f"{self.source}#{self.title}"


def team_answers() -> list[BotAnswer]:
    """The fixture team answers as unsaved rows, oldest first (as _document orders them)."""
    import json

    rows = json.loads((KNOWLEDGE_DIR / "team_answers.json").read_text())
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        BotAnswer(id=uuid.uuid4(), question=r["question"], answer=r["answer"], kind=r.get("kind", "answer"),
                  created_at=start + timedelta(minutes=i))
        for i, r in enumerate(rows)
    ]


def _split(source: str, markdown: str) -> list[Section]:
    """One passage per "## " section; text before the first one is a title only."""
    sections = []
    for block in markdown.split("\n## ")[1:]:
        title, _, body = block.partition("\n")
        sections.append(Section(source, title.strip(), f"## {title.strip()}\n\n{body.strip()}"))
    return sections


def load_sections(answers: list[BotAnswer]) -> list[Section]:
    """Docs first, then the team answers rendered exactly as Ping pushes them."""
    sections: list[Section] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        sections += _split(path.name, path.read_text())
    sections += _split(TEAM_ANSWERS, answer_service._document(answers))
    return sections


def _chunk(s: Section, similarity: float, rerank: float | None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=s.key, source_id=s.source, source_filename=s.source, content=s.text,
        section_path=[s.title], page_start=None, page_end=None, similarity=similarity, rerank_score=rerank,
    )


class LocalKnowledge:
    """Scores each section by how many of the query's key words it contains
    (the same words the taught-answer matcher uses). Full coverage scores like
    a strong Memora hit (similarity 0.95, rerank +6); one word in five lands
    between the Strict and Balanced floors, so the modes behave differently."""

    name = "local"

    def __init__(self, sections: list[Section]):
        self.sections = sections
        self._words = [answer_service._words(s.text) for s in sections]
        self.queries: list[str] = []

    def retrieve(self, query: str, subject_id, top_k: int) -> RetrievalResult:
        self.queries.append(query)
        asked = answer_service._words(query)
        scored = []
        for i, (s, words) in enumerate(zip(self.sections, self._words)):
            shared = len(asked & words)
            if not asked or not shared:
                continue
            coverage = shared / len(asked)
            scored.append((-coverage, i, _chunk(s, round(0.3 + 0.65 * coverage, 4), round(-8 + 14 * coverage, 3))))
        scored.sort(key=lambda t: (t[0], t[1]))  # best first; docs before team answers on a tie
        return RetrievalResult(chunks=[c for _, _, c in scored[:top_k]], trace={"retriever": "local"})


class PinnedKnowledge:
    """Returns the passages a case pins, with the scores it gives.

    `pins` is a list (every query gets it) or {query: list} (per query; a
    follow-up searches the rewrite and the visitor's own words)."""

    name = "pinned"

    def __init__(self, sections: list[Section], pins):
        by_key = {s.key: s for s in sections}
        self.queries: list[str] = []

        def build(items):
            out = []
            for p in items:
                key = f"{p['source']}#{p['section']}"
                if key not in by_key:
                    raise KeyError(f"pinned passage {key!r} is not in evals/knowledge")
                out.append(_chunk(by_key[key], p.get("similarity", 0.8), p.get("rerank")))
            return out

        self._by_query = {q: build(items) for q, items in pins.items()} if isinstance(pins, dict) else None
        self._all = build(pins) if isinstance(pins, list) else []

    def retrieve(self, query: str, subject_id, top_k: int) -> RetrievalResult:
        self.queries.append(query)
        chunks = self._by_query.get(query, []) if self._by_query is not None else self._all
        return RetrievalResult(chunks=list(chunks[:top_k]), trace={"retriever": "pinned"})


class MemoraKnowledge:
    """The fixture docs in a throwaway Memora subject. Use as a context manager:
    the subject is deleted on exit."""

    name = "memora"

    def __init__(self, client: MemoraClient, sections: list[Section], timeout: float = 300):
        self.client = client
        self.sections = sections
        self.timeout = timeout
        self.subject_id: uuid.UUID | None = None
        self.names: dict[str, str] = {}  # Memora source id -> fixture source name
        self.queries: list[str] = []

    def __enter__(self) -> "MemoraKnowledge":
        self.subject_id = self.client.create_subject(f"ping-evals-{uuid.uuid4().hex[:8]}")
        docs: dict[str, list[str]] = {}
        for s in self.sections:
            docs.setdefault(s.source, []).append(s.text)
        pushed = []
        for source, parts in docs.items():
            title = source.removesuffix(".md")
            sid = self.client.push_text(self.subject_id, title, f"# {title}\n\n" + "\n\n".join(parts))
            self.names[str(sid)] = source
            pushed.append(sid)
        started = time.time()
        pending = set(pushed)
        while pending and time.time() - started < self.timeout:
            for sid in list(pending):
                status = self.client.source_progress(sid, time.time() - started).status
                if status == "failed":
                    raise RuntimeError(f"Memora failed to index {self.names[str(sid)]}")
                if status == "ready":
                    pending.discard(sid)
            if pending:
                time.sleep(4)
        if pending:
            raise RuntimeError(f"Memora did not finish indexing within {self.timeout:.0f}s")
        return self

    def __exit__(self, *exc) -> None:
        if self.subject_id is not None:
            self.client.delete_subject(self.subject_id)

    def retrieve(self, query: str, subject_id, top_k: int) -> RetrievalResult:
        self.queries.append(query)
        return self.client.retrieve(query, self.subject_id, top_k)

    def source_names(self, ids: list[str]) -> dict[str, str]:
        return {i: self.names[i] for i in ids if i in self.names}
