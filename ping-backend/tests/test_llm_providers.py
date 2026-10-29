"""MODEL_PROVIDER routing: each provider gets the URL, credential and body it expects."""

import json

import httpx
import pytest

from app.clients import llm as llm_module
from app.clients.llm import LLMClient, StreamMeta
from app.core.config import Settings
from app.core.errors import RateLimitedError, ServiceUnavailableError


def _settings(**kw) -> Settings:
    base = dict(
        vizhi_base_url="http://vizhi.test",
        vizhi_token_balanced="vz_live_bal",
        vizhi_token_fast="vz_live_fast",
        nvidia_base_url="https://nvidia.test/v1",
        nvidia_api_key="nvapi-test",
        nebius_base_url="https://nebius.test/v1/",
        nebius_api_key="nebius-test",
        llm_model_balanced="nvidia/balanced",
        llm_model_fast="nvidia/fast",
    )
    base.update(kw)
    return Settings(_env_file=None, **base)


class _Recorder:
    def __init__(self, stream: bool = False, status: int = 200):
        self.requests: list[httpx.Request] = []
        self.stream = stream
        self.status = status

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"message": "nope"}})
        if self.stream:
            events = [
                {"model": "m", "choices": [{"delta": {"content": "Hi"}}]},
                {"model": "m", "choices": [{"delta": {"content": " there"}}]},
                {"model": "m", "choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}},
            ]
            body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
            return httpx.Response(200, content=body.encode())
        return httpx.Response(200, json={
            "model": "m",
            "choices": [{"message": {"content": " ok "}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
        })

    @property
    def last_body(self) -> dict:
        return json.loads(self.requests[-1].content)


def _client(monkeypatch, provider: str, recorder: _Recorder, **settings) -> LLMClient:
    s = _settings(**settings)
    monkeypatch.setattr(llm_module, "get_settings", lambda: s)
    return LLMClient(provider, 5, transport=httpx.MockTransport(recorder.handle))


def test_vizhi_uses_tier_token_and_sends_no_model(monkeypatch):
    rec = _Recorder()
    result = _client(monkeypatch, "vizhi", rec).chat([{"role": "user", "content": "q"}], tier="fast")
    req = rec.requests[0]
    assert str(req.url) == "http://vizhi.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer vz_live_fast"
    assert "model" not in rec.last_body
    assert "chat_template_kwargs" not in rec.last_body
    assert result.content == "ok"


@pytest.mark.parametrize(
    ("provider", "url", "key"),
    [
        ("build-nvidia", "https://nvidia.test/v1/chat/completions", "nvapi-test"),
        ("nebius", "https://nebius.test/v1/chat/completions", "nebius-test"),
    ],
)
def test_direct_providers_send_key_and_tier_model(monkeypatch, provider, url, key):
    rec = _Recorder()
    client = _client(monkeypatch, provider, rec)
    client.chat([{"role": "user", "content": "q"}], tier="fast")
    assert str(rec.requests[0].url) == url
    assert rec.requests[0].headers["authorization"] == f"Bearer {key}"
    assert rec.last_body["model"] == "nvidia/fast"
    assert rec.last_body["chat_template_kwargs"] == {"enable_thinking": False}

    # An unset tier falls back to the balanced model.
    client.chat([{"role": "user", "content": "q"}], tier="best")
    assert rec.last_body["model"] == "nvidia/balanced"


def test_disable_thinking_can_be_turned_off(monkeypatch):
    rec = _Recorder()
    _client(monkeypatch, "nebius", rec, llm_disable_thinking=False).chat([{"role": "user", "content": "q"}])
    assert "chat_template_kwargs" not in rec.last_body


def test_direct_stream_asks_for_usage(monkeypatch):
    rec = _Recorder(stream=True)
    meta = StreamMeta()
    text = "".join(_client(monkeypatch, "build-nvidia", rec).chat_stream([{"role": "user", "content": "q"}], meta))
    assert text == "Hi there"
    assert rec.last_body["stream_options"] == {"include_usage": True}
    assert (meta.prompt_tokens, meta.completion_tokens) == (7, 2)
    assert meta.query_id is None


def test_missing_key_names_the_env_var(monkeypatch):
    rec = _Recorder()
    client = _client(monkeypatch, "nebius", rec, nebius_api_key="")
    with pytest.raises(ServiceUnavailableError, match="NEBIUS_API_KEY"):
        client.chat([{"role": "user", "content": "q"}])
    assert rec.requests == []


def test_direct_rate_limit_is_not_called_a_budget(monkeypatch):
    client = _client(monkeypatch, "build-nvidia", _Recorder(status=429))
    with pytest.raises(RateLimitedError, match="nope"):
        client.chat([{"role": "user", "content": "q"}])
