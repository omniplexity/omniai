"""Test V2 repository layer — CRUD operations."""

from __future__ import annotations

import pytest
import pytest_asyncio

from omni_backend.v2.db.types import GUID
from omni_backend.v2.repositories.user_repo import SQLAlchemyUserRepository
from omni_backend.v2.repositories.project_repo import SQLAlchemyProjectRepository
from omni_backend.v2.repositories.thread_repo import SQLAlchemyThreadRepository
from omni_backend.v2.repositories.message_repo import SQLAlchemyMessageRepository
from omni_backend.v2.repositories.run_repo import SQLAlchemyRunRepository

pytestmark = pytest.mark.asyncio


class TestUserRepository:
    async def test_create_and_get(self, session):
        repo = SQLAlchemyUserRepository(session)
        user = await repo.create(username="alice", display_name="Alice")
        assert user.id is not None

        fetched = await repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.username == "alice"

    async def test_get_by_username(self, session):
        repo = SQLAlchemyUserRepository(session)
        await repo.create(username="bob", display_name="Bob")
        fetched = await repo.get_by_username("bob")
        assert fetched is not None
        assert fetched.display_name == "Bob"

    async def test_update(self, session):
        repo = SQLAlchemyUserRepository(session)
        user = await repo.create(username="carol", display_name="Carol")
        updated = await repo.update(user.id, display_name="Carol Updated")
        assert updated.display_name == "Carol Updated"

    async def test_delete(self, session):
        repo = SQLAlchemyUserRepository(session)
        user = await repo.create(username="dave", display_name="Dave")
        deleted = await repo.delete(user.id)
        assert deleted is True
        assert await repo.get_by_id(user.id) is None

    async def test_list_all(self, session):
        repo = SQLAlchemyUserRepository(session)
        await repo.create(username="user1", display_name="User 1")
        await repo.create(username="user2", display_name="User 2")
        users = await repo.list_all()
        assert len(users) == 2


class TestProjectRepository:
    async def test_create_and_members(self, session):
        user_repo = SQLAlchemyUserRepository(session)
        proj_repo = SQLAlchemyProjectRepository(session)

        user = await user_repo.create(username="projowner", display_name="Owner")
        project = await proj_repo.create(name="My Project", created_by=user.id)
        assert project.id is not None

        await proj_repo.add_member(project.id, user.id, "owner")
        members = await proj_repo.get_members(project.id)
        assert len(members) == 1
        assert members[0].role == "owner"

    async def test_list_for_user(self, session):
        user_repo = SQLAlchemyUserRepository(session)
        proj_repo = SQLAlchemyProjectRepository(session)

        user = await user_repo.create(username="lister", display_name="Lister")
        p1 = await proj_repo.create(name="P1")
        p2 = await proj_repo.create(name="P2")
        await proj_repo.add_member(p1.id, user.id, "member")
        await proj_repo.add_member(p2.id, user.id, "viewer")

        projects = await proj_repo.list_for_user(user.id)
        assert len(projects) == 2


class TestThreadRepository:
    async def test_create_and_list(self, session):
        proj_repo = SQLAlchemyProjectRepository(session)
        thread_repo = SQLAlchemyThreadRepository(session)

        project = await proj_repo.create(name="Thread Test")
        t1 = await thread_repo.create(project.id, "Thread 1")
        t2 = await thread_repo.create(project.id, "Thread 2")

        threads = await thread_repo.list_for_project(project.id)
        assert len(threads) == 2


class TestRunRepository:
    async def test_create_run_and_events(self, session):
        proj_repo = SQLAlchemyProjectRepository(session)
        thread_repo = SQLAlchemyThreadRepository(session)
        run_repo = SQLAlchemyRunRepository(session)

        project = await proj_repo.create(name="Run Test")
        thread = await thread_repo.create(project.id, "Run Thread")
        run = await run_repo.create(thread.id)
        assert run.status == "active"

        e1 = await run_repo.append_event(run.id, "message", {"text": "hi"}, "user")
        e2 = await run_repo.append_event(run.id, "response", {"text": "hello"}, "assistant")
        assert e1.seq == 1
        assert e2.seq == 2

        events = await run_repo.get_events(run.id)
        assert len(events) == 2
        assert events[0].seq == 1

    async def test_update_status(self, session):
        proj_repo = SQLAlchemyProjectRepository(session)
        thread_repo = SQLAlchemyThreadRepository(session)
        run_repo = SQLAlchemyRunRepository(session)

        project = await proj_repo.create(name="Status Test")
        thread = await thread_repo.create(project.id, "Status Thread")
        run = await run_repo.create(thread.id)

        updated = await run_repo.update_status(run.id, "completed")
        assert updated.status == "completed"


class TestMessageRepository:
    async def test_create_and_list(self, session):
        from omni_backend.v2.repositories.message_repo import SQLAlchemyMessageRepository

        proj_repo = SQLAlchemyProjectRepository(session)
        thread_repo = SQLAlchemyThreadRepository(session)
        msg_repo = SQLAlchemyMessageRepository(session)

        project = await proj_repo.create(name="Msg Test")
        thread = await thread_repo.create(project.id, "Msg Thread")

        m1 = await msg_repo.create(thread.id, "user", "Hello!")
        m2 = await msg_repo.create(thread.id, "assistant", "Hi there!")

        messages = await msg_repo.list_for_thread(thread.id)
        assert len(messages) == 2
        assert messages[0].role == "user"
