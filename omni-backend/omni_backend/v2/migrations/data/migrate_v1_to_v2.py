"""V1 SQLite → V2 data migration script.

Usage:
    python -m omni_backend.v2.migrations.data.migrate_v1_to_v2 \\
        --v1-db /path/to/omni.db \\
        --v2-url postgresql+asyncpg://omni:pass@localhost/omniai \\
        [--dry-run] [--resume]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from omni_backend.v2.db.models import (
    Base, User, Session as SessionModel, ApiKey, Project, ProjectMember,
    Thread, Message, Run, RunEvent, ToolCall, Artifact,
    WorkflowTemplate, WorkflowRun, WorkflowStep,
    MemoryEntry, Notification, AuditLog, Setting,
)
from omni_backend.v2.db.session import make_engine, make_session_factory
from omni_backend.v2.db.types import GUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("v1_to_v2_migration")

# V1 ID → V2 GUID mapping
_id_map: dict[str, str] = {}


def _map_id(v1_id: str | None) -> str | None:
    """Map a V1 ID to a V2 GUID, creating a new one if needed."""
    if v1_id is None:
        return None
    if v1_id not in _id_map:
        _id_map[v1_id] = v1_id if len(v1_id) == 36 else str(uuid4())
    return _id_map[v1_id]


def _parse_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def _v1_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # read-only, no FK enforcement needed
    return conn


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


async def migrate_users(v1: sqlite3.Connection, session: AsyncSession) -> int:
    """Migrate auth_identities + users → V2 users."""
    count = 0
    rows = v1.execute("""
        SELECT ai.user_id, ai.username, ai.password_hash, ai.created_at,
               u.display_name, u.avatar_url
        FROM auth_identities ai
        LEFT JOIN users u ON ai.user_id = u.user_id
    """).fetchall()

    for row in rows:
        v2_id = _map_id(row["user_id"])
        user = User(
            id=v2_id,
            username=row["username"],
            display_name=row["display_name"] or row["username"],
            avatar_url=row["avatar_url"],
            password_hash=row["password_hash"],
        )
        session.add(user)
        count += 1

    # Also migrate users without auth_identities
    orphan_rows = v1.execute("""
        SELECT u.user_id, u.display_name, u.avatar_url, u.created_at
        FROM users u
        LEFT JOIN auth_identities ai ON u.user_id = ai.user_id
        WHERE ai.user_id IS NULL
    """).fetchall()

    for row in orphan_rows:
        v2_id = _map_id(row["user_id"])
        user = User(
            id=v2_id,
            username=row["user_id"][:50],  # use user_id as fallback username
            display_name=row["display_name"] or row["user_id"],
            avatar_url=row["avatar_url"],
        )
        session.add(user)
        count += 1

    await session.flush()
    logger.info("Migrated %d users", count)
    return count


async def migrate_sessions(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM sessions").fetchall()
    for row in rows:
        obj = SessionModel(
            id=_map_id(row["session_id"]),
            user_id=_map_id(row["user_id"]),
            csrf_secret=row["csrf_secret"],
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else datetime.now(UTC),
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d sessions", count)
    return count


async def migrate_projects(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM projects").fetchall()
    for row in rows:
        obj = Project(id=_map_id(row["id"]), name=row["name"])
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d projects", count)
    return count


async def migrate_project_members(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM project_members").fetchall()
    for row in rows:
        obj = ProjectMember(
            project_id=_map_id(row["project_id"]),
            user_id=_map_id(row["user_id"]),
            role=row["role"],
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d project_members", count)
    return count


async def migrate_threads(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM threads").fetchall()
    for row in rows:
        obj = Thread(
            id=_map_id(row["id"]),
            project_id=_map_id(row["project_id"]),
            title=row["title"],
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d threads", count)
    return count


async def migrate_runs(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM runs").fetchall()
    for row in rows:
        obj = Run(
            id=_map_id(row["id"]),
            thread_id=_map_id(row["thread_id"]),
            status=row["status"],
            model_config_=_parse_json(row["pins_json"], {}),
            created_by=_map_id(row["created_by_user_id"]) if row["created_by_user_id"] else None,
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d runs", count)
    return count


async def migrate_run_events(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM run_events ORDER BY run_id, seq").fetchall()
    for row in rows:
        obj = RunEvent(
            id=_map_id(row["event_id"]),
            run_id=_map_id(row["run_id"]),
            seq=row["seq"],
            kind=row["kind"],
            payload=_parse_json(row["payload_json"], {}),
            actor=row["actor"],
            parent_event_id=_map_id(row["parent_event_id"]) if row["parent_event_id"] else None,
            correlation_id=row["correlation_id"],
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d run_events", count)
    return count


async def migrate_artifacts(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM artifacts").fetchall()
    for row in rows:
        # Find the run_id from artifact_links if available
        link = v1.execute(
            "SELECT run_id FROM artifact_links WHERE artifact_id = ? LIMIT 1",
            (row["artifact_id"],)
        ).fetchone()
        run_id = _map_id(link["run_id"]) if link else None

        obj = Artifact(
            id=_map_id(row["artifact_id"]),
            run_id=run_id,
            kind=row["kind"],
            media_type=row["media_type"],
            title=row["title"],
            size_bytes=row["size_bytes"],
            content_hash=row["content_hash"],
            storage_path=row["storage_path"] or row["storage_ref"],
            storage_kind=row["storage_kind"],
            created_by=_map_id(row["created_by_user_id"]) if row["created_by_user_id"] else None,
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d artifacts", count)
    return count


async def migrate_workflows(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM workflows").fetchall()
    for row in rows:
        obj = WorkflowTemplate(
            id=_map_id(row["workflow_id"]),
            name=row["name"],
            version=row["version"],
            graph={"artifact_id": row["graph_artifact_id"]},
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d workflow_templates", count)
    return count


async def migrate_workflow_runs(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM workflow_runs").fetchall()
    for row in rows:
        obj = WorkflowRun(
            id=_map_id(row["workflow_run_id"]),
            template_id=_map_id(row["workflow_id"]),
            run_id=_map_id(row["run_id"]),
            status=row["status"],
            inputs=_parse_json(row["inputs_json"], {}),
            state=_parse_json(row["state_json"], {}),
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d workflow_runs", count)
    return count


async def migrate_memory(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM memory_items").fetchall()
    for row in rows:
        # Get provenance for source field
        prov = v1.execute(
            "SELECT * FROM memory_provenance WHERE memory_id = ?", (row["memory_id"],)
        ).fetchone()
        source = {}
        if prov:
            source = {
                "project_id": prov["project_id"],
                "thread_id": prov["thread_id"],
                "run_id": prov["run_id"],
                "event_id": prov["event_id"],
                "kind": prov["source_kind"],
            }

        obj = MemoryEntry(
            id=_map_id(row["memory_id"]),
            type=row["type"],
            scope_type=row["scope_type"],
            scope_id=_map_id(row["scope_id"]) if row["scope_id"] else None,
            title=row["title"],
            content=row["content"],
            tags=_parse_json(row["tags_json"], []),
            importance=row["importance"],
            source=source,
            privacy=_parse_json(row["privacy_json"], {}),
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d memory_entries", count)
    return count


async def migrate_notifications(v1: sqlite3.Connection, session: AsyncSession) -> int:
    count = 0
    rows = v1.execute("SELECT * FROM notifications").fetchall()
    for row in rows:
        obj = Notification(
            id=_map_id(row["notification_id"]),
            user_id=_map_id(row["user_id"]),
            kind=row["kind"],
            payload=_parse_json(row["payload_json"], {}),
            project_id=_map_id(row["project_id"]) if row["project_id"] else None,
            run_id=_map_id(row["run_id"]) if row["run_id"] else None,
            read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
        )
        session.add(obj)
        count += 1
    await session.flush()
    logger.info("Migrated %d notifications", count)
    return count


async def run_migration(v1_db_path: str, v2_url: str, dry_run: bool = False) -> dict[str, int]:
    """Execute full V1→V2 migration."""
    logger.info("Starting V1→V2 migration (dry_run=%s)", dry_run)
    logger.info("V1 source: %s", v1_db_path)
    logger.info("V2 target: %s", v2_url.split("@")[-1] if "@" in v2_url else v2_url)

    v1 = _v1_connect(v1_db_path)
    engine = make_engine(v2_url)
    session_factory = make_session_factory(engine)

    # Ensure V2 tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    counts: dict[str, int] = {}

    async with session_factory() as session:
        async with session.begin():
            # Migration order follows FK dependencies
            counts["users"] = await migrate_users(v1, session)
            counts["sessions"] = await migrate_sessions(v1, session)
            counts["projects"] = await migrate_projects(v1, session)
            counts["project_members"] = await migrate_project_members(v1, session)
            counts["threads"] = await migrate_threads(v1, session)
            counts["runs"] = await migrate_runs(v1, session)
            counts["run_events"] = await migrate_run_events(v1, session)
            counts["artifacts"] = await migrate_artifacts(v1, session)
            counts["workflows"] = await migrate_workflows(v1, session)
            counts["workflow_runs"] = await migrate_workflow_runs(v1, session)
            counts["memory_entries"] = await migrate_memory(v1, session)
            counts["notifications"] = await migrate_notifications(v1, session)

            if dry_run:
                logger.info("DRY RUN — rolling back")
                await session.rollback()
            else:
                logger.info("Committing migration...")

    v1.close()
    await engine.dispose()

    logger.info("Migration complete. Counts: %s", counts)
    total = sum(counts.values())
    logger.info("Total rows migrated: %d", total)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Migrate V1 SQLite to V2")
    parser.add_argument("--v1-db", required=True, help="Path to V1 SQLite database")
    parser.add_argument("--v2-url", required=True, help="V2 database URL")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing")
    args = parser.parse_args()

    asyncio.run(run_migration(args.v1_db, args.v2_url, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
