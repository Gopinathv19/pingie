from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class LLMEndpoint:
    base_url: str
    path: str
    token: str
    # The env var to set when `token` is empty, for the error message.
    token_env: str
    # None for Vizhi: its token is bound to a model.
    model: str | None = None


# Shipped defaults that must never sign real tokens.
_DEFAULT_SECRETS = {"change-me-in-production", "change-me-admin-secret"}
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application configuration, read from the environment / ping-backend/.env."""

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "production"] = "local"

    database_url: str = "postgresql+psycopg://user:password@localhost:5432/ping"
    # Dashboard origins. The widget endpoints answer any origin that is on a
    # bot's allowed-domain list instead (see app/api/widget_cors.py).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Where the embeddable widget script is served from; shown in the install
    # snippet.
    widget_script_url: str = "https://cdn.pingie.app/widget.js"
    # Dashboard base URL, used in invitation links.
    app_url: str = "http://localhost:3000"

    # --- Dashboard session (same scheme as Memora) ----------------------------
    auth_jwt_secret: str = "change-me-in-production"
    auth_jwt_issuer: str = "ping"
    auth_token_ttl_minutes: int = 60 * 24 * 7  # one week
    auth_cookie_name: str = "ping_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    # Google sign-in is the only dashboard login. The backend checks every
    # Google ID token was minted for this client id.
    google_client_id: str = ""

    # --- Memora: the retrieval engine -----------------------------------------
    # Ping is one Memora application. Every bot is a Memora subject, every
    # source a Memora source. The token is a `memora_...` API credential.
    memora_base_url: str = "http://localhost:8000"
    memora_api_token: str = ""
    # Memora is slow to register sources and to answer queries (cold starts,
    # reranking), so allow it well past a typical HTTP timeout.
    memora_timeout_seconds: float = 180.0

    # --- LLM provider ---------------------------------------------------------
    # Where every model call goes (app/clients/llm.py):
    #   vizhi         the VizhiOps gateway, one model token per tier
    #   nebius        Nebius Token Factory, NEBIUS_API_KEY + LLM_MODEL_* below
    #   build-nvidia  build.nvidia.com, NVIDIA_API_KEY + LLM_MODEL_* below
    model_provider: Literal["vizhi", "nebius", "build-nvidia"] = "vizhi"
    # Reasoning through a model is as slow as Memora; give it the same room.
    llm_timeout_seconds: float = Field(
        180.0, validation_alias=AliasChoices("llm_timeout_seconds", "vizhi_timeout_seconds")
    )

    # VizhiOps: a Vizhi model token is bound to one model, so each tier is its
    # own token. Unset tiers fall back to the balanced token.
    vizhi_base_url: str = "http://localhost:8001"
    vizhi_token_fast: str = ""
    vizhi_token_balanced: str = ""
    vizhi_token_best: str = ""

    # Direct providers: one key per provider, one model per tier. Unset tiers
    # fall back to the balanced model.
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    llm_model_fast: str = ""
    llm_model_balanced: str = "nvidia/nemotron-3-super-120b-a12b"
    llm_model_best: str = ""
    # Ask direct providers to skip the model's thinking phase, which would
    # otherwise eat the answer's token budget. Turn off for a model that
    # rejects `chat_template_kwargs`.
    llm_disable_thinking: bool = True

    # --- Reasoning ------------------------------------------------------------
    # Chunks requested from Memora per question, after its reranker.
    reasoning_top_k: int = 5
    # Default similarity floor below which a chunk is not evidence. Each bot
    # can override it (Bot.min_similarity).
    reasoning_min_similarity: float = 0.30
    # Memora's embedding similarity is crowded into ~0.6-0.8 for everything, so
    # the floor above rarely rejects anything. Its reranker separates on-topic
    # (about -2 to -5) from off-topic (-6 and below) far better; passages
    # scoring under this are not evidence. Set very low (-100) to turn it off.
    reasoning_min_rerank: float = -5.5
    # Rewriting a follow-up is an enhancement; past this, search the raw words.
    reasoning_condense_timeout_seconds: float = 3.0
    # In-process caches (per API worker). 0 entries turns one off.
    retrieval_cache_entries: int = 2000
    retrieval_cache_ttl_seconds: float = 600
    answer_cache_entries: int = 1000
    answer_cache_ttl_seconds: float = 1800
    # Prior visitor/bot turns sent with each question.
    reasoning_history_turns: int = 6
    reasoning_max_answer_tokens: int = 700
    reasoning_temperature: float = 0.2

    # --- Knowledge ingestion --------------------------------------------------
    upload_max_bytes: int = 25 * 1024 * 1024
    crawl_max_pages: int = 200
    crawl_concurrency: int = 4
    crawl_timeout_seconds: float = 15.0
    crawl_max_page_bytes: int = 5 * 1024 * 1024
    crawl_user_agent: str = "PingieBot/1.0 (+https://pingie.app/bot)"
    # Fetching user-supplied URLs from the server is an SSRF risk; private and
    # loopback addresses are refused unless this is on (local development).
    crawl_allow_private_hosts: bool = False
    # Background refresh of sources still being indexed by Memora.
    status_sweeper_enabled: bool = True
    status_sweeper_interval_seconds: float = 20.0
    # Chat memory: finished chats a team member answered are pushed to Memora,
    # so the bot can draw on how the team handled similar questions. A chat is
    # finished when closed, or idle this long with nobody live on it.
    chat_memory_enabled: bool = True
    chat_memory_idle_minutes: int = 30

    # --- Widget ---------------------------------------------------------------
    widget_rate_limit_per_minute: int = 20
    widget_conversation_ttl_hours: int = 24 * 30
    widget_poll_rate_limit_per_minute: int = 60
    # How long a visitor waits for a person before the widget asks for an email.
    handoff_wait_seconds: int = 120

    # --- Plans & admin ------------------------------------------------------
    # Plan limits live in the `plans` table, managed from ping-admin.
    support_email: str = "support@pingie.app"
    # Comma-separated Google account emails allowed into ping-admin.
    admin_emails: str = ""
    admin_jwt_secret: str = "change-me-admin-secret"
    admin_token_ttl_minutes: int = 60 * 8

    # --- Handoff email (optional; logged only when SMTP is not configured) ----
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "Pingie <no-reply@pingie.app>"

    # --- Client IP behind a proxy -------------------------------------------------
    # Proxies in front of the API that append to X-Forwarded-For. The client IP
    # (rate limits) is the entry that many hops from the right: the leftmost
    # entries are written by the client and can't be trusted. 0 ignores the
    # header and uses the socket peer.
    trusted_proxy_hops: int = Field(default=1, ge=0, le=5)

    @model_validator(mode="after")
    def _production_secrets(self) -> "Settings":
        """Refuse to run in production with secrets anyone can sign tokens with."""
        if self.environment != "production":
            return self
        problems = []
        for name in ("auth_jwt_secret", "admin_jwt_secret"):
            value = getattr(self, name)
            if value in _DEFAULT_SECRETS or len(value) < _MIN_SECRET_LENGTH:
                problems.append(f"{name.upper()} must be a random value of at least {_MIN_SECRET_LENGTH} characters")
        if not self.auth_cookie_secure:
            problems.append("AUTH_COOKIE_SECURE must be true")
        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self

    @property
    def admin_email_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def vizhi_token_for(self, tier: str) -> str:
        token = {
            "fast": self.vizhi_token_fast,
            "balanced": self.vizhi_token_balanced,
            "best": self.vizhi_token_best,
        }.get(tier, "")
        return token or self.vizhi_token_balanced

    def llm_model_for(self, tier: str) -> str:
        model = {
            "fast": self.llm_model_fast,
            "balanced": self.llm_model_balanced,
            "best": self.llm_model_best,
        }.get(tier, "")
        return model or self.llm_model_balanced

    def llm_endpoint(self, provider: str, tier: str) -> "LLMEndpoint":
        """Where a call for `tier` goes on `provider`, and with which credential."""
        if provider == "vizhi":
            return LLMEndpoint(
                self.vizhi_base_url, "/v1/chat/completions",
                self.vizhi_token_for(tier), "VIZHI_TOKEN_BALANCED",
            )
        if provider == "nebius":
            return LLMEndpoint(
                self.nebius_base_url, "/chat/completions",
                self.nebius_api_key, "NEBIUS_API_KEY", self.llm_model_for(tier),
            )
        return LLMEndpoint(
            self.nvidia_base_url, "/chat/completions",
            self.nvidia_api_key, "NVIDIA_API_KEY", self.llm_model_for(tier),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
