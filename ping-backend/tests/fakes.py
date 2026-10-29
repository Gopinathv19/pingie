"""In-memory stand-ins for Memora and VizhiOps (the default LLM provider), speaking their real HTTP
contracts through httpx.MockTransport, so the actual clients are exercised."""

import json
import re
import uuid

import httpx

from app.clients.memora import MemoraClient
from app.clients.llm import LLMClient


class FakeMemora:
    """Subjects, sources and keyword-overlap "retrieval".

    A source becomes fully embedded on the second status check, so tests see
    the indexing -> ready transition.
    """

    def __init__(self) -> None:
        self.application_id = str(uuid.uuid4())
        self.subjects: dict[str, str] = {}      # id -> external_id
        self.sources: dict[str, dict] = {}      # id -> {subject_id, filename, text, checks}
        self.queries: list[dict] = []
        self.fail_queries = False
        self.fail_uploads = False

    def client(self) -> MemoraClient:
        return MemoraClient("http://memora.test", "memora_test", 5, transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1")
        method = request.method

        if path == "/whoami":
            return httpx.Response(200, json={"application_id": self.application_id})

        if m := re.fullmatch(r"/applications/[^/]+/subjects", path):
            if method == "POST":
                ext = json.loads(request.content)["external_id"]
                if ext in self.subjects.values():
                    return httpx.Response(409, json={"detail": "duplicate"})
                sid = str(uuid.uuid4())
                self.subjects[sid] = ext
                return httpx.Response(201, json={"id": sid, "external_id": ext})
            return httpx.Response(200, json=[{"id": k, "external_id": v} for k, v in self.subjects.items()])

        if m := re.fullmatch(r"/subjects/([^/]+)", path):
            self.subjects.pop(m.group(1), None)
            self.sources = {k: v for k, v in self.sources.items() if v["subject_id"] != m.group(1)}
            return httpx.Response(204)

        # Memora has no text-ingestion route; markdown goes up as a file.
        if m := re.fullmatch(r"/subjects/([^/]+)/sources/upload", path):
            if self.fail_uploads:
                return httpx.Response(503, json={"detail": "Memora is down"})
            body = request.content.decode("utf-8", "replace")
            match = re.search(r'filename="([^"]+)"', body)
            filename = match.group(1)
            part = body[match.end():]
            text = part.split("\r\n\r\n", 1)[1].split("\r\n--", 1)[0] if "\r\n\r\n" in part else ""
            return self._new_source(m.group(1), filename, text)

        if m := re.fullmatch(r"/sources/([^/]+)", path):
            src = self.sources.get(m.group(1))
            if method == "DELETE":
                self.sources.pop(m.group(1), None)
                return httpx.Response(204)
            if src is None:
                return httpx.Response(404, json={"detail": "Source not found"})
            return httpx.Response(200, json={"id": m.group(1), "status": "completed", "filename": src["filename"]})

        if m := re.fullmatch(r"/sources/([^/]+)/extractions", path):
            return httpx.Response(202, json={"status": "processing"})

        if m := re.fullmatch(r"/embedding/sources/([^/]+)/status", path):
            src = self.sources[m.group(1)]
            src["checks"] += 1
            done = src["checks"] >= 2
            return httpx.Response(200, json={
                "total_chunks": 3, "embedded": 3 if done else 1,
                "pending": 0 if done else 2, "processing": 0, "failed": 0,
            })

        if path == "/query":
            raise AssertionError("Ping must never call /query: it always generates an answer")

        if path == "/query/stream":
            data = json.loads(request.content)
            self.queries.append(data)
            if self.fail_queries:
                return httpx.Response(503, json={"detail": "Query embedding failed"})
            start = {
                "query": data["query"], "strategy_id": "s", "strategy_name": "default",
                "chunks": self._search(data["query"], data["subject_id"], 6),
                "retrieval": {"hnsw_candidates": 3, "mmr_candidates": 3, "final_chunks": 3, "reranker_used": True},
            }
            body = (
                f"event: start\ndata: {json.dumps(start)}\n\n"
                f"event: delta\ndata: {json.dumps({'text': 'Memora answer Ping must not use'})}\n\n"
                "event: done\ndata: {}\n\n"
            )
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

        return httpx.Response(404, json={"detail": f"fake memora: no route {method} {path}"})

    def _new_source(self, subject_id: str, filename: str, text: str) -> httpx.Response:
        sid = str(uuid.uuid4())
        self.sources[sid] = {"subject_id": subject_id, "filename": filename, "text": text, "checks": 0}
        return httpx.Response(201, json={"id": sid, "status": "pending", "filename": filename})

    def _search(self, query: str, subject_id: str, top_k: int) -> list[dict]:
        words = {w for w in re.findall(r"[a-z]{3,}", query.lower())}
        hits = []
        for sid, src in self.sources.items():
            if src["subject_id"] != subject_id:
                continue
            for i, para in enumerate(p for p in src["text"].split("\n\n") if p.strip()):
                overlap = words & set(re.findall(r"[a-z]{3,}", para.lower()))
                if overlap:
                    hits.append({
                        # Like Memora main: a source id, no filename (Ping names sources itself).
                        "chunk_id": f"{sid}:{i}", "source_id": sid,
                        "subject_id": subject_id, "content": para.strip(), "content_type": "text",
                        "section_path": ["Billing"], "page_start": 4, "page_end": 4, "token_count": 40,
                        "similarity": min(0.95, 0.4 + 0.15 * len(overlap)), "rerank_score": 1.2,
                    })
        return sorted(hits, key=lambda h: -h["similarity"])[:top_k]


class FakeVizhi:
    """Answers from the context it is given: cites [1] when the first passage
    mentions a word from the question, otherwise declines with NO_ANSWER."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def client(self) -> LLMClient:
        return LLMClient("vizhi", 5, transport=httpx.MockTransport(self.handle))

    def _answer(self, messages: list[dict]) -> str:
        system = messages[0]["content"]
        last = messages[-1]["content"]
        if system.startswith("Rewrite the visitor"):
            return last.rsplit("Latest message:", 1)[1].strip()
        context = last.split("Visitor question:")[0]
        question = last.split("Visitor question:")[1]
        words = set(re.findall(r"[a-z]{4,}", question.lower()))
        first = context.split("\n\n[2]")[0].lower()
        if words & set(re.findall(r"[a-z]{4,}", first)):
            return "Yes. Go to Settings → Billing → Invoices and click Export [1]."
        return "NO_ANSWER"

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Bearer vz_live_")
        body = json.loads(request.content)
        self.calls.append(body)
        text = self._answer(body["messages"])
        if body.get("stream"):
            chunks = [text[i:i + 5] for i in range(0, len(text), 5)]
            lines = "".join(
                f"data: {json.dumps({'model': 'fake-model', 'choices': [{'delta': {'content': c}}]})}\n\n" for c in chunks
            )
            return httpx.Response(200, headers={"X-Vizhi-Query-Id": "q_stream"}, content=(lines + "data: [DONE]\n\n").encode())
        return httpx.Response(200, json={
            "id": "vzr_1", "model": "fake-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
            "vizhi_metadata": {"query_id": "q_123", "provider": "fake"},
        })
