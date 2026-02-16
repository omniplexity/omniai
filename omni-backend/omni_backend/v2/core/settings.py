"""V2 settings with local-dev-first defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


_LOCAL_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]


@dataclass(frozen=True)
class V2Settings:
    env: str = field(default_factory=lambda: os.getenv("OMNI_ENV", "dev"))
    host: str = field(default_factory=lambda: os.getenv("OMNI_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("OMNI_PORT", "8000")))

    database_url: str = field(
        default_factory=lambda: os.getenv(
            "OMNI_V2_DATABASE_URL", "sqlite+aiosqlite:///./omniai_dev.db"
        )
    )

    cors_origins_raw: str = field(
        default_factory=lambda: os.getenv("OMNI_V2_CORS_ORIGINS", "")
    )

    trusted_hosts: str = field(
        default_factory=lambda: os.getenv("OMNI_TRUSTED_HOSTS", "localhost,127.0.0.1")
    )

    sse_heartbeat_seconds: float = field(
        default_factory=lambda: float(os.getenv("OMNI_SSE_HEARTBEAT_SECONDS", "15"))
    )

    sse_max_replay: int = field(
        default_factory=lambda: int(os.getenv("OMNI_SSE_MAX_REPLAY", "500"))
    )

    max_request_bytes: int = field(
        default_factory=lambda: int(os.getenv("OMNI_MAX_REQUEST_BYTES", str(2 * 1024 * 1024)))
    )

    eventbus_backlog: int = field(
        default_factory=lambda: int(os.getenv("OMNI_EVENTBUS_BACKLOG", "1000"))
    )

    @property
    def cors_origins(self) -> list[str]:
        raw = [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]
        if any(o == "*" for o in raw):
            raise ValueError("OMNI_V2_CORS_ORIGINS must not include wildcard '*'")
        if raw:
            return raw
        # Default: local origins only
        return list(_LOCAL_CORS_ORIGINS)

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"
