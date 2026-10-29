"""LLM client: every model call Ping makes goes through here.

`MODEL_PROVIDER` picks where the calls go. All three speak the OpenAI
`POST /chat/completions` API, so one client serves them:

  vizhi         the VizhiOps gateway (default). A Vizhi *model token* is bound
                to one model, so Ping picks a token per tier (fast / balanced /
                best) and never names the model. Vizhi adds provider fallback,
                per-call logging, cost tracking and budgets.
  nebius        Nebius Token Factory, with NEBIUS_API_KEY and a model per tier.
  build-nvidia  build.nvidia.com, with NVIDIA_API_KEY and a model per tier.
"""

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import LLMEndpoint, get_settings
from app.core.errors import RateLimitedError, ServiceUnavailableError

log = logging.getLogger(__name__)


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str | None = None
    query_id: str | None = None
    latency_ms: int = 0


@dataclass
class StreamMeta:
    """Filled in while a stream is consumed; read it after the iterator ends."""

    model: str | None = None
    query_id: str | None = None
    first_token_ms: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient:
    def __init__(
        self,
        provider: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ):
        self.provider = provider
        self.label = _LABELS.get(provider, provider)
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def _endpoint(self, tier: str) -> LLMEndpoint:
        endpoint = get_settings().llm_endpoint(self.provider, tier)
        if not endpoint.token:
            raise ServiceUnavailableError(f"{self.label} is not configured: set {endpoint.token_env}")
        if self.provider != "vizhi" and not endpoint.model:
            raise ServiceUnavailableError(f"{self.label} is not configured: set LLM_MODEL_BALANCED")
        return endpoint

    def _request(self, endpoint: LLMEndpoint, payload: dict) -> tuple[str, dict, dict]:
        """(url, headers, body) for one chat-completions call."""
        body = dict(payload)
        if self.provider != "vizhi":
            # A Vizhi token already names its model; sending one that differs
            # is a 400. Direct providers need it on every call.
            body["model"] = endpoint.model
            if get_settings().llm_disable_thinking:
                # Nemotron reasons by default and would spend the answer's
                # token budget thinking. Vizhi applies its own policy.
                body["chat_template_kwargs"] = {"enable_thinking": False}
            if body.get("stream"):
                # Direct providers only report usage on a stream when asked.
                body["stream_options"] = {"include_usage": True}
        url = endpoint.base_url.rstrip("/") + endpoint.path
        return url, {"Authorization": f"Bearer {endpoint.token}"}, body

    def chat(
        self,
        messages: list[dict],
        tier: str = "balanced",
        max_tokens: int | None = None,
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> ChatResult:
        started = time.monotonic()
        payload = {"messages": messages, "temperature": temperature, "stream": False}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        url, headers, body = self._request(self._endpoint(tier), payload)
        try:
            response = self._client.post(
                url, json=body, headers=headers,
                **({"timeout": timeout} if timeout else {}),
            )
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"Could not reach {self.label}") from exc
        self._raise_for_status(response)
        data = response.json()
        usage = data.get("usage") or {}
        meta = data.get("vizhi_metadata") or {}
        return ChatResult(
            content=(data["choices"][0]["message"].get("content") or "").strip(),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            model=data.get("model"),
            query_id=meta.get("query_id"),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    def chat_stream(
        self,
        messages: list[dict],
        meta: StreamMeta,
        tier: str = "balanced",
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Yield content deltas as the model writes them (SSE)."""
        started = time.monotonic()
        payload = {"messages": messages, "temperature": temperature, "stream": True}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        url, headers, body = self._request(self._endpoint(tier), payload)
        try:
            with self._client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code >= 400:
                    response.read()
                    self._raise_for_status(response)
                meta.query_id = response.headers.get("X-Vizhi-Query-Id")
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    if "error" in event:
                        error = event["error"]
                        message = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
                        raise ServiceUnavailableError(f"{self.label} stream failed: {message}")
                    meta.model = event.get("model") or meta.model
                    usage = event.get("usage") or {}
                    if usage:
                        meta.prompt_tokens = int(usage.get("prompt_tokens") or 0)
                        meta.completion_tokens = int(usage.get("completion_tokens") or 0)
                    for choice in event.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            if meta.first_token_ms is None:
                                meta.first_token_ms = int((time.monotonic() - started) * 1000)
                            yield delta
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"Lost connection to {self.label}") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = None
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("error")
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("error")
        if response.status_code == 429:
            fallback = (
                "The LLM budget for this bot is exhausted"
                if self.provider == "vizhi"
                else f"{self.label} rate limit reached; try again shortly"
            )
            raise RateLimitedError(str(detail or fallback))
        if response.status_code in (401, 403):
            raise ServiceUnavailableError(f"{self.label} rejected Ping's credentials")
        log.warning("%s error %s: %s", self.provider, response.status_code, detail)
        raise ServiceUnavailableError(str(detail or f"{self.label} could not complete the request"))


_LABELS = {"vizhi": "VizhiOps", "nebius": "Nebius", "build-nvidia": "build.nvidia.com"}

_override: LLMClient | None = None


def use_llm(client: LLMClient | None) -> None:
    """Swap the process-wide client (tests point it at a fake server)."""
    global _override
    _override = client


def get_llm() -> LLMClient:
    return _override or _default_llm()


@lru_cache
def _default_llm() -> LLMClient:
    settings = get_settings()
    return LLMClient(settings.model_provider, settings.llm_timeout_seconds)
