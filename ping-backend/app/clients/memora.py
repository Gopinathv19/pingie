"""Memora client: Ping's only path to its retrieval engine.

Ping is one Memora *application*, authenticated with a `memora_...` API
credential. The mapping is:

    Ping bot     -> Memora subject  (external_id = bot.public_id)
    Ping source  -> Memora source   (uploaded or pushed as markdown text)

Memora supplies the evidence only; Ping writes every answer itself through
its LLM provider (app/reasoning). Memora's `POST /query` always writes its own answer,
so Ping calls `POST /query/stream`, keeps the `start` event (the ranked chunks,
sent before Memora's LLM runs) and closes the stream. Nothing here reasons.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, PingError, ServiceUnavailableError

log = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_id: str
    source_filename: str | None
    content: str
    section_path: list
    page_start: int | None
    page_end: int | None
    similarity: float
    rerank_score: float | None

    @property
    def location(self) -> str:
        """Human-readable position: "p. 42 · Billing exports"."""
        parts = []
        if self.page_start is not None:
            page = f"p. {self.page_start}"
            if self.page_end and self.page_end != self.page_start:
                page += f"–{self.page_end}"
            parts.append(page)
        if self.section_path:
            parts.append(str(self.section_path[-1]))
        return " · ".join(parts)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    trace: dict = field(default_factory=dict)


@dataclass
class SourceProgress:
    """Memora's view of one source, collapsed into the dashboard's states."""

    status: str  # indexing | ready | failed
    chunk_count: int = 0
    progress: int = 0
    error: str | None = None


class MemoraClient:
    def __init__(self, base_url: str, token: str, timeout: float, transport: httpx.BaseTransport | None = None):
        self._token = token
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/api/v1",
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            transport=transport,
        )
        self._application_id: uuid.UUID | None = None

    # --- plumbing -------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self._token:
            raise ServiceUnavailableError("Memora is not configured: set MEMORA_API_TOKEN")
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("memora %s %s failed: %s", method, path, exc)
            raise ServiceUnavailableError("Could not reach Memora") from exc
        return _check(response)

    @property
    def application_id(self) -> uuid.UUID:
        """The Memora application behind the credential, from /whoami, once."""
        if self._application_id is None:
            data = self._request("GET", "/whoami").json()
            self._application_id = uuid.UUID(data["application_id"])
        return self._application_id

    # --- subjects -------------------------------------------------------------

    def create_subject(self, external_id: str) -> uuid.UUID:
        data = self._request(
            "POST",
            f"/applications/{self.application_id}/subjects",
            json={"external_id": external_id},
        ).json()
        return uuid.UUID(data["id"])

    def find_subject(self, external_id: str) -> uuid.UUID | None:
        """Memora has no lookup by external_id; list the roots and match."""
        rows = self._request(
            "GET", f"/applications/{self.application_id}/subjects", params={"roots_only": "true"}
        ).json()
        for row in rows:
            if row.get("external_id") == external_id:
                return uuid.UUID(row["id"])
        return None

    def delete_subject(self, subject_id: uuid.UUID) -> None:
        try:
            self._request("DELETE", f"/subjects/{subject_id}")
        except NotFoundError:
            pass

    # --- sources --------------------------------------------------------------

    def upload_file(self, subject_id: uuid.UUID, filename: str, content: bytes, mime_type: str) -> uuid.UUID:
        """Store a file and start extraction -> chunking -> embedding."""
        data = self._request(
            "POST",
            f"/subjects/{subject_id}/sources/upload",
            files={"file": (filename, content, mime_type)},
            data={"extract": "true"},
        ).json()
        return uuid.UUID(data["id"])

    def push_text(self, subject_id: uuid.UUID, title: str, text: str) -> uuid.UUID:
        """Index markdown Ping built itself (a crawled page, team answers, a
        past chat). Memora has no text-ingestion route, so it goes up as a
        `.md` file through the same upload as documents."""
        return self.upload_file(subject_id, _md_filename(title), text.encode("utf-8"), "text/markdown")

    def reextract(self, source_id: uuid.UUID) -> None:
        self._request("POST", f"/sources/{source_id}/extractions", json={})

    def delete_source(self, source_id: uuid.UUID) -> None:
        try:
            self._request("DELETE", f"/sources/{source_id}")
        except NotFoundError:
            pass

    def source_progress(self, source_id: uuid.UUID, age_seconds: float) -> SourceProgress:
        """Collapse Memora's extraction + embedding state into one status.

        Memora marks a source `completed` right after extraction, before its
        chunks are embedded, so "ready" means: extracted, chunked, and nothing
        left pending in the embedding queue.
        """
        source = self._request("GET", f"/sources/{source_id}").json()
        status = source.get("status")
        if status == "failed":
            return SourceProgress("failed", error=self._extraction_error(source_id))
        if status in ("pending", "processing"):
            return SourceProgress("indexing", progress=10 if status == "processing" else 2)

        emb = self._request("GET", f"/embedding/sources/{source_id}/status").json()
        total = int(emb.get("total_chunks") or 0)
        embedded = int(emb.get("embedded") or 0)
        in_flight = int(emb.get("pending") or 0) + int(emb.get("processing") or 0)
        failed = int(emb.get("failed") or 0)

        if total == 0:
            # Chunking runs just after extraction completes; give it a moment
            # before calling an empty document a failure.
            if age_seconds > 180:
                return SourceProgress("failed", error="No readable text was found in this source.")
            return SourceProgress("indexing", progress=40)
        if in_flight:
            return SourceProgress("indexing", chunk_count=embedded, progress=40 + int(55 * embedded / total))
        if embedded == 0 and failed:
            return SourceProgress("failed", error="Embedding failed. Try re-syncing the source.")
        return SourceProgress("ready", chunk_count=embedded, progress=100)

    def _extraction_error(self, source_id: uuid.UUID) -> str:
        try:
            latest = self._request("GET", f"/sources/{source_id}/extractions/latest").json()
            return latest.get("error") or "Extraction failed."
        except PingError:
            return "Extraction failed."

    # --- retrieval ------------------------------------------------------------

    def retrieve(self, query: str, subject_id: uuid.UUID, top_k: int) -> RetrievalResult:
        """Ranked chunks for a question (Memora's hybrid search -> MMR ->
        reranker), with no answer generated.

        `/query/stream` sends the evidence as its first event, before its LLM
        starts; leaving the `with` block closes the connection, so Memora's
        answer is abandoned. Memora picks how many chunks to return; Ping keeps
        the best `top_k`."""
        if not self._token:
            raise ServiceUnavailableError("Memora is not configured: set MEMORA_API_TOKEN")
        start = None
        try:
            with self._client.stream(
                "POST", "/query/stream", json={"query": query, "subject_id": str(subject_id)}
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    _check(response)
                event = None
                for line in response.iter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:") and event in ("start", "error"):
                        data = json.loads(line[5:])
                        if event == "error":
                            raise ServiceUnavailableError(data.get("message") or "Memora retrieval failed")
                        start = data
                        break
        except httpx.HTTPError as exc:
            log.warning("memora POST /query/stream failed: %s", exc)
            raise ServiceUnavailableError("Could not reach Memora") from exc
        except ValueError as exc:
            raise ServiceUnavailableError("Memora sent unreadable evidence") from exc
        if start is None:
            raise ServiceUnavailableError("Memora closed the stream before sending evidence")

        chunks = [
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                source_id=c["source_id"],
                source_filename=c.get("source_filename"),
                content=c["content"],
                section_path=c.get("section_path") or [],
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                similarity=float(c.get("similarity") or 0.0),
                rerank_score=c.get("rerank_score"),
            )
            for c in start.get("chunks", [])
        ]
        return RetrievalResult(chunks=chunks[:top_k], trace=start.get("retrieval") or {})


def _md_filename(title: str) -> str:
    """A safe `<title>.md` for Memora's upload (and its source_filename)."""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", title).strip(" .")[:120].strip()
    return f"{name or 'document'}.md"


def _check(response: httpx.Response) -> httpx.Response:
    """Map Memora's error statuses onto Ping's errors."""
    if response.status_code == 404:
        raise NotFoundError(_detail(response, "Not found in Memora"))
    if response.status_code in (401, 403):
        raise ServiceUnavailableError("Memora rejected Ping's credential (MEMORA_API_TOKEN)")
    if response.status_code == 409:
        raise ConflictError(_detail(response, "Already exists in Memora"))
    if response.status_code >= 500:
        raise ServiceUnavailableError(_detail(response, "Memora is unavailable"))
    if response.status_code >= 400:
        raise PingError(_detail(response, "Memora rejected the request"))
    return response


def _detail(response: httpx.Response, default: str) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return detail if isinstance(detail, str) and detail else default


_override: MemoraClient | None = None


def use_memora(client: MemoraClient | None) -> None:
    """Swap the process-wide client (tests point it at a fake server)."""
    global _override
    _override = client


def get_memora() -> MemoraClient:
    return _override or _default_memora()


@lru_cache
def _default_memora() -> MemoraClient:
    settings = get_settings()
    return MemoraClient(settings.memora_base_url, settings.memora_api_token, settings.memora_timeout_seconds)
