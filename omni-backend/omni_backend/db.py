from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

MAX_LOCK_RETRIES = 5
LOCK_BACKOFF_SECONDS = 0.05

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS threads(
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS runs(
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by_user_id TEXT NULL,
  pins_json TEXT NOT NULL,
  FOREIGN KEY(thread_id) REFERENCES threads(id)
);
CREATE TABLE IF NOT EXISTS run_events(
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  parent_event_id TEXT NULL,
  correlation_id TEXT NULL,
  actor TEXT NOT NULL,
  privacy_json TEXT NOT NULL,
  pins_json TEXT NOT NULL,
  UNIQUE(run_id, seq),
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS artifacts(
  artifact_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  media_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  storage_ref TEXT NOT NULL,
  title TEXT NULL,
  storage_path TEXT NULL,
  storage_kind TEXT NOT NULL DEFAULT 'disk',
  etag TEXT NULL,
  created_by_user_id TEXT NULL
);
CREATE TABLE IF NOT EXISTS artifact_links(
  run_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  source_event_id TEXT NULL,
  correlation_id TEXT NULL,
  tool_id TEXT NULL,
  tool_version TEXT NULL,
  purpose TEXT NULL,
  created_at TEXT NULL,
  PRIMARY KEY(run_id, event_id, artifact_id)
);
CREATE TABLE IF NOT EXISTS tool_correlations(
  run_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  tool_call_event_id TEXT NULL,
  tool_outcome_event_id TEXT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(run_id, correlation_id)
);
CREATE TABLE IF NOT EXISTS research_source_links(
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  correlation_id TEXT NULL,
  tool_call_event_id TEXT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(run_id, source_id)
);
CREATE TABLE IF NOT EXISTS tools(
  tool_id TEXT NOT NULL,
  version TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  installed_at TEXT NOT NULL,
  PRIMARY KEY(tool_id, version)
);
CREATE TABLE IF NOT EXISTS policy_grants(
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  PRIMARY KEY(project_id, scope)
);
CREATE TABLE IF NOT EXISTS approvals(
  approval_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  tool_call_event_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  inputs_json TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  decided_at TEXT NULL,
  decided_by TEXT NULL
);
CREATE TABLE IF NOT EXISTS mcp_servers(
  server_id TEXT PRIMARY KEY,
  scope_type TEXT NOT NULL,
  scope_id TEXT NULL,
  name TEXT NOT NULL,
  transport TEXT NOT NULL,
  endpoint_url TEXT NULL,
  stdio_cmd_json TEXT NULL,
  env_json TEXT NOT NULL DEFAULT '{}',
  auth_state_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  last_health_ts TEXT NULL,
  last_latency_ms INTEGER NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  protocol_version TEXT NULL,
  session_id TEXT NULL
);
CREATE TABLE IF NOT EXISTS mcp_catalog(
  server_id TEXT PRIMARY KEY,
  fetched_at TEXT NOT NULL,
  tools_json TEXT NOT NULL,
  next_cursor TEXT NULL
);
CREATE TABLE IF NOT EXISTS research_sources(
  source_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  snippet TEXT NULL,
  retrieved_at TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  artifact_id TEXT NULL
);
CREATE TABLE IF NOT EXISTS workflows(
  workflow_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  graph_artifact_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_runs(
  workflow_run_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  status TEXT NOT NULL,
  inputs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT NULL,
  state_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS memory_items(
  memory_id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  scope_type TEXT NOT NULL,
  scope_id TEXT NULL,
  title TEXT NULL,
  content TEXT NOT NULL,
  tags_json TEXT NOT NULL DEFAULT '[]',
  importance REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT NULL,
  privacy_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_provenance(
  memory_id TEXT PRIMARY KEY,
  project_id TEXT NULL,
  thread_id TEXT NULL,
  run_id TEXT NULL,
  event_id TEXT NULL,
  artifact_id TEXT NULL,
  source_kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registry_packages(
  package_id TEXT NOT NULL,
  version TEXT NOT NULL,
  tier TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  files_json TEXT NOT NULL,
  signature_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  checks_json TEXT NOT NULL DEFAULT '{}',
  moderation_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  PRIMARY KEY(package_id, version)
);
CREATE TABLE IF NOT EXISTS registry_keys(
  public_key_id TEXT PRIMARY KEY,
  public_key_base64 TEXT NOT NULL,
  added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_tool_pins(
  project_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  pinned_at TEXT NOT NULL,
  PRIMARY KEY(project_id, tool_id)
);
CREATE TABLE IF NOT EXISTS registry_reports(
  report_id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  version TEXT NOT NULL,
  reporter TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  details TEXT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS collections(
  collection_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NULL,
  packages_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_metrics(
  run_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  completed_at TEXT NULL,
  duration_ms INTEGER NULL,
  event_count INTEGER NOT NULL,
  tool_calls INTEGER NOT NULL,
  tool_errors INTEGER NOT NULL,
  artifacts_count INTEGER NOT NULL,
  bytes_in INTEGER NOT NULL,
  bytes_out INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_metrics(
  tool_id TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  calls INTEGER NOT NULL,
  errors INTEGER NOT NULL,
  last_latency_ms INTEGER NULL,
  last_error_code TEXT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(tool_id, tool_version)
);
CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  avatar_url TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_members(
  project_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY(project_id, user_id)
);
CREATE TABLE IF NOT EXISTS comments(
  comment_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  run_id TEXT NULL,
  thread_id TEXT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  author_id TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  deleted_at TEXT NULL
);
CREATE TABLE IF NOT EXISTS activity(
  activity_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  ref_type TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_identities(
  user_id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
  session_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  csrf_secret TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_project_state(
  user_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  last_seen_activity_seq INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(user_id, project_id)
);
CREATE TABLE IF NOT EXISTS notifications(
  notification_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  project_id TEXT NULL,
  run_id TEXT NULL,
  activity_seq INTEGER NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  read_at TEXT NULL
);
CREATE TABLE IF NOT EXISTS notification_state(
  user_id TEXT PRIMARY KEY,
  last_seen_notification_seq INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys(
  key TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  response_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provenance_cache(
  run_id TEXT PRIMARY KEY,
  computed_at TEXT NOT NULL,
  last_seq INTEGER NOT NULL,
  graph_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS system_counters(
  name TEXT PRIMARY KEY,
  value INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS system_gauges(
  name TEXT PRIMARY KEY,
  value_real REAL NULL,
  value_text TEXT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_uploads(
  upload_id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  finalized_at TEXT NULL,
  parts_json TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
  memory_id UNINDEXED,
  title,
  content,
  tags
);
CREATE INDEX IF NOT EXISTS idx_run_events_run_seq ON run_events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_run_events_correlation_id ON run_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read_id ON notifications(user_id, read_at, notification_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created_desc ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_activity_seq ON notifications(user_id, activity_seq);
"""


@dataclass
class RunContext:
    run_id: str
    thread_id: str
    project_id: str


class QuotaExceededError(Exception):
    def __init__(self, scope: str, limit: int, observed: int):
        super().__init__(f"quota exceeded: {scope} {observed}>{limit}")
        self.scope = scope
        self.limit = limit
        self.observed = observed


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            try:
                conn.execute("ALTER TABLE activity ADD COLUMN activity_seq INTEGER")
            except sqlite3.OperationalError:
                pass
            for stmt in [
                "ALTER TABLE runs ADD COLUMN created_by_user_id TEXT",
                "ALTER TABLE artifact_links ADD COLUMN source_event_id TEXT",
                "ALTER TABLE artifact_links ADD COLUMN correlation_id TEXT",
                "ALTER TABLE artifact_links ADD COLUMN tool_id TEXT",
                "ALTER TABLE artifact_links ADD COLUMN tool_version TEXT",
                "ALTER TABLE artifact_links ADD COLUMN purpose TEXT",
                "ALTER TABLE artifact_links ADD COLUMN created_at TEXT",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            for stmt in [
                "ALTER TABLE artifacts ADD COLUMN storage_path TEXT",
                "ALTER TABLE artifacts ADD COLUMN storage_kind TEXT NOT NULL DEFAULT 'disk'",
                "ALTER TABLE artifacts ADD COLUMN etag TEXT",
                "ALTER TABLE artifacts ADD COLUMN created_by_user_id TEXT",
            ]:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            self._backfill_notification_state(conn)

    def _backfill_notification_state(self, conn: sqlite3.Connection) -> None:
        now = datetime.now(UTC).isoformat()
        # Ensure users with notifications have a state row.
        conn.execute(
            """
            INSERT OR IGNORE INTO notification_state(user_id, last_seen_notification_seq, updated_at)
            SELECT n.user_id, 0, ?
            FROM notifications n
            GROUP BY n.user_id
            """,
            (now,),
        )
        # One-way backfill: only lift missing/zero state from existing read notifications.
        conn.execute(
            """
            UPDATE notification_state
            SET last_seen_notification_seq = (
                  SELECT COALESCE(MAX(n.rowid), 0)
                  FROM notifications n
                  WHERE n.user_id = notification_state.user_id
                    AND n.read_at IS NOT NULL
                ),
                updated_at = ?
            WHERE COALESCE(last_seen_notification_seq, 0) = 0
              AND EXISTS (
                SELECT 1
                FROM notifications n2
                WHERE n2.user_id = notification_state.user_id
                  AND n2.read_at IS NOT NULL
              )
            """,
            (now,),
        )

    @contextmanager
    def _retrying_connection(self):
        for attempt in range(MAX_LOCK_RETRIES):
            conn = self.connect()
            try:
                yield conn
                conn.close()
                return
            except sqlite3.OperationalError as exc:
                conn.close()
                if "locked" not in str(exc).lower() or attempt == MAX_LOCK_RETRIES - 1:
                    raise
                time.sleep(LOCK_BACKOFF_SECONDS * (attempt + 1))

    def create_project(self, name: str) -> dict[str, str]:
        pid = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO projects(id, name, created_at) VALUES(?, ?, ?)", (pid, name, created_at))
            conn.execute("COMMIT")
        return {"id": pid, "name": name, "created_at": created_at}

    def ensure_user(self, user_id: str, display_name: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        # Try to get the actual username from auth_identities to use as default display name
        actual_username = None
        with self.connect() as conn:
            identity_row = conn.execute("SELECT username FROM auth_identities WHERE user_id = ?", (user_id,)).fetchone()
            if identity_row:
                actual_username = identity_row["username"]
        # Use provided display_name, or fall back to actual username, then UUID
        dname = (display_name or actual_username or user_id).strip() or user_id
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO users(user_id, display_name, created_at) VALUES(?, ?, ?)", (user_id, dname, now))
            conn.execute("COMMIT")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("""
                SELECT u.user_id, u.display_name, u.avatar_url, u.created_at, i.username 
                FROM users u 
                LEFT JOIN auth_identities i ON u.user_id = i.user_id 
                WHERE u.user_id = ?
            """, (user_id,)).fetchone()
        return dict(row) if row else None

    def update_user_avatar(self, user_id: str, avatar_url: str) -> dict[str, Any] | None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE users SET avatar_url = ? WHERE user_id = ?", (avatar_url, user_id)).rowcount
            conn.execute("COMMIT")
        if not changed:
            return None
        return self.get_user(user_id)

    def get_identity_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM auth_identities WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def create_identity(self, username: str, password_hash: str | None = None) -> dict[str, Any]:
        user_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO auth_identities(user_id, username, password_hash, created_at) VALUES(?, ?, ?, ?)",
                (user_id, username, password_hash, created_at),
            )
            conn.execute("COMMIT")
        self.ensure_user(user_id, username)
        return {"user_id": user_id, "username": username, "password_hash": password_hash, "created_at": created_at}

    def create_session(self, user_id: str, expires_at: str, csrf_secret: str) -> dict[str, Any]:
        session_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO sessions(session_id, user_id, created_at, expires_at, csrf_secret) VALUES(?, ?, ?, ?, ?)",
                (session_id, user_id, created_at, expires_at, csrf_secret),
            )
            conn.execute("COMMIT")
        return {"session_id": session_id, "user_id": user_id, "created_at": created_at, "expires_at": expires_at, "csrf_secret": csrf_secret}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def rotate_session(self, old_session_id: str | None, user_id: str, expires_at: str, csrf_secret: str) -> dict[str, Any]:
        if old_session_id:
            self.delete_session(old_session_id)
        return self.create_session(user_id, expires_at, csrf_secret)

    def extend_session(self, session_id: str, expires_at: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", (expires_at, session_id)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def revoke_sessions_for_user(self, user_id: str) -> int:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount
            conn.execute("COMMIT")
        return int(changed)

    def update_identity_password_hash(self, user_id: str, password_hash: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE auth_identities SET password_hash = ? WHERE user_id = ?", (password_hash, user_id)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def update_user_display_name(self, user_id: str, display_name: str) -> dict[str, Any] | None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (display_name, user_id)).rowcount
            conn.execute("COMMIT")
        if not changed:
            return None
        return self.ensure_user(user_id)

    def add_project_member(self, project_id: str, user_id: str, role: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR REPLACE INTO project_members(project_id, user_id, role, added_at) VALUES(?, ?, ?, ?)",
                (project_id, user_id, role, datetime.now(UTC).isoformat()),
            )
            conn.execute("COMMIT")

    def get_project_member_role(self, project_id: str, user_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT role FROM project_members WHERE project_id = ? AND user_id = ?", (project_id, user_id)).fetchone()
        return str(row["role"]) if row else None

    def list_project_members(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT m.project_id, m.user_id, m.role, m.added_at, u.display_name FROM project_members m LEFT JOIN users u ON u.user_id = m.user_id WHERE project_id = ? ORDER BY m.added_at ASC",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def remove_project_member(self, project_id: str, user_id: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("DELETE FROM project_members WHERE project_id = ? AND user_id = ?", (project_id, user_id)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def create_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        comment_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO comments(comment_id, project_id, run_id, thread_id, target_type, target_id, author_id, body, created_at, deleted_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    comment_id,
                    payload["project_id"],
                    payload.get("run_id"),
                    payload.get("thread_id"),
                    payload["target_type"],
                    payload["target_id"],
                    payload["author_id"],
                    payload["body"],
                    now,
                ),
            )
            conn.execute("COMMIT")
        return self.get_comment(comment_id) or {"comment_id": comment_id}

    def get_comment(self, comment_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM comments WHERE comment_id = ?", (comment_id,)).fetchone()
        return dict(row) if row else None

    def list_comments(self, project_id: str, run_id: str | None = None, target_type: str | None = None, target_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM comments WHERE project_id = ? AND deleted_at IS NULL"
        args: list[Any] = [project_id]
        if run_id:
            q += " AND run_id = ?"
            args.append(run_id)
        if target_type:
            q += " AND target_type = ?"
            args.append(target_type)
        if target_id:
            q += " AND target_id = ?"
            args.append(target_id)
        q += " ORDER BY created_at ASC"
        with self.connect() as conn:
            rows = conn.execute(q, tuple(args)).fetchall()
        return [dict(r) for r in rows]

    def delete_comment(self, comment_id: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE comments SET deleted_at = ? WHERE comment_id = ? AND deleted_at IS NULL", (datetime.now(UTC).isoformat(), comment_id)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def add_activity(self, project_id: str, kind: str, ref_type: str, ref_id: str, actor_id: str) -> dict[str, Any]:
        activity_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO activity(activity_id, project_id, kind, ref_type, ref_id, actor_id, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (activity_id, project_id, kind, ref_type, ref_id, actor_id, now),
            )
            row = conn.execute("SELECT rowid FROM activity WHERE activity_id = ?", (activity_id,)).fetchone()
            activity_seq = int(row["rowid"]) if row else 0
            conn.execute("UPDATE activity SET activity_seq = ? WHERE activity_id = ?", (activity_seq, activity_id))
            conn.execute("COMMIT")
        return {"activity_id": activity_id, "activity_seq": activity_seq, "project_id": project_id, "kind": kind, "ref_type": ref_type, "ref_id": ref_id, "actor_id": actor_id, "created_at": now}

    def list_activity(
        self,
        project_id: str,
        after: str | None = None,
        limit: int = 50,
        after_seq: int | None = None,
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if after_seq is not None:
                rows = conn.execute(
                    """
                    SELECT rowid as activity_seq, activity_id, project_id, kind, ref_type, ref_id, actor_id, created_at
                    FROM activity
                    WHERE project_id = ? AND rowid > ?
                    ORDER BY rowid ASC
                    LIMIT ?
                    """,
                    (project_id, after_seq, limit),
                ).fetchall()
            elif after:
                rows = conn.execute(
                    "SELECT * FROM activity WHERE project_id = ? AND created_at > ? ORDER BY created_at ASC LIMIT ?",
                    (project_id, after, limit),
                ).fetchall()
            else:
                order = "ASC" if ascending else "DESC"
                rows = conn.execute(
                    f"SELECT rowid as activity_seq, activity_id, project_id, kind, ref_type, ref_id, actor_id, created_at FROM activity WHERE project_id = ? ORDER BY rowid {order} LIMIT ?",
                    (project_id, limit),
                ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            if "activity_seq" not in item or item["activity_seq"] is None:
                item["activity_seq"] = 0
            out.append(item)
        return out

    def latest_run_for_project(self, project_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT r.id AS run_id
                FROM runs r
                JOIN threads t ON t.id = r.thread_id
                WHERE t.project_id = ?
                ORDER BY r.created_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return str(row["run_id"]) if row else None

    def latest_run_for_user(self, user_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT r.id AS run_id
                FROM runs r
                JOIN threads t ON t.id = r.thread_id
                JOIN project_members pm ON pm.project_id = t.project_id
                WHERE pm.user_id = ?
                ORDER BY r.created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return str(row["run_id"]) if row else None

    def latest_project_for_user(self, user_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT pm.project_id
                FROM project_members pm
                JOIN projects p ON p.id = pm.project_id
                WHERE pm.user_id = ?
                ORDER BY p.created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return str(row["project_id"]) if row else None

    def get_user_project_state(self, user_id: str, project_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT user_id, project_id, last_seen_activity_seq, updated_at FROM user_project_state WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            ).fetchone()
            if row:
                return dict(row)
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR IGNORE INTO user_project_state(user_id, project_id, last_seen_activity_seq, updated_at) VALUES(?, ?, 0, ?)",
                (user_id, project_id, now),
            )
            conn.execute("COMMIT")
        return {"user_id": user_id, "project_id": project_id, "last_seen_activity_seq": 0, "updated_at": now}

    def mark_activity_seen(self, user_id: str, project_id: str, seq: int) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO user_project_state(user_id, project_id, last_seen_activity_seq, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(user_id, project_id) DO UPDATE SET
                  last_seen_activity_seq = CASE
                    WHEN excluded.last_seen_activity_seq > user_project_state.last_seen_activity_seq THEN excluded.last_seen_activity_seq
                    ELSE user_project_state.last_seen_activity_seq
                  END,
                  updated_at = excluded.updated_at
                """,
                (user_id, project_id, int(seq), now),
            )
            conn.execute("COMMIT")
        return self.get_user_project_state(user_id, project_id)

    def max_activity_seq(self, project_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(rowid), 0) as max_seq FROM activity WHERE project_id = ?", (project_id,)).fetchone()
        return int(row["max_seq"] if row else 0)

    def get_project_owner_ids(self, project_id: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM project_members WHERE project_id = ? AND role = 'owner' ORDER BY user_id ASC",
                (project_id,),
            ).fetchall()
        return [str(r["user_id"]) for r in rows]

    def get_run_creator_user_id(self, run_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT created_by_user_id FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        uid = row["created_by_user_id"]
        return str(uid) if uid else None

    def create_notification(
        self,
        *,
        user_id: str,
        kind: str,
        payload: dict[str, Any],
        project_id: str | None = None,
        run_id: str | None = None,
        activity_seq: int | None = None,
    ) -> dict[str, Any]:
        notification_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO notifications(
                  notification_id, user_id, project_id, run_id, activity_seq, kind, created_at, payload_json, read_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (notification_id, user_id, project_id, run_id, activity_seq, kind, now, json.dumps(payload)),
            )
            row = conn.execute(
                """
                SELECT rowid AS notification_seq, notification_id, user_id, project_id, run_id, activity_seq, kind, created_at, payload_json, read_at
                FROM notifications WHERE notification_id = ?
                """,
                (notification_id,),
            ).fetchone()
            conn.execute("COMMIT")
        if not row:
            raise RuntimeError("failed to persist notification")
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json"))
        out["notification_seq"] = int(out["notification_seq"])
        return out

    def list_notifications(
        self,
        user_id: str,
        limit: int = 50,
        after_id: str | None = None,
        after_seq: int | None = None,
        unread_only: bool = False,
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        lim = min(max(int(limit), 1), 200)
        order = "ASC" if ascending else "DESC"
        q = """
            SELECT rowid AS notification_seq, notification_id, user_id, project_id, run_id, activity_seq, kind, created_at, payload_json, read_at
            FROM notifications
            WHERE user_id = ?
        """
        args: list[Any] = [user_id]
        if unread_only:
            q += " AND read_at IS NULL"
        if after_seq is not None:
            q += " AND rowid > ?"
            args.append(int(after_seq))
            order = "ASC"
        elif after_id:
            q += " AND rowid > COALESCE((SELECT rowid FROM notifications WHERE notification_id = ? AND user_id = ?), 0)"
            args.extend([after_id, user_id])
            order = "ASC"
        q += f" ORDER BY rowid {order} LIMIT ?"
        args.append(lim)
        with self.connect() as conn:
            rows = conn.execute(q, tuple(args)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["notification_seq"] = int(item["notification_seq"])
            item["payload"] = json.loads(item.pop("payload_json"))
            out.append(item)
        return out

    def mark_notifications_read(
        self,
        user_id: str,
        *,
        up_to_seq: int | None = None,
        notification_ids: list[str] | None = None,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        changed = 0
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if up_to_seq is not None:
                changed = self.mark_notifications_read_up_to_seq(user_id, int(up_to_seq), now=now, conn=conn)
            elif notification_ids:
                placeholders = ",".join("?" for _ in notification_ids)
                changed = conn.execute(
                    f"UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE user_id = ? AND notification_id IN ({placeholders})",
                    (now, user_id, *notification_ids),
                ).rowcount
            conn.execute("COMMIT")
        return int(changed)

    def mark_notifications_read_up_to_seq(
        self,
        user_id: str,
        up_to_seq: int,
        *,
        now: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        ts = now or datetime.now(UTC).isoformat()
        if conn is not None:
            return int(
                conn.execute(
                    "UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE user_id = ? AND rowid <= ?",
                    (ts, user_id, int(up_to_seq)),
                ).rowcount
            )
        with self._retrying_connection() as c2:
            c2.execute("BEGIN IMMEDIATE")
            changed = c2.execute(
                "UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE user_id = ? AND rowid <= ?",
                (ts, user_id, int(up_to_seq)),
            ).rowcount
            c2.execute("COMMIT")
        return int(changed)

    def get_unread_count(self, user_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS unread_count FROM notifications WHERE user_id = ? AND read_at IS NULL",
                (user_id,),
            ).fetchone()
        return int(row["unread_count"]) if row else 0

    def count_notifications_for_run_kind(self, run_id: str, kind: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM notifications WHERE run_id = ? AND kind = ?",
                (run_id, kind),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def get_notification_state(self, user_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT user_id, last_seen_notification_seq, updated_at FROM notification_state WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row:
                return dict(row)
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR IGNORE INTO notification_state(user_id, last_seen_notification_seq, updated_at) VALUES(?, 0, ?)",
                (user_id, now),
            )
            conn.execute("COMMIT")
        return {"user_id": user_id, "last_seen_notification_seq": 0, "updated_at": now}

    def set_last_seen_notification_seq(self, user_id: str, seq: int) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO notification_state(user_id, last_seen_notification_seq, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  last_seen_notification_seq = CASE
                    WHEN excluded.last_seen_notification_seq > notification_state.last_seen_notification_seq THEN excluded.last_seen_notification_seq
                    ELSE notification_state.last_seen_notification_seq
                  END,
                  updated_at = excluded.updated_at
                """,
                (user_id, int(seq), now),
            )
            conn.execute("COMMIT")
        return self.get_notification_state(user_id)

    def get_idempotency_response(self, key: str, user_id: str, endpoint: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM idempotency_keys WHERE key = ? AND user_id = ? AND endpoint = ?",
                (key, user_id, endpoint),
            ).fetchone()
        if not row:
            return None
        return json.loads(str(row["response_json"]))

    def put_idempotency_response(self, key: str, user_id: str, endpoint: str, response: dict[str, Any]) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency_keys(key, user_id, endpoint, created_at, response_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (key, user_id, endpoint, datetime.now(UTC).isoformat(), json.dumps(response)),
            )
            conn.execute("COMMIT")

    def list_projects(self) -> list[dict[str, str]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id, name, created_at FROM projects ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]

    def create_thread(self, project_id: str, title: str) -> dict[str, str] | None:
        tid = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone():
                conn.execute("ROLLBACK")
                return None
            conn.execute("INSERT INTO threads(id, project_id, title, created_at) VALUES(?, ?, ?, ?)", (tid, project_id, title, created_at))
            conn.execute("COMMIT")
        return {"id": tid, "project_id": project_id, "title": title, "created_at": created_at}

    def list_threads(self, project_id: str) -> tuple[bool, list[dict[str, str]]]:
        with self.connect() as conn:
            if not conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone():
                return False, []
            rows = conn.execute("SELECT id, project_id, title, created_at FROM threads WHERE project_id = ? ORDER BY created_at ASC", (project_id,)).fetchall()
        return True, [dict(r) for r in rows]

    def create_run(self, thread_id: str, status: str, pins: dict[str, Any], created_by_user_id: str | None = None) -> dict[str, Any] | None:
        rid = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT id FROM threads WHERE id = ?", (thread_id,)).fetchone():
                conn.execute("ROLLBACK")
                return None
            conn.execute(
                "INSERT INTO runs(id, thread_id, status, created_at, created_by_user_id, pins_json) VALUES(?, ?, ?, ?, ?, ?)",
                (rid, thread_id, status, created_at, created_by_user_id, json.dumps(pins)),
            )
            conn.execute(
                """
                INSERT INTO run_metrics(run_id, created_at, completed_at, duration_ms, event_count, tool_calls, tool_errors, artifacts_count, bytes_in, bytes_out)
                VALUES(?, ?, NULL, NULL, 0, 0, 0, 0, 0, 0)
                """,
                (rid, created_at),
            )
            conn.execute("COMMIT")
        return {"id": rid, "thread_id": thread_id, "status": status, "created_at": created_at, "created_by_user_id": created_by_user_id, "pins": pins}

    def list_runs(self, thread_id: str) -> tuple[bool, list[dict[str, Any]]]:
        with self.connect() as conn:
            if not conn.execute("SELECT id FROM threads WHERE id = ?", (thread_id,)).fetchone():
                return False, []
            rows = conn.execute("SELECT id, thread_id, status, created_at, created_by_user_id, pins_json FROM runs WHERE thread_id = ? ORDER BY created_at ASC", (thread_id,)).fetchall()
        return True, [{"id": r["id"], "thread_id": r["thread_id"], "status": r["status"], "created_at": r["created_at"], "created_by_user_id": r["created_by_user_id"], "pins": json.loads(r["pins_json"])} for r in rows]

    def update_run_status(self, run_id: str, status: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))
            conn.execute("COMMIT")

    def get_run_context(self, run_id: str) -> RunContext | None:
        with self.connect() as conn:
            row = conn.execute("SELECT r.id as run_id, r.thread_id, t.project_id FROM runs r JOIN threads t ON t.id = r.thread_id WHERE r.id = ?", (run_id,)).fetchone()
            return RunContext(run_id=row["run_id"], thread_id=row["thread_id"], project_id=row["project_id"]) if row else None

    def get_run_summary(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id, status, created_at, created_by_user_id, pins_json FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            agg = conn.execute("SELECT COUNT(*) as event_count, COALESCE(MAX(seq), 0) as last_seq FROM run_events WHERE run_id = ?", (run_id,)).fetchone()
        return {"run_id": row["id"], "status": row["status"], "created_at": row["created_at"], "created_by_user_id": row["created_by_user_id"], "event_count": int(agg["event_count"]), "last_seq": int(agg["last_seq"]), "pins": json.loads(row["pins_json"])}

    def get_run_last_seq(self, run_id: str) -> int | None:
        if not self.get_run_context(run_id):
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(seq), 0) as last_seq FROM run_events WHERE run_id = ?", (run_id,)).fetchone()
        return int(row["last_seq"]) if row else 0

    def get_provenance_cache(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT run_id, computed_at, last_seq, graph_json FROM provenance_cache WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["graph"] = json.loads(out["graph_json"])
        return out

    def upsert_provenance_cache(self, run_id: str, last_seq: int, graph: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO provenance_cache(run_id, computed_at, last_seq, graph_json)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  computed_at = excluded.computed_at,
                  last_seq = excluded.last_seq,
                  graph_json = excluded.graph_json
                """,
                (run_id, now, int(last_seq), json.dumps(graph)),
            )
            row = conn.execute(
                "SELECT run_id, computed_at, last_seq, graph_json FROM provenance_cache WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            conn.execute("COMMIT")
        out = dict(row) if row else {"run_id": run_id, "computed_at": now, "last_seq": int(last_seq), "graph_json": json.dumps(graph)}
        out["graph"] = json.loads(out["graph_json"])
        return out

    def append_event(self, run_id: str, event: dict[str, Any], max_events_per_run: int | None = None, max_bytes_per_run: int | None = None) -> dict[str, Any] | None:
        ctx = self.get_run_context(run_id)
        if not ctx:
            return None
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rm = conn.execute("SELECT event_count, bytes_in, bytes_out FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
            payload_bytes = len(json.dumps(event["payload"]).encode("utf-8"))
            bytes_in_inc = payload_bytes if event.get("actor") == "user" else 0
            bytes_out_inc = payload_bytes if event.get("actor") != "user" else 0
            next_events = int((rm["event_count"] if rm else 0) + 1)
            next_bytes = int((rm["bytes_in"] if rm else 0) + (rm["bytes_out"] if rm else 0) + bytes_in_inc + bytes_out_inc)
            if max_events_per_run is not None and next_events > max_events_per_run:
                conn.execute("ROLLBACK")
                raise QuotaExceededError("events_per_run", max_events_per_run, next_events)
            if max_bytes_per_run is not None and next_bytes > max_bytes_per_run:
                conn.execute("ROLLBACK")
                raise QuotaExceededError("bytes_per_run", max_bytes_per_run, next_bytes)
            seq = int(conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 as next_seq FROM run_events WHERE run_id = ?", (run_id,)).fetchone()["next_seq"])
            event_id = event.get("event_id") or str(uuid4())
            ts = event.get("ts") or datetime.now(UTC).isoformat()
            conn.execute(
                "INSERT INTO run_events(event_id, run_id, seq, ts, kind, payload_json, parent_event_id, correlation_id, actor, privacy_json, pins_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, run_id, seq, ts, event["kind"], json.dumps(event["payload"]), event.get("parent_event_id"), event.get("correlation_id"), event["actor"], json.dumps(event["privacy"]), json.dumps(event["pins"])),
            )
            if event["kind"] == "artifact_ref" and isinstance(event["payload"], dict) and event["payload"].get("artifact_id"):
                payload = event["payload"]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO artifact_links(
                      run_id, event_id, artifact_id, source_event_id, correlation_id, tool_id, tool_version, purpose, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        event_id,
                        payload["artifact_id"],
                        payload.get("source_event_id"),
                        event.get("correlation_id"),
                        payload.get("tool_id"),
                        payload.get("tool_version"),
                        payload.get("purpose"),
                        ts,
                    ),
                )
            tool_calls_inc = 1 if event["kind"] == "tool_call" else 0
            tool_errors_inc = 1 if event["kind"] == "tool_error" else 0
            artifacts_inc = 1 if event["kind"] == "artifact_ref" else 0
            conn.execute(
                """
                UPDATE run_metrics
                SET event_count = event_count + 1,
                    tool_calls = tool_calls + ?,
                    tool_errors = tool_errors + ?,
                    artifacts_count = artifacts_count + ?,
                    bytes_in = bytes_in + ?,
                    bytes_out = bytes_out + ?
                WHERE run_id = ?
                """,
                (tool_calls_inc, tool_errors_inc, artifacts_inc, bytes_in_inc, bytes_out_inc, run_id),
            )
            if event["kind"] in {"tool_result", "tool_error"}:
                payload = event["payload"] if isinstance(event["payload"], dict) else {}
                tool_id = str(payload.get("tool_id", "unknown"))
                tool_version = str(payload.get("tool_version", "unknown"))
                latency_ms = None
                if event.get("correlation_id"):
                    call_row = conn.execute(
                        "SELECT ts FROM run_events WHERE run_id = ? AND correlation_id = ? AND kind = 'tool_call' ORDER BY seq DESC LIMIT 1",
                        (run_id, event["correlation_id"]),
                    ).fetchone()
                    if call_row:
                        try:
                            latency_ms = max(0, int((datetime.fromisoformat(ts) - datetime.fromisoformat(call_row["ts"])).total_seconds() * 1000))
                        except Exception:
                            latency_ms = None
                error_code = str(payload.get("error_code")) if event["kind"] == "tool_error" else None
                conn.execute(
                    """
                    INSERT INTO tool_metrics(tool_id, tool_version, calls, errors, last_latency_ms, last_error_code, updated_at)
                    VALUES(?, ?, 1, ?, ?, ?, ?)
                    ON CONFLICT(tool_id, tool_version) DO UPDATE SET
                      calls = calls + 1,
                      errors = errors + excluded.errors,
                      last_latency_ms = excluded.last_latency_ms,
                      last_error_code = COALESCE(excluded.last_error_code, tool_metrics.last_error_code),
                      updated_at = excluded.updated_at
                    """,
                    (tool_id, tool_version, 1 if event["kind"] == "tool_error" else 0, latency_ms, error_code, datetime.now(UTC).isoformat()),
                )
                corr = str(event.get("correlation_id") or "")
                if corr:
                    call_row = conn.execute(
                        "SELECT event_id FROM run_events WHERE run_id = ? AND correlation_id = ? AND kind = 'tool_call' ORDER BY seq ASC LIMIT 1",
                        (run_id, corr),
                    ).fetchone()
                    conn.execute(
                        """
                        INSERT INTO tool_correlations(run_id, correlation_id, tool_call_event_id, tool_outcome_event_id, created_at)
                        VALUES(?, ?, ?, ?, ?)
                        ON CONFLICT(run_id, correlation_id) DO UPDATE SET
                          tool_call_event_id = COALESCE(tool_correlations.tool_call_event_id, excluded.tool_call_event_id),
                          tool_outcome_event_id = excluded.tool_outcome_event_id
                        """,
                        (run_id, corr, call_row["event_id"] if call_row else None, event_id, ts),
                    )
            if event["kind"] == "tool_call":
                corr = str(event.get("correlation_id") or "")
                if corr:
                    conn.execute(
                        """
                        INSERT INTO tool_correlations(run_id, correlation_id, tool_call_event_id, tool_outcome_event_id, created_at)
                        VALUES(?, ?, ?, NULL, ?)
                        ON CONFLICT(run_id, correlation_id) DO UPDATE SET
                          tool_call_event_id = COALESCE(tool_correlations.tool_call_event_id, excluded.tool_call_event_id)
                        """,
                        (run_id, corr, event_id, ts),
                    )
            if event["kind"] == "workflow_run_completed" or (event["kind"] == "run_status" and str(event.get("payload", {}).get("status", "")).lower() in {"complete", "completed", "denied", "failed"}):
                created_row = conn.execute("SELECT created_at FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
                if created_row and created_row["created_at"]:
                    try:
                        duration_ms = max(0, int((datetime.fromisoformat(ts) - datetime.fromisoformat(created_row["created_at"])).total_seconds() * 1000))
                        conn.execute(
                            "UPDATE run_metrics SET completed_at = COALESCE(completed_at, ?), duration_ms = COALESCE(duration_ms, ?) WHERE run_id = ?",
                            (ts, duration_ms, run_id),
                        )
                    except Exception:
                        pass
            if self._is_provenance_affecting_kind(event["kind"]):
                conn.execute("DELETE FROM provenance_cache WHERE run_id = ?", (run_id,))
            conn.execute("COMMIT")
        return {"event_id": event_id, "run_id": run_id, "thread_id": ctx.thread_id, "project_id": ctx.project_id, "seq": seq, "ts": ts, "kind": event["kind"], "payload": event["payload"], "parent_event_id": event.get("parent_event_id"), "correlation_id": event.get("correlation_id"), "actor": event["actor"], "privacy": event["privacy"], "pins": event["pins"]}

    @staticmethod
    def _is_provenance_affecting_kind(kind: str) -> bool:
        if kind in {"artifact_ref", "tool_call", "tool_result", "tool_error", "research_source_created", "research_report_created"}:
            return True
        return kind.startswith("workflow_")

    def list_events(self, run_id: str, after_seq: int, kinds: list[str] | None = None, tool_id: str | None = None, errors_only: bool = False) -> tuple[bool, list[dict[str, Any]]]:
        ctx = self.get_run_context(run_id)
        if not ctx:
            return False, []
        with self.connect() as conn:
            rows = conn.execute("SELECT event_id, run_id, seq, ts, kind, payload_json, parent_event_id, correlation_id, actor, privacy_json, pins_json FROM run_events WHERE run_id = ? AND seq > ? ORDER BY seq ASC", (run_id, after_seq)).fetchall()
        events = [{"event_id": r["event_id"], "run_id": r["run_id"], "thread_id": ctx.thread_id, "project_id": ctx.project_id, "seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "payload": json.loads(r["payload_json"]), "parent_event_id": r["parent_event_id"], "correlation_id": r["correlation_id"], "actor": r["actor"], "privacy": json.loads(r["privacy_json"]), "pins": json.loads(r["pins_json"])} for r in rows]
        if kinds:
            wanted = set(kinds)
            events = [e for e in events if e["kind"] in wanted]
        if tool_id:
            events = [e for e in events if isinstance(e.get("payload"), dict) and e["payload"].get("tool_id") == tool_id]
        if errors_only:
            events = [e for e in events if e["kind"] in {"tool_error", "system_event", "workflow_node_failed"}]
        return True, events

    def get_run_metrics(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM run_metrics WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_tool_metrics(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tool_metrics ORDER BY calls DESC, errors DESC, tool_id ASC").fetchall()
        return [dict(r) for r in rows]

    def get_system_stats(self) -> dict[str, int]:
        with self.connect() as conn:
            runs_count = int(conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"])
            tools_count = int(conn.execute("SELECT COUNT(*) AS c FROM tools").fetchone()["c"])
            events_count = int(conn.execute("SELECT COUNT(*) AS c FROM run_events").fetchone()["c"])
        db_size_bytes = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        return {"db_size_bytes": db_size_bytes, "runs_count": runs_count, "tools_count": tools_count, "events_count": events_count}

    def db_health_ok(self) -> bool:
        try:
            with self.connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def increment_counter(self, name: str, delta: int = 1) -> int:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO system_counters(name, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  value = system_counters.value + excluded.value,
                  updated_at = excluded.updated_at
                """,
                (name, int(delta), now),
            )
            row = conn.execute("SELECT value FROM system_counters WHERE name = ?", (name,)).fetchone()
            conn.execute("COMMIT")
        return int(row["value"]) if row else 0

    def set_gauge_real(self, name: str, value: float) -> float:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO system_gauges(name, value_real, value_text, updated_at)
                VALUES(?, ?, NULL, ?)
                ON CONFLICT(name) DO UPDATE SET
                  value_real = excluded.value_real,
                  value_text = NULL,
                  updated_at = excluded.updated_at
                """,
                (name, float(value), now),
            )
            conn.execute("COMMIT")
        return float(value)

    def add_gauge_real(self, name: str, delta: float) -> float:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO system_gauges(name, value_real, value_text, updated_at)
                VALUES(?, ?, NULL, ?)
                ON CONFLICT(name) DO UPDATE SET
                  value_real = COALESCE(system_gauges.value_real, 0) + excluded.value_real,
                  value_text = NULL,
                  updated_at = excluded.updated_at
                """,
                (name, float(delta), now),
            )
            row = conn.execute("SELECT value_real FROM system_gauges WHERE name = ?", (name,)).fetchone()
            conn.execute("COMMIT")
        return float(row["value_real"]) if row and row["value_real"] is not None else 0.0

    def set_gauge_text(self, name: str, value: str) -> str:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO system_gauges(name, value_real, value_text, updated_at)
                VALUES(?, NULL, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  value_real = NULL,
                  value_text = excluded.value_text,
                  updated_at = excluded.updated_at
                """,
                (name, value, now),
            )
            conn.execute("COMMIT")
        return value

    def list_system_counters(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT name, value FROM system_counters ORDER BY name ASC").fetchall()
        return {str(r["name"]): int(r["value"]) for r in rows}

    def list_system_gauges(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute("SELECT name, value_real, value_text FROM system_gauges ORDER BY name ASC").fetchall()
        out: dict[str, Any] = {}
        for r in rows:
            out[str(r["name"])] = float(r["value_real"]) if r["value_real"] is not None else r["value_text"]
        return out

    def get_max_provenance_cache_age_seconds(self) -> float | None:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(computed_at) as computed_at FROM provenance_cache").fetchone()
        if not row or not row["computed_at"]:
            return None
        try:
            return max(0.0, (datetime.now(UTC) - datetime.fromisoformat(str(row["computed_at"]))).total_seconds())
        except Exception:
            return None

    def count_active_uploads(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM artifact_uploads WHERE status != 'finalized'").fetchone()
        return int(row["c"]) if row else 0

    def upsert_artifact(self, kind: str, media_type: str, size_bytes: int, content_hash: str, storage_ref: str, title: str | None = None, created_by_user_id: str | None = None) -> dict[str, Any]:
        created_at = datetime.now(UTC).isoformat()
        artifact_id = content_hash
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR IGNORE INTO artifacts(
                  artifact_id, kind, media_type, size_bytes, content_hash, created_at, storage_ref, title, storage_path, storage_kind, etag, created_by_user_id
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'disk', ?, ?)
                """,
                (artifact_id, kind, media_type, size_bytes, content_hash, created_at, storage_ref, title, storage_ref, content_hash, created_by_user_id),
            )
            row = conn.execute("SELECT artifact_id, kind, media_type, size_bytes, content_hash, created_at, storage_ref, title, storage_path, storage_kind, etag, created_by_user_id FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
            conn.execute("COMMIT")
        return dict(row)

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT artifact_id, kind, media_type, size_bytes, content_hash, created_at, storage_ref, title, storage_path, storage_kind, etag, created_by_user_id FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
            return dict(row) if row else None

    def list_run_artifacts(self, run_id: str) -> tuple[bool, list[dict[str, Any]]]:
        if not self.get_run_context(run_id):
            return False, []
        with self.connect() as conn:
            rows = conn.execute("SELECT a.artifact_id, a.kind, a.media_type, a.size_bytes, a.content_hash, a.created_at, a.storage_ref, a.title, a.storage_path, a.storage_kind, a.etag, a.created_by_user_id FROM artifact_links l JOIN artifacts a ON a.artifact_id = l.artifact_id WHERE l.run_id = ? ORDER BY a.created_at DESC", (run_id,)).fetchall()
        return True, [dict(r) for r in rows]

    def create_artifact_link(self, run_id: str, event_id: str, artifact_id: str, *, source_event_id: str | None = None, correlation_id: str | None = None, tool_id: str | None = None, tool_version: str | None = None, purpose: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO artifact_links(
                  run_id, event_id, artifact_id, source_event_id, correlation_id, tool_id, tool_version, purpose, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, event_id, artifact_id, source_event_id, correlation_id, tool_id, tool_version, purpose, now),
            )
            row = conn.execute(
                """
                SELECT run_id, event_id, artifact_id, source_event_id, correlation_id, tool_id, tool_version, purpose, created_at
                FROM artifact_links WHERE run_id = ? AND event_id = ? AND artifact_id = ?
                """,
                (run_id, event_id, artifact_id),
            ).fetchone()
            conn.execute("COMMIT")
        return dict(row) if row else {"run_id": run_id, "event_id": event_id, "artifact_id": artifact_id}

    def list_artifact_links(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, event_id, artifact_id, source_event_id, correlation_id, tool_id, tool_version, purpose, created_at
                FROM artifact_links WHERE run_id = ?
                ORDER BY created_at ASC, event_id ASC, artifact_id ASC
                """,
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_tool_correlations(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT run_id, correlation_id, tool_call_event_id, tool_outcome_event_id, created_at FROM tool_correlations WHERE run_id = ? ORDER BY correlation_id ASC",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_research_source_link(self, run_id: str, source_id: str, correlation_id: str | None, tool_call_event_id: str | None) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO research_source_links(run_id, source_id, correlation_id, tool_call_event_id, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(run_id, source_id) DO UPDATE SET
                  correlation_id = COALESCE(excluded.correlation_id, research_source_links.correlation_id),
                  tool_call_event_id = COALESCE(excluded.tool_call_event_id, research_source_links.tool_call_event_id)
                """,
                (run_id, source_id, correlation_id, tool_call_event_id, datetime.now(UTC).isoformat()),
            )
            conn.execute("COMMIT")

    def list_research_source_links(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT run_id, source_id, correlation_id, tool_call_event_id, created_at FROM research_source_links WHERE run_id = ? ORDER BY source_id ASC",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_artifact_upload(self, artifact_id: str) -> dict[str, Any]:
        upload_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO artifact_uploads(upload_id, artifact_id, status, created_at, finalized_at, parts_json) VALUES(?, ?, 'initiated', ?, NULL, '[]')",
                (upload_id, artifact_id, now),
            )
            conn.execute("COMMIT")
        return {"upload_id": upload_id, "artifact_id": artifact_id, "status": "initiated", "created_at": now, "parts": []}

    def get_artifact_upload(self, upload_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM artifact_uploads WHERE upload_id = ?", (upload_id,)).fetchone()
        if not row:
            return None
        obj = dict(row)
        obj["parts"] = json.loads(obj["parts_json"])
        return obj

    def set_artifact_upload_parts(self, upload_id: str, parts: list[dict[str, Any]], status: str = "initiated") -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE artifact_uploads SET parts_json = ?, status = ? WHERE upload_id = ?", (json.dumps(parts), status, upload_id))
            conn.execute("COMMIT")

    def finalize_artifact_upload(self, upload_id: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE artifact_uploads SET status = 'finalized', finalized_at = ? WHERE upload_id = ?",
                (datetime.now(UTC).isoformat(), upload_id),
            )
            conn.execute("COMMIT")

    def create_pending_artifact(self, artifact_id: str, kind: str, media_type: str, title: str | None, created_by_user_id: str | None, expected_size_bytes: int | None = None, expected_hash: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                  artifact_id, kind, media_type, size_bytes, content_hash, created_at, storage_ref, title, storage_path, storage_kind, etag, created_by_user_id
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'disk', ?, ?)
                """,
                (artifact_id, kind, media_type, int(expected_size_bytes or 0), expected_hash or "", now, "", title, "", expected_hash, created_by_user_id),
            )
            conn.execute("COMMIT")
        return self.get_artifact(artifact_id) or {"artifact_id": artifact_id}

    def complete_artifact(self, artifact_id: str, size_bytes: int, content_hash: str, storage_path: str) -> dict[str, Any] | None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE artifacts
                SET size_bytes = ?, content_hash = ?, storage_ref = ?, storage_path = ?, etag = ?
                WHERE artifact_id = ?
                """,
                (size_bytes, content_hash, storage_path, storage_path, content_hash, artifact_id),
            )
            conn.execute("COMMIT")
        return self.get_artifact(artifact_id)

    def install_tool(self, manifest: dict[str, Any]) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR REPLACE INTO tools(tool_id, version, manifest_json, installed_at) VALUES(?, ?, ?, ?)", (manifest["tool_id"], manifest["version"], json.dumps(manifest), datetime.now(UTC).isoformat()))
            conn.execute("COMMIT")

    def list_tools(self) -> list[dict[str, str]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT tool_id, version FROM tools ORDER BY tool_id, version").fetchall()
        return [dict(r) for r in rows]

    def list_tool_versions(self, tool_id: str) -> list[dict[str, str]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT tool_id, version FROM tools WHERE tool_id = ? ORDER BY version", (tool_id,)).fetchall()
        return [dict(r) for r in rows]

    def uninstall_tool(self, tool_id: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM tools WHERE tool_id = ?", (tool_id,))
            conn.execute("COMMIT")

    def get_tool_manifest(self, tool_id: str, version: str | None = None) -> dict[str, Any] | None:
        with self.connect() as conn:
            if version:
                row = conn.execute("SELECT manifest_json FROM tools WHERE tool_id = ? AND version = ?", (tool_id, version)).fetchone()
            else:
                row = conn.execute("SELECT manifest_json FROM tools WHERE tool_id = ? ORDER BY version DESC LIMIT 1", (tool_id,)).fetchone()
        return json.loads(row["manifest_json"]) if row else None

    def list_grants(self, project_id: str) -> list[dict[str, str]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT project_id, scope, granted_by, granted_at FROM policy_grants WHERE project_id = ? ORDER BY scope", (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def grant_scope(self, project_id: str, scope: str, granted_by: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR REPLACE INTO policy_grants(project_id, scope, granted_by, granted_at) VALUES(?, ?, ?, ?)", (project_id, scope, granted_by, datetime.now(UTC).isoformat()))
            conn.execute("COMMIT")

    def revoke_scope(self, project_id: str, scope: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM policy_grants WHERE project_id = ? AND scope = ?", (project_id, scope))
            conn.execute("COMMIT")

    def has_scope(self, project_id: str, scope: str) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM policy_grants WHERE project_id = ? AND scope = ?", (project_id, scope)).fetchone() is not None

    def create_approval(self, run_id: str, tool_call_event_id: str, tool_id: str, tool_version: str, inputs: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        approval_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO approvals(approval_id, run_id, tool_call_event_id, tool_id, tool_version, inputs_json, correlation_id, status, created_at, decided_at, decided_by) VALUES(?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)",
                (approval_id, run_id, tool_call_event_id, tool_id, tool_version, json.dumps(inputs), correlation_id, created_at),
            )
            conn.execute("COMMIT")
        return {"approval_id": approval_id, "run_id": run_id, "tool_call_event_id": tool_call_event_id, "tool_id": tool_id, "tool_version": tool_version, "inputs": inputs, "correlation_id": correlation_id, "status": "pending", "created_at": created_at}

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["inputs"] = json.loads(out.pop("inputs_json"))
        return out

    def list_approvals(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM approvals WHERE run_id = ? ORDER BY created_at DESC", (run_id,)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["inputs"] = json.loads(item.pop("inputs_json"))
            results.append(item)
        return results

    def decide_approval(self, approval_id: str, status: str, decided_by: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                return None
            conn.execute("UPDATE approvals SET status = ?, decided_at = ?, decided_by = ? WHERE approval_id = ?", (status, now, decided_by, approval_id))
            conn.execute("COMMIT")
        return self.get_approval(approval_id)

    def has_prior_approval(self, run_id: str, tool_id: str, tool_version: str) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM approvals WHERE run_id = ? AND tool_id = ? AND tool_version = ? AND status = 'approved'", (run_id, tool_id, tool_version)).fetchone() is not None

    def create_mcp_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        server_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO mcp_servers(
                  server_id, scope_type, scope_id, name, transport, endpoint_url, stdio_cmd_json,
                  env_json, auth_state_json, created_at, status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown')
                """,
                (
                    server_id,
                    payload["scope_type"],
                    payload.get("scope_id"),
                    payload["name"],
                    payload["transport"],
                    payload.get("endpoint_url"),
                    json.dumps(payload.get("stdio_cmd")) if payload.get("stdio_cmd") is not None else None,
                    json.dumps(payload.get("env", {})),
                    json.dumps(payload.get("auth_state", {})),
                    now,
                ),
            )
            conn.execute("COMMIT")
        return self.get_mcp_server(server_id)

    def list_mcp_servers(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM mcp_servers ORDER BY created_at DESC").fetchall()
        return [self._decode_mcp_server(dict(r)) for r in rows]

    def _decode_mcp_server(self, row: dict[str, Any]) -> dict[str, Any]:
        row["env"] = json.loads(row.pop("env_json"))
        row["auth_state"] = json.loads(row.pop("auth_state_json"))
        row["stdio_cmd"] = json.loads(row["stdio_cmd_json"]) if row.get("stdio_cmd_json") else None
        return row

    def get_mcp_server(self, server_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM mcp_servers WHERE server_id = ?", (server_id,)).fetchone()
        if not row:
            return None
        return self._decode_mcp_server(dict(row))

    def update_mcp_server_health(self, server_id: str, status: str, latency_ms: int | None, protocol_version: str | None, session_id: str | None) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE mcp_servers
                SET last_health_ts = ?, last_latency_ms = ?, status = ?, protocol_version = COALESCE(?, protocol_version), session_id = COALESCE(?, session_id)
                WHERE server_id = ?
                """,
                (datetime.now(UTC).isoformat(), latency_ms, status, protocol_version, session_id, server_id),
            )
            conn.execute("COMMIT")

    def upsert_mcp_catalog(self, server_id: str, tools: list[dict[str, Any]], next_cursor: str | None = None) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO mcp_catalog(server_id, fetched_at, tools_json, next_cursor)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(server_id) DO UPDATE SET fetched_at=excluded.fetched_at, tools_json=excluded.tools_json, next_cursor=excluded.next_cursor
                """,
                (server_id, datetime.now(UTC).isoformat(), json.dumps(tools), next_cursor),
            )
            conn.execute("COMMIT")

    def get_mcp_catalog(self, server_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM mcp_catalog WHERE server_id = ?", (server_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["tools"] = json.loads(out.pop("tools_json"))
        return out

    def create_memory_item(self, item: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        memory_id = str(uuid4())
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO memory_items(memory_id, type, scope_type, scope_id, title, content, tags_json, importance, created_at, updated_at, expires_at, privacy_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    item["type"],
                    item["scope_type"],
                    item.get("scope_id"),
                    item.get("title"),
                    item["content"],
                    json.dumps(item.get("tags", [])),
                    float(item.get("importance", 0.5)),
                    now,
                    now,
                    item.get("expires_at"),
                    json.dumps(item["privacy"]),
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_provenance(memory_id, project_id, thread_id, run_id, event_id, artifact_id, source_kind)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    provenance.get("project_id"),
                    provenance.get("thread_id"),
                    provenance.get("run_id"),
                    provenance.get("event_id"),
                    provenance.get("artifact_id"),
                    provenance.get("source_kind", "manual"),
                ),
            )
            conn.execute(
                "INSERT INTO memory_fts(memory_id, title, content, tags) VALUES(?, ?, ?, ?)",
                (memory_id, item.get("title", ""), item["content"], " ".join(item.get("tags", []))),
            )
            conn.execute("COMMIT")
        return self.get_memory_item(memory_id)

    def get_memory_item(self, memory_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT m.*, p.project_id, p.thread_id, p.run_id, p.event_id, p.artifact_id, p.source_kind
                FROM memory_items m JOIN memory_provenance p ON p.memory_id = m.memory_id
                WHERE m.memory_id = ?
                """,
                (memory_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["tags"] = json.loads(item.pop("tags_json"))
        item["privacy"] = json.loads(item.pop("privacy_json"))
        return item

    def list_memory_items(self, *, scope_type: str | None = None, scope_id: str | None = None, memory_type: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if q:
                rows = conn.execute(
                    """
                    SELECT m.*, p.project_id, p.thread_id, p.run_id, p.event_id, p.artifact_id, p.source_kind
                    FROM memory_fts f
                    JOIN memory_items m ON m.memory_id = f.memory_id
                    JOIN memory_provenance p ON p.memory_id = m.memory_id
                    WHERE memory_fts MATCH ?
                    ORDER BY m.updated_at DESC
                    """,
                    (q,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.*, p.project_id, p.thread_id, p.run_id, p.event_id, p.artifact_id, p.source_kind
                    FROM memory_items m JOIN memory_provenance p ON p.memory_id = m.memory_id
                    ORDER BY m.updated_at DESC
                    """
                ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            if scope_type and item["scope_type"] != scope_type:
                continue
            if scope_id is not None and item.get("scope_id") != scope_id:
                continue
            if memory_type and item["type"] != memory_type:
                continue
            item["tags"] = json.loads(item.pop("tags_json"))
            item["privacy"] = json.loads(item.pop("privacy_json"))
            out.append(item)
        return out

    def update_memory_item(self, memory_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_memory_item(memory_id)
        if not current:
            return None
        merged = {
            "title": patch.get("title", current.get("title")),
            "content": patch.get("content", current["content"]),
            "tags": patch.get("tags", current["tags"]),
            "importance": float(patch.get("importance", current["importance"])),
            "expires_at": patch.get("expires_at", current.get("expires_at")),
            "privacy": patch.get("privacy", current["privacy"]),
        }
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE memory_items
                SET title=?, content=?, tags_json=?, importance=?, updated_at=?, expires_at=?, privacy_json=?
                WHERE memory_id=?
                """,
                (merged["title"], merged["content"], json.dumps(merged["tags"]), merged["importance"], now, merged["expires_at"], json.dumps(merged["privacy"]), memory_id),
            )
            conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            conn.execute("INSERT INTO memory_fts(memory_id, title, content, tags) VALUES(?, ?, ?, ?)", (memory_id, merged["title"] or "", merged["content"], " ".join(merged["tags"])))
            conn.execute("COMMIT")
        return self.get_memory_item(memory_id)

    def delete_memory_item(self, memory_id: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            deleted = conn.execute("DELETE FROM memory_items WHERE memory_id = ?", (memory_id,)).rowcount
            conn.execute("DELETE FROM memory_provenance WHERE memory_id = ?", (memory_id,))
            conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            conn.execute("COMMIT")
        return bool(deleted)

    def create_research_source(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO research_sources(source_id, run_id, title, url, snippet, retrieved_at, correlation_id, tool_id, tool_version, artifact_id)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source_id"],
                    row["run_id"],
                    row["title"],
                    row["url"],
                    row.get("snippet"),
                    row["retrieved_at"],
                    row["correlation_id"],
                    row["tool_id"],
                    row["tool_version"],
                    row.get("artifact_id"),
                ),
            )
            conn.execute("COMMIT")
        return row

    def list_research_sources(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM research_sources WHERE run_id = ? ORDER BY retrieved_at ASC", (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def create_workflow(self, workflow_id: str, name: str, version: str, graph_artifact_id: str) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO workflows(workflow_id, name, version, graph_artifact_id, created_at) VALUES(?, ?, ?, ?, ?)", (workflow_id, name, version, graph_artifact_id, now))
            conn.execute("COMMIT")
        return {"workflow_id": workflow_id, "name": name, "version": version, "graph_artifact_id": graph_artifact_id, "created_at": now}

    def list_workflows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM workflows ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_workflow(self, workflow_id: str, version: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE workflow_id = ? AND version = ?", (workflow_id, version)).fetchone()
        return dict(row) if row else None

    def create_workflow_run(self, workflow_id: str, run_id: str, inputs: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        wid = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO workflow_runs(workflow_run_id, workflow_id, run_id, status, inputs_json, created_at, completed_at, state_json) VALUES(?, ?, ?, 'running', ?, ?, NULL, ?)",
                (wid, workflow_id, run_id, json.dumps(inputs), now, json.dumps(state or {})),
            )
            conn.execute("COMMIT")
        return {"workflow_run_id": wid, "workflow_id": workflow_id, "run_id": run_id, "status": "running", "inputs": inputs, "created_at": now, "completed_at": None, "state": state or {}}

    def update_workflow_run(self, workflow_run_id: str, *, status: str | None = None, state: dict[str, Any] | None = None, completed: bool = False) -> dict[str, Any] | None:
        row = self.get_workflow_run(workflow_run_id)
        if not row:
            return None
        next_status = status or row["status"]
        next_state = state if state is not None else row["state"]
        completed_at = datetime.now(UTC).isoformat() if completed else row.get("completed_at")
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE workflow_runs SET status = ?, state_json = ?, completed_at = ? WHERE workflow_run_id = ?", (next_status, json.dumps(next_state), completed_at, workflow_run_id))
            conn.execute("COMMIT")
        return self.get_workflow_run(workflow_run_id)

    def get_workflow_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workflow_runs WHERE workflow_run_id = ?", (workflow_run_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["inputs"] = json.loads(out.pop("inputs_json"))
        out["state"] = json.loads(out.pop("state_json"))
        return out

    def list_workflow_runs(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ? ORDER BY created_at DESC", (run_id,)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["inputs"] = json.loads(item.pop("inputs_json"))
            item["state"] = json.loads(item.pop("state_json"))
            out.append(item)
        return out

    def add_registry_key(self, public_key_id: str, public_key_base64: str) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR REPLACE INTO registry_keys(public_key_id, public_key_base64, added_at) VALUES(?, ?, ?)",
                (public_key_id, public_key_base64, now),
            )
            conn.execute("COMMIT")
        return {"public_key_id": public_key_id, "public_key_base64": public_key_base64, "added_at": now}

    def get_registry_key(self, public_key_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM registry_keys WHERE public_key_id = ?", (public_key_id,)).fetchone()
        return dict(row) if row else None

    def upsert_registry_package(self, package: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        checks = package.get("checks", {"schema_ok": False, "signature_ok": False, "static_ok": False, "contract_tests_ok": False, "last_checked_at": None})
        moderation = package.get("moderation", {"reports_count": 0, "last_report_at": None})
        status = package.get("status", "active")
        updated_by = package.get("updated_by", "system")
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO registry_packages(
                  package_id, version, tier, manifest_json, files_json, signature_json, metadata_json, status, checks_json, moderation_json, created_at, updated_at, updated_by
                ) VALUES(
                  ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT status FROM registry_packages WHERE package_id=? AND version=?), ?),
                  COALESCE((SELECT checks_json FROM registry_packages WHERE package_id=? AND version=?), ?),
                  COALESCE((SELECT moderation_json FROM registry_packages WHERE package_id=? AND version=?), ?),
                  ?, ?, ?
                )
                """,
                (
                    package["package_id"],
                    package["version"],
                    package["metadata"]["tier"],
                    json.dumps(package["manifest"]),
                    json.dumps(package.get("files", [])),
                    json.dumps(package["signature"]),
                    json.dumps(package["metadata"]),
                    package["package_id"],
                    package["version"],
                    status,
                    package["package_id"],
                    package["version"],
                    json.dumps(checks),
                    package["package_id"],
                    package["version"],
                    json.dumps(moderation),
                    package["created_at"],
                    now,
                    updated_by,
                ),
            )
            conn.execute("COMMIT")
        return self.get_registry_package(package["package_id"], package["version"])

    def list_registry_packages(self, tier: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT package_id, version, tier, status, created_at, metadata_json, checks_json, moderation_json FROM registry_packages WHERE 1=1"
        args: list[Any] = []
        if tier:
            q += " AND tier = ?"
            args.append(tier)
        if status:
            q += " AND status = ?"
            args.append(status)
        q += " ORDER BY package_id ASC, version DESC"
        with self.connect() as conn:
            rows = conn.execute(q, tuple(args)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            item["checks"] = json.loads(item.pop("checks_json"))
            item["moderation"] = json.loads(item.pop("moderation_json"))
            out.append(item)
        return out

    def list_registry_package_versions(self, package_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT package_id, version, tier, status, created_at, metadata_json, checks_json, moderation_json FROM registry_packages WHERE package_id = ? ORDER BY version DESC",
                (package_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            item["checks"] = json.loads(item.pop("checks_json"))
            item["moderation"] = json.loads(item.pop("moderation_json"))
            out.append(item)
        return out

    def get_registry_package(self, package_id: str, version: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM registry_packages WHERE package_id = ? AND version = ?", (package_id, version)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["manifest"] = json.loads(out.pop("manifest_json"))
        out["files"] = json.loads(out.pop("files_json"))
        out["signature"] = json.loads(out.pop("signature_json"))
        out["metadata"] = json.loads(out.pop("metadata_json"))
        out["checks"] = json.loads(out.pop("checks_json"))
        out["moderation"] = json.loads(out.pop("moderation_json"))
        return out

    def set_registry_package_status(self, package_id: str, version: str, status: str, updated_by: str, checks: dict[str, Any] | None = None) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if checks is None:
                changed = conn.execute(
                    "UPDATE registry_packages SET status = ?, updated_at = ?, updated_by = ? WHERE package_id = ? AND version = ?",
                    (status, datetime.now(UTC).isoformat(), updated_by, package_id, version),
                ).rowcount
            else:
                changed = conn.execute(
                    "UPDATE registry_packages SET status = ?, checks_json = ?, updated_at = ?, updated_by = ? WHERE package_id = ? AND version = ?",
                    (status, json.dumps(checks), datetime.now(UTC).isoformat(), updated_by, package_id, version),
                ).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def create_registry_report(self, package_id: str, version: str, reporter: str, reason_code: str, details: str | None) -> dict[str, Any]:
        report_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO registry_reports(report_id, package_id, version, reporter, reason_code, details, created_at, status) VALUES(?, ?, ?, ?, ?, ?, ?, 'open')",
                (report_id, package_id, version, reporter, reason_code, details, now),
            ).rowcount
            row = conn.execute("SELECT moderation_json FROM registry_packages WHERE package_id = ? AND version = ?", (package_id, version)).fetchone()
            moderation = json.loads(row["moderation_json"]) if row else {"reports_count": 0, "last_report_at": None}
            moderation["reports_count"] = int(moderation.get("reports_count", 0)) + 1
            moderation["last_report_at"] = now
            conn.execute(
                "UPDATE registry_packages SET moderation_json = ?, updated_at = ?, updated_by = ? WHERE package_id = ? AND version = ?",
                (json.dumps(moderation), now, reporter, package_id, version),
            )
            conn.execute("COMMIT")
        return {"report_id": report_id, "package_id": package_id, "version": version, "reporter": reporter, "reason_code": reason_code, "details": details, "created_at": now, "status": "open"}

    def list_registry_reports(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status:
                rows = conn.execute("SELECT * FROM registry_reports WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM registry_reports ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_registry_report_status(self, report_id: str, status: str) -> bool:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            changed = conn.execute("UPDATE registry_reports SET status = ? WHERE report_id = ?", (status, report_id)).rowcount
            conn.execute("COMMIT")
        return bool(changed)

    def create_collection(self, name: str, description: str | None, packages: list[dict[str, str]]) -> dict[str, Any]:
        collection_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO collections(collection_id, name, description, packages_json, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
                (collection_id, name, description, json.dumps(packages), now, now),
            )
            conn.execute("COMMIT")
        return {"collection_id": collection_id, "name": name, "description": description, "packages": packages, "created_at": now, "updated_at": now}

    def list_collections(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM collections ORDER BY created_at DESC").fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["packages"] = json.loads(item.pop("packages_json"))
            out.append(item)
        return out

    def set_project_tool_pin(self, project_id: str, tool_id: str, tool_version: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR REPLACE INTO project_tool_pins(project_id, tool_id, tool_version, pinned_at) VALUES(?, ?, ?, ?)",
                (project_id, tool_id, tool_version, datetime.now(UTC).isoformat()),
            )
            conn.execute("COMMIT")

    def get_project_tool_pin(self, project_id: str, tool_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT project_id, tool_id, tool_version, pinned_at FROM project_tool_pins WHERE project_id = ? AND tool_id = ?",
                (project_id, tool_id),
            ).fetchone()
        return dict(row) if row else None

    def list_project_tool_pins(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT project_id, tool_id, tool_version, pinned_at FROM project_tool_pins WHERE project_id = ? ORDER BY tool_id",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def remove_project_tool_pin(self, project_id: str, tool_id: str) -> None:
        with self._retrying_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM project_tool_pins WHERE project_id = ? AND tool_id = ?", (project_id, tool_id))
            conn.execute("COMMIT")


def hash_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
