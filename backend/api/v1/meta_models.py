"""Response models for `/v1/meta`."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class FeatureGate(BaseModel):
    supported: bool
    permitted: bool
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class MetaUser(BaseModel):
    id: str
    email: str
    username: str
    is_admin: bool


class MetaServer(BaseModel):
    version: str
    build_sha: str
    build_time: str
    environment: str
    server_time: str
    uptime_seconds: Optional[int] = None
    debug: bool


class MetaCsrf(BaseModel):
    cookie_name: str
    header_name: str


class MetaCookiePolicy(BaseModel):
    secure: bool
    samesite: str
    partitioned_configured: bool
    partitioned_enabled: bool


class MetaAuth(BaseModel):
    required: bool
    authenticated: bool
    user: Optional[MetaUser] = None
    session_cookie_name: str
    csrf: MetaCsrf
    cookie_policy: MetaCookiePolicy


class LaneRule(BaseModel):
    route_prefix: str
    auth_mode: str
    csrf_required: bool
    cors_mode: str
    status: str


class LaneRules(BaseModel):
    ui: LaneRule
    public: LaneRule
    dev: LaneRule
    legacy: LaneRule


class MetaFlags(BaseModel):
    schema_version: int = 1
    defaults: Dict[str, bool]
    effective: Dict[str, bool]


class MetaResponse(BaseModel):
    meta_version: int
    server: MetaServer
    auth: MetaAuth
    lanes: LaneRules
    capabilities: Dict[str, Any]
    features: Dict[str, FeatureGate]
    flags: MetaFlags
