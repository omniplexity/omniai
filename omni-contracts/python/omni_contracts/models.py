from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


RunEventKind = Literal[
    "run_created",
    "user_message",
    "assistant_message",
    "assistant_message_delta",
    "tool_call",
    "tool_result",
    "tool_error",
    "artifact_ref",
    "artifact_linked",
    "system_event",
    "editor_action",
    "run_status",
    "memory_item_created",
    "memory_item_updated",
    "memory_item_deleted",
    "memory_retrieved",
    "research_stage_started",
    "research_stage_completed",
    "research_source_created",
    "research_report_created",
    "workflow_defined",
    "workflow_run_started",
    "workflow_node_started",
    "workflow_node_completed",
    "workflow_node_failed",
    "workflow_run_completed",
    "tool_package_published",
    "tool_package_installed",
    "tool_package_uninstalled",
    "tool_package_yanked",
    "tool_pins_updated",
    "tool_package_reported",
    "tool_package_status_changed",
    "tool_package_mirrored",
    "collection_created",
    "collection_updated",
    "metrics_computed",
    "quota_exceeded",
    "project_member_added",
    "project_member_role_changed",
    "project_member_removed",
    "comment_created",
    "comment_deleted",
    "activity_emitted",
    "auth_session_created",
    "auth_session_revoked",
    "auth_login_failed",
    "auth_csrf_failed",
]

ActorKind = Literal["user", "assistant", "system", "tool"]


class Privacy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redact_level: Literal["none", "partial", "full"] = "none"
    contains_secrets: bool = False


class ModelPin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "stub"
    model_id: str = "stub-model"
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None


class ToolPin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class RuntimePin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executor_version: str = "v0"


class Pins(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: ModelPin = Field(default_factory=ModelPin)
    tools: list[ToolPin] = Field(default_factory=list)
    runtime: RuntimePin = Field(default_factory=RuntimePin)


class RunEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    run_id: UUID
    thread_id: UUID
    project_id: UUID
    seq: int = Field(ge=1)
    ts: datetime
    kind: RunEventKind
    payload: dict[str, Any]
    parent_event_id: UUID | None = None
    correlation_id: str | None = None
    actor: ActorKind
    privacy: Privacy = Field(default_factory=Privacy)
    pins: Pins = Field(default_factory=Pins)


class RunEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RunEventKind
    payload: dict[str, Any]
    parent_event_id: UUID | None = None
    correlation_id: str | None = None
    actor: ActorKind
    privacy: Privacy = Field(default_factory=Privacy)
    pins: Pins = Field(default_factory=Pins)


class SystemConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notify_tool_errors: bool
    notify_tool_errors_only_codes: list[str]
    notify_tool_errors_only_bindings: list[str]
    notify_tool_errors_max_per_run: int = Field(ge=0)
    sse_max_replay: int = Field(ge=0)
    sse_heartbeat_seconds: int = Field(ge=1)
    artifact_max_bytes: int = Field(ge=0)
    artifact_part_size: int = Field(ge=1)
    session_ttl_seconds: int = Field(ge=0)
    session_sliding_enabled: bool
    session_sliding_window_seconds: int = Field(ge=0)
    max_events_per_run: int = Field(ge=0)
    max_bytes_per_run: int = Field(ge=0)
    generated_at: datetime | None = None
    contract_version: str | None = None
    runtime_version: str | None = None
