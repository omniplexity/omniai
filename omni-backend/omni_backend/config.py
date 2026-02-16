from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    host: str = field(default_factory=lambda: os.getenv("OMNI_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("OMNI_PORT", "8000")))
    db_path: str = field(default_factory=lambda: os.getenv("OMNI_DB_PATH", "./omni.db"))
    cors_origins_raw: str = field(default_factory=lambda: os.getenv("OMNI_CORS_ORIGINS", ""))
    max_request_bytes: int = field(default_factory=lambda: int(os.getenv("OMNI_MAX_REQUEST_BYTES", "262144")))
    sse_poll_interval_s: float = field(default_factory=lambda: float(os.getenv("OMNI_SSE_POLL_INTERVAL_S", "1.0")))
    sse_heartbeat_s: float = field(default_factory=lambda: float(os.getenv("OMNI_SSE_HEARTBEAT_SECONDS", os.getenv("OMNI_SSE_HEARTBEAT_S", "15.0"))))
    sse_max_replay: int = field(default_factory=lambda: int(os.getenv("OMNI_SSE_MAX_REPLAY", "500")))
    artifact_max_bytes: int = field(default_factory=lambda: int(os.getenv("OMNI_ARTIFACT_MAX_BYTES", str(25 * 1024 * 1024))))
    artifact_part_size: int = field(default_factory=lambda: int(os.getenv("OMNI_ARTIFACT_PART_SIZE", str(512 * 1024))))
    dev_mode: bool = field(default_factory=lambda: os.getenv("OMNI_DEV_MODE", "false").lower() == "true")
    workspace_root: str = field(default_factory=lambda: os.getenv("OMNI_WORKSPACE_ROOT", "./.omni_workspaces"))
    registry_root: str = field(default_factory=lambda: os.getenv("OMNI_REGISTRY_ROOT", "./.omni_registry"))
    allow_remote_mcp: bool = field(default_factory=lambda: os.getenv("OMNI_ALLOW_REMOTE_MCP", "false").lower() == "true")
    allow_community_install: bool = field(default_factory=lambda: os.getenv("OMNI_ALLOW_COMMUNITY_INSTALL", "false").lower() == "true")
    max_events_per_run: int = field(default_factory=lambda: int(os.getenv("OMNI_MAX_EVENTS_PER_RUN", "10000")))
    max_bytes_per_run: int = field(default_factory=lambda: int(os.getenv("OMNI_MAX_BYTES_PER_RUN", "10485760")))
    session_cookie_name: str = field(default_factory=lambda: os.getenv("OMNI_SESSION_COOKIE_NAME", "OMNI_SESSION"))
    session_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("OMNI_SESSION_TTL_SECONDS", "86400")))
    session_secure_cookie: bool = field(default_factory=lambda: os.getenv("OMNI_SESSION_SECURE", "false").lower() == "true")
    session_samesite: str = field(default_factory=lambda: os.getenv("OMNI_SESSION_SAMESITE", "lax"))
    dev_login_password: str = field(default_factory=lambda: os.getenv("OMNI_DEV_LOGIN_PASSWORD", ""))
    session_sliding_enabled: bool = field(default_factory=lambda: os.getenv("OMNI_SESSION_SLIDING_ENABLED", "true").lower() == "true")
    session_sliding_window_seconds: int = field(default_factory=lambda: int(os.getenv("OMNI_SESSION_SLIDING_WINDOW_SECONDS", "1800")))
    notify_tool_errors: bool = field(default_factory=lambda: os.getenv("OMNI_NOTIFY_TOOL_ERRORS", "true").lower() == "true")
    notify_tool_errors_only_codes_raw: str = field(default_factory=lambda: os.getenv("OMNI_NOTIFY_TOOL_ERRORS_ONLY_CODES", ""))
    notify_tool_errors_only_bindings_raw: str = field(default_factory=lambda: os.getenv("OMNI_NOTIFY_TOOL_ERRORS_ONLY_BINDINGS", ""))
    notify_tool_errors_max_per_run: int = field(default_factory=lambda: int(os.getenv("OMNI_NOTIFY_TOOL_ERRORS_MAX_PER_RUN", "5")))

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]
        if any(o == "*" for o in origins):
            raise ValueError("OMNI_CORS_ORIGINS must not include wildcard '*'")
        return origins

    @property
    def notify_tool_errors_only_codes(self) -> list[str]:
        return [v.strip() for v in self.notify_tool_errors_only_codes_raw.split(",") if v.strip()]

    @property
    def notify_tool_errors_only_bindings(self) -> list[str]:
        return [v.strip() for v in self.notify_tool_errors_only_bindings_raw.split(",") if v.strip()]
