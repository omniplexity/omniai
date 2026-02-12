"""Application settings using Pydantic BaseSettings."""

import os
import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_db_path() -> str:
    """Get absolute path to default SQLite database."""
    # Get the directory containing this settings file (backend/config/)
    config_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to backend/
    backend_dir = os.path.dirname(config_dir)
    # Path to database file
    db_path = os.path.join(backend_dir, "data", "omniai.db")
    # Convert to absolute path with sqlite:/// prefix
    return f"sqlite:///{db_path}"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    # Explicit environment selector. Keep this separate from DEBUG so production
    # checks don't accidentally trigger just because SECRET_KEY looks "strong".
    environment: str = Field(default="development")
    # Bind to 127.0.0.1 by default for security. Use 0.0.0.0 only in containers.
    # On host machines, always prefer localhost binding to prevent LAN exposure.
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # Trusted hosts for Host header validation
    # Required for tunnel deployments (ngrok/cloudflared) which forward original Host
    # Format: comma-separated list of allowed hostnames
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,omniplexity.duckdns.org,rossie-chargeful-plentifully.ngrok-free.dev",
        description="Comma-separated allowed Host headers. Include tunnel domains when using ngrok/cloudflared.",
    )
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default=None)
    public_base_url: str = Field(default="")

    # Security
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    cors_origins: str = Field(default="https://omniplexity.github.io")
    required_frontend_origins: str = Field(
        default="",
        description="Comma-separated frontend origins required for CORS. Overrides default GH Pages origin. Leave empty to use default.",
    )
    rate_limit_rpm: int = Field(default=60)
    rate_limit_user_rpm: int = Field(default=60)
    # Rate limit + concurrency store backend
    # "memory" = in-memory (current, single-worker only)
    # "redis" = distributed (requires redis_url, multi-worker)
    limits_backend: str = Field(default="memory")
    # Redis URL for distributed rate limiting (when limits_backend=redis)
    # Format: redis://localhost:6379/0
    redis_url: str = Field(default="")
    max_request_bytes: int = Field(default=1048576)
    voice_max_request_bytes: int = Field(default=26214400)

    # Authentication
    session_cookie_name: str = Field(default="omni_session")
    session_ttl_seconds: int = Field(default=604800)
    # Local/test-safe defaults. Production must explicitly set secure cross-site values.
    cookie_secure: bool = Field(default=False)
    cookie_samesite: str = Field(default="lax")
    # CHIPS support: when true and cross-site cookie requirements are met,
    # emit Partitioned cookies for third-party contexts (Pages -> API domain).
    cookie_partitioned: bool = Field(default=True)
    cookie_domain: str = Field(default="")
    csrf_header_name: str = Field(default="X-CSRF-Token")
    csrf_cookie_name: str = Field(default="omni_csrf")
    invite_required: bool = Field(default=True)
    diag_token: Optional[str] = Field(default=None)
    # None means "environment-based default":
    # - false in production/staging
    # - true in development/test
    diag_enabled: Optional[bool] = Field(default=None)
    diag_rate_limit_rpm: int = Field(default=10)

    # Bootstrap admin (startup-only, env-driven)
    bootstrap_admin_enabled: bool = Field(default=False)
    bootstrap_admin_username: str = Field(default="")
    bootstrap_admin_email: str = Field(default="")
    bootstrap_admin_password: str = Field(default="")
    # Test-only deterministic E2E seed user (never enabled in production)
    e2e_seed_user: bool = Field(default=False)
    e2e_username: str = Field(default="")
    e2e_password: str = Field(default="")
    # Optional client telemetry ingest (metadata-only)
    client_events_enabled: bool = Field(default=False)
    client_events_max_batch: int = Field(default=50)
    client_events_rpm: int = Field(default=120)
    client_events_max_sample_rate: float = Field(default=0.1)
    client_events_force_sample_rate: float | None = Field(default=None)
    client_events_sampling_mode: str = Field(default="hash")

    # Database
    database_url: str = Field(default_factory=_get_default_db_path)
    database_url_postgres: str = Field(default="")

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL (Postgres takes precedence if set)."""
        return self.database_url_postgres or self.database_url

    # Media storage
    media_storage_path: str = Field(default="./data/uploads")

    # Providers
    provider_default: str = Field(default="lmstudio")
    providers_enabled: str = Field(default="lmstudio")
    provider_timeout_seconds: int = Field(default=30)
    provider_max_retries: int = Field(default=1)
    sse_ping_interval_seconds: int = Field(default=10)
    readiness_check_providers: bool = Field(default=False)

    # Embeddings (semantic search / RAG)
    embeddings_enabled: bool = Field(default=False)
    embeddings_model: str = Field(default="")
    embeddings_provider_preference: str = Field(default="openai_compat,ollama,lmstudio")

    # LM Studio
    lmstudio_base_url: str = Field(default="http://host.docker.internal:1234")

    # Ollama
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")

    # OpenAI-compatible
    openai_compat_base_url: str = Field(default="")
    openai_compat_api_key: str = Field(default="")

    # Voice
    voice_provider_preference: str = Field(default="whisper,openai_compat")
    voice_whisper_model: str = Field(default="base")
    voice_whisper_device: str = Field(default="cpu")
    voice_openai_audio_model: str = Field(default="whisper-1")

    # Tools (server-side policy enforcement)
    # These settings enforce tool usage policy - client hints are NOT trusted
    tools_enabled: str = Field(default="")  # Empty = all disabled, comma-separated list to enable
    feature_workspace: bool = Field(default=True)
    tools_web_browsing_enabled: bool = Field(default=False)
    tools_web_depth_max: int = Field(default=3)
    tools_max_calls_per_request: int = Field(default=10)
    tools_rate_limit_per_minute: int = Field(default=30)

    # SSE streaming abuse controls
    # Limits to prevent resource exhaustion from long-lived connections
    sse_max_concurrent_per_user: int = Field(default=3)
    sse_max_duration_seconds: int = Field(default=1800)  # 30 minutes
    sse_max_tokens_per_stream: int = Field(default=32768)
    sse_idle_timeout_seconds: int = Field(default=60)

    # DuckDNS Ops (admin-only observability + controls)
    duckdns_subdomain: str = Field(default="omniplexity")
    duckdns_token: str = Field(default="")
    duckdns_timeout_seconds: int = Field(default=15)
    duckdns_events_limit: int = Field(default=500)
    ops_scheduler_enabled: bool = Field(default=False)
    ops_scheduler_interval_minutes: int = Field(default=5)

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse allowed hosts from comma-separated string."""
        if not self.allowed_hosts:
            return []
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def providers_enabled_list(self) -> List[str]:
        """Parse enabled providers from comma-separated string."""
        if not self.providers_enabled:
            return []
        return [p.strip() for p in self.providers_enabled.split(",") if p.strip()]

    @property
    def embeddings_provider_preference_list(self) -> List[str]:
        if not self.embeddings_provider_preference:
            return []
        return [
            p.strip()
            for p in self.embeddings_provider_preference.split(",")
            if p.strip()
        ]

    @property
    def tools_enabled_list(self) -> List[str]:
        """Parse enabled tools from comma-separated string."""
        if not self.tools_enabled:
            return []
        return [t.strip() for t in self.tools_enabled.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper

    @field_validator("cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, v: str) -> str:
        """Normalize + validate SameSite cookie attribute."""
        vv = (v or "").strip().lower()
        if vv not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return vv

    @property
    def cookie_samesite_header(self) -> str:
        """Return SameSite value for HTTP header (capitalized for browser compatibility).
        
        Browsers require SameSite=None (capital N) for cross-site cookies.
        """
        if self.cookie_samesite == "none":
            return "None"
        return self.cookie_samesite.capitalize()

    @property
    def cookie_partitioned_enabled(self) -> bool:
        """Return whether Partitioned cookies should be emitted."""
        return bool(self.cookie_partitioned and self.cookie_secure and self.cookie_samesite == "none")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        vv = (v or "").strip().lower()
        if vv not in {"development", "staging", "production", "test"}:
            raise ValueError("ENVIRONMENT must be one of: development, staging, production, test")
        return vv

    @field_validator("client_events_sampling_mode")
    @classmethod
    def validate_client_events_sampling_mode(cls, v: str) -> str:
        vv = (v or "").strip().lower()
        if vv not in {"hash", "random"}:
            raise ValueError("CLIENT_EVENTS_SAMPLING_MODE must be one of: hash, random")
        return vv

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment.lower() == "test"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.environment.lower() == "staging"

    @property
    def is_prod_like(self) -> bool:
        """Check if running in production or staging mode."""
        return self.is_production or self.is_staging

    @property
    def docs_url(self) -> str | None:
        """Return docs URL if not in prod-like environment, else None."""
        return None if self.is_prod_like else "/docs"

    @property
    def redoc_url(self) -> str | None:
        """Return redoc URL if not in prod-like environment, else None."""
        return None if self.is_prod_like else "/redoc"

    @property
    def openapi_url(self) -> str | None:
        """Return openapi URL if not in prod-like environment, else None."""
        return None if self.is_prod_like else "/openapi.json"

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str, info):  # type: ignore[override]
        env = (info.data.get("environment") or "development").strip().lower()
        origins = [o.strip() for o in (v or "").split(",") if o.strip()]
        if env == "production":
            # Fail closed: require https origins only.
            bad = [o for o in origins if o.startswith("http://")]
            if bad:
                raise ValueError(f"In production, CORS_ORIGINS must be https-only; got: {bad}")
        return v

    @model_validator(mode="after")
    def validate_cross_field_constraints(self) -> "Settings":
        # SameSite=None requires Secure=true.
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE=none")

        # Wildcard hosts not allowed in production
        if self.is_production:
            for host in self.allowed_hosts_list:
                if host.startswith("*."):
                    raise ValueError(
                        f"Wildcard hosts (*.{host[2:]}) are not allowed in production. "
                        "Use exact hostnames or configure origin-locking."
                    )
        if self.diag_enabled is None:
            self.diag_enabled = not self.is_prod_like

        if not (0.0 <= self.client_events_max_sample_rate <= 1.0):
            raise ValueError("CLIENT_EVENTS_MAX_SAMPLE_RATE must be between 0 and 1")
        if self.client_events_force_sample_rate is not None and not (
            0.0 <= self.client_events_force_sample_rate <= 1.0
        ):
            raise ValueError("CLIENT_EVENTS_FORCE_SAMPLE_RATE must be between 0 and 1")
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
