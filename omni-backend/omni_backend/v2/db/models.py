"""V2 SQLAlchemy ORM models — 18 tables, dual-dialect (Postgres/SQLite)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .types import GUID, JSONB


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Provides created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# 1. users
# ---------------------------------------------------------------------------
class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # relationships
    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="user", cascade="all, delete-orphan")
    project_memberships: Mapped[list[ProjectMember]] = relationship(back_populates="user")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 2. sessions
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    csrf_secret: Mapped[str] = mapped_column(Text, nullable=False)
    device_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="sessions")


# ---------------------------------------------------------------------------
# 3. api_keys
# ---------------------------------------------------------------------------
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scopes: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="api_keys")


# ---------------------------------------------------------------------------
# 4. projects
# ---------------------------------------------------------------------------
class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    members: Mapped[list[ProjectMember]] = relationship(back_populates="project", cascade="all, delete-orphan")
    threads: Mapped[list[Thread]] = relationship(back_populates="project", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 5. project_members
# ---------------------------------------------------------------------------
class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # owner/admin/member/viewer
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="project_memberships")


# ---------------------------------------------------------------------------
# 6. threads
# ---------------------------------------------------------------------------
class Thread(TimestampMixin, Base):
    __tablename__ = "threads"
    __table_args__ = (
        Index("ix_threads_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="threads")
    messages: Mapped[list[Message]] = relationship(back_populates="thread", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="thread", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 7. messages
# ---------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread_created", "thread_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    thread_id: Mapped[str] = mapped_column(GUID(), ForeignKey("threads.id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user/assistant/system/tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    thread: Mapped[Thread] = relationship(back_populates="messages")
    run: Mapped[Run | None] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# 8. runs
# ---------------------------------------------------------------------------
class Run(TimestampMixin, Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    thread_id: Mapped[str] = mapped_column(GUID(), ForeignKey("threads.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    model_config_: Mapped[dict] = mapped_column("model_config", JSONB(), nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped[Thread] = relationship(back_populates="runs")
    events: Mapped[list[RunEvent]] = relationship(back_populates="run", cascade="all, delete-orphan")
    tool_calls: Mapped[list[ToolCall]] = relationship(back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="run")
    messages: Mapped[list[Message]] = relationship(back_populates="run")
    workflow_runs: Mapped[list[WorkflowRun]] = relationship(back_populates="run")


# ---------------------------------------------------------------------------
# 9. run_events
# ---------------------------------------------------------------------------
class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
        Index("ix_run_events_run_seq", "run_id", "seq"),
        Index("ix_run_events_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    run_id: Mapped[str] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_event_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    run: Mapped[Run] = relationship(back_populates="events")


# ---------------------------------------------------------------------------
# 10. tool_calls
# ---------------------------------------------------------------------------
class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    run_id: Mapped[str] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=False, index=True)
    tool_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    tool_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inputs: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    call_event_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("run_events.id"), nullable=True)
    result_event_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("run_events.id"), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[Run] = relationship(back_populates="tool_calls")


# ---------------------------------------------------------------------------
# 11. artifacts
# ---------------------------------------------------------------------------
class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    run_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="disk")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB(), nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    run: Mapped[Run | None] = relationship(back_populates="artifacts")


# ---------------------------------------------------------------------------
# 12. workflow_templates
# ---------------------------------------------------------------------------
class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_workflow_templates_name_version"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    graph: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    workflow_runs: Mapped[list[WorkflowRun]] = relationship(back_populates="template")


# ---------------------------------------------------------------------------
# 13. workflow_runs
# ---------------------------------------------------------------------------
class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    template_id: Mapped[str] = mapped_column(GUID(), ForeignKey("workflow_templates.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    state: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="workflow_runs")
    run: Mapped[Run] = relationship(back_populates="workflow_runs")
    steps: Mapped[list[WorkflowStep]] = relationship(back_populates="workflow_run", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 14. workflow_steps
# ---------------------------------------------------------------------------
class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    workflow_run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("workflow_runs.id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    outputs: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# 15. memory_entries
# ---------------------------------------------------------------------------
class MemoryEntry(TimestampMixin, Base):
    __tablename__ = "memory_entries"
    __table_args__ = (
        Index("ix_memory_scope", "scope_type", "scope_id"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=list)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    privacy: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# 16. notifications
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    project_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=True)
    run_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("runs.id"), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="notifications")


# ---------------------------------------------------------------------------
# 17. audit_log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=GUID.new)
    user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# 18. settings
# ---------------------------------------------------------------------------
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
