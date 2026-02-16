"""Test V2 ORM models — creation, constraints, relationships."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from omni_backend.v2.db.models import (
    User, Session as SessionModel, Project, ProjectMember,
    Thread, Message, Run, RunEvent, ToolCall, Artifact,
    WorkflowTemplate, WorkflowRun, WorkflowStep,
    MemoryEntry, Notification, AuditLog, Setting,
)
from omni_backend.v2.db.types import GUID

pytestmark = pytest.mark.asyncio


async def _create_user(session, username="testuser") -> User:
    user = User(
        id=GUID.new(), username=username,
        display_name="Test User", password_hash="$argon2id$test",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_project(session, user_id=None) -> Project:
    project = Project(id=GUID.new(), name="Test Project", created_by=user_id)
    session.add(project)
    await session.flush()
    return project


async def _create_thread(session, project_id) -> Thread:
    thread = Thread(id=GUID.new(), project_id=project_id, title="Test Thread")
    session.add(thread)
    await session.flush()
    return thread


async def _create_run(session, thread_id, user_id=None) -> Run:
    run = Run(id=GUID.new(), thread_id=thread_id, status="active", created_by=user_id)
    session.add(run)
    await session.flush()
    return run


class TestUserModel:
    async def test_create_user(self, session):
        user = await _create_user(session)
        assert user.id is not None
        assert user.username == "testuser"
        assert user.is_active is True

    async def test_unique_username(self, session):
        await _create_user(session, "unique1")
        with pytest.raises(IntegrityError):
            await _create_user(session, "unique1")


class TestProjectModel:
    async def test_create_project(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        assert project.id is not None
        assert project.name == "Test Project"

    async def test_project_members(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        member = ProjectMember(project_id=project.id, user_id=user.id, role="owner")
        session.add(member)
        await session.flush()
        assert member.role == "owner"


class TestThreadModel:
    async def test_create_thread(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        thread = await _create_thread(session, project.id)
        assert thread.project_id == project.id
        assert thread.pinned is False


class TestRunEventModel:
    async def test_create_run_and_events(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        thread = await _create_thread(session, project.id)
        run = await _create_run(session, thread.id)

        event1 = RunEvent(
            id=GUID.new(), run_id=run.id, seq=1,
            kind="message", payload={"text": "hello"}, actor="user",
        )
        event2 = RunEvent(
            id=GUID.new(), run_id=run.id, seq=2,
            kind="response", payload={"text": "hi"}, actor="assistant",
        )
        session.add_all([event1, event2])
        await session.flush()

        result = await session.execute(
            select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
        )
        events = result.scalars().all()
        assert len(events) == 2
        assert events[0].seq == 1
        assert events[1].seq == 2

    async def test_unique_run_seq_constraint(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        thread = await _create_thread(session, project.id)
        run = await _create_run(session, thread.id)

        event1 = RunEvent(
            id=GUID.new(), run_id=run.id, seq=1,
            kind="msg", payload={}, actor="user",
        )
        session.add(event1)
        await session.flush()

        event_dup = RunEvent(
            id=GUID.new(), run_id=run.id, seq=1,
            kind="msg2", payload={}, actor="user",
        )
        session.add(event_dup)
        with pytest.raises(IntegrityError):
            await session.flush()


class TestArtifactModel:
    async def test_create_artifact(self, session):
        artifact = Artifact(
            id=GUID.new(), kind="file", media_type="text/plain",
            size_bytes=42, content_hash="abc123", storage_path="/tmp/test",
        )
        session.add(artifact)
        await session.flush()
        assert artifact.storage_kind == "disk"


class TestSettingModel:
    async def test_create_setting(self, session):
        setting = Setting(key="theme", value={"mode": "dark"})
        session.add(setting)
        await session.flush()
        result = await session.get(Setting, "theme")
        assert result.value == {"mode": "dark"}


class TestWorkflowModels:
    async def test_workflow_chain(self, session):
        user = await _create_user(session)
        project = await _create_project(session, user.id)
        thread = await _create_thread(session, project.id)
        run = await _create_run(session, thread.id)

        template = WorkflowTemplate(
            id=GUID.new(), name="research", version="1.0",
            graph={"steps": ["plan", "execute"]},
        )
        session.add(template)
        await session.flush()

        wf_run = WorkflowRun(
            id=GUID.new(), template_id=template.id, run_id=run.id,
            status="running", inputs={"query": "test"},
        )
        session.add(wf_run)
        await session.flush()

        step = WorkflowStep(
            id=GUID.new(), workflow_run_id=wf_run.id,
            step_name="plan", status="completed",
        )
        session.add(step)
        await session.flush()
        assert step.workflow_run_id == wf_run.id
