# V2 Database Schema Specification

## Design Principles
- **GUID primary keys** everywhere (UUID on Postgres, CHAR(36) on SQLite)
- **JSONB** for flexible/nested data (native on Postgres, JSON on SQLite)
- **`created_at` / `updated_at`** on all tables with server defaults
- **Soft deletes** via `deleted_at` where appropriate
- **Async SQLAlchemy 2.0** with asyncpg (Postgres) / aiosqlite (SQLite)
- **Alembic** for all schema migrations

---

## Tables (18)

### 1. users
Merges V1 `auth_identities` + `users`.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| username | CIText | UNIQUE NOT NULL |
| display_name | TEXT | NOT NULL |
| avatar_url | TEXT | NULL |
| password_hash | TEXT | NULL |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| updated_at | TIMESTAMP(tz) | NOT NULL, server_default=now(), onupdate=now() |
| deleted_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_users_username` UNIQUE on username

### 2. sessions

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| user_id | GUID | FK→users NOT NULL |
| csrf_secret | TEXT | NOT NULL |
| device_fingerprint | TEXT | NULL |
| expires_at | TIMESTAMP(tz) | NOT NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Indexes**: `ix_sessions_user_id`, `ix_sessions_expires_at`

### 3. api_keys

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| user_id | GUID | FK→users NOT NULL |
| prefix | TEXT | NOT NULL (first 8 chars) |
| key_hash | TEXT | NOT NULL |
| name | TEXT | NOT NULL |
| scopes | JSONB | NOT NULL DEFAULT '[]' |
| last_used_at | TIMESTAMP(tz) | NULL |
| expires_at | TIMESTAMP(tz) | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| revoked_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_api_keys_prefix`, `ix_api_keys_user_id`

### 4. projects

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| name | TEXT | NOT NULL |
| description | TEXT | NULL |
| created_by | GUID | FK→users NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| updated_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| archived_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_projects_created_by`

### 5. project_members

| Column | Type | Constraints |
|--------|------|-------------|
| project_id | GUID | FK→projects, PK |
| user_id | GUID | FK→users, PK |
| role | TEXT | NOT NULL (owner/admin/member/viewer) |
| added_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

### 6. threads

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| project_id | GUID | FK→projects NOT NULL |
| title | TEXT | NOT NULL |
| pinned | BOOLEAN | NOT NULL DEFAULT FALSE |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| updated_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| archived_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_threads_project_id`, `ix_threads_project_created` on (project_id, created_at DESC)

### 7. messages
Merges V1 run_events that represent user/assistant messages into a first-class entity.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| thread_id | GUID | FK→threads NOT NULL |
| run_id | GUID | FK→runs NULL |
| role | TEXT | NOT NULL (user/assistant/system/tool) |
| content | TEXT | NOT NULL |
| attachments | JSONB | NOT NULL DEFAULT '[]' |
| metadata | JSONB | NOT NULL DEFAULT '{}' |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Indexes**: `ix_messages_thread_id`, `ix_messages_thread_created` on (thread_id, created_at)

### 8. runs
Extends existing V2 model.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| thread_id | GUID | FK→threads NOT NULL |
| status | TEXT | NOT NULL (active/completed/failed/cancelled) |
| model_config | JSONB | NOT NULL DEFAULT '{}' |
| created_by | GUID | FK→users NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| completed_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_runs_thread_id`, `ix_runs_status`

### 9. run_events
Extends existing V2 model.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| run_id | GUID | FK→runs NOT NULL |
| seq | INTEGER | NOT NULL |
| kind | TEXT | NOT NULL |
| payload | JSONB | NOT NULL |
| actor | TEXT | NOT NULL |
| parent_event_id | GUID | NULL |
| correlation_id | TEXT | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Constraints**: `UNIQUE(run_id, seq)` — critical invariant
**Indexes**: `ix_run_events_run_seq` on (run_id, seq), `ix_run_events_correlation`

### 10. tool_calls
Normalizes V1 tool_correlations + approvals.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| run_id | GUID | FK→runs NOT NULL |
| tool_id | TEXT | NOT NULL |
| tool_version | TEXT | NULL |
| inputs | JSONB | NOT NULL |
| output | JSONB | NULL |
| status | TEXT | NOT NULL (pending/approved/denied/completed/errored) |
| call_event_id | GUID | FK→run_events NULL |
| result_event_id | GUID | FK→run_events NULL |
| latency_ms | INTEGER | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| completed_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_tool_calls_run_id`, `ix_tool_calls_tool_id`

### 11. artifacts
Merges V1 artifacts + artifact_links.

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| run_id | GUID | FK→runs NULL |
| kind | TEXT | NOT NULL |
| media_type | TEXT | NOT NULL |
| title | TEXT | NULL |
| size_bytes | INTEGER | NOT NULL |
| content_hash | TEXT | NOT NULL |
| storage_path | TEXT | NOT NULL |
| storage_kind | TEXT | NOT NULL DEFAULT 'disk' |
| metadata | JSONB | NOT NULL DEFAULT '{}' |
| created_by | GUID | FK→users NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Indexes**: `ix_artifacts_run_id`, `ix_artifacts_content_hash`

### 12. workflow_templates

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| name | TEXT | NOT NULL |
| version | TEXT | NOT NULL |
| graph | JSONB | NOT NULL |
| description | TEXT | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Constraints**: `UNIQUE(name, version)`

### 13. workflow_runs

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| template_id | GUID | FK→workflow_templates NOT NULL |
| run_id | GUID | FK→runs NOT NULL |
| status | TEXT | NOT NULL |
| inputs | JSONB | NOT NULL |
| state | JSONB | NOT NULL DEFAULT '{}' |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| completed_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_workflow_runs_run_id`

### 14. workflow_steps

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| workflow_run_id | GUID | FK→workflow_runs NOT NULL |
| step_name | TEXT | NOT NULL |
| status | TEXT | NOT NULL |
| inputs | JSONB | NOT NULL DEFAULT '{}' |
| outputs | JSONB | NULL |
| started_at | TIMESTAMP(tz) | NULL |
| completed_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_workflow_steps_run_id`

### 15. memory_entries

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| type | TEXT | NOT NULL |
| scope_type | TEXT | NOT NULL |
| scope_id | GUID | NULL |
| title | TEXT | NULL |
| content | TEXT | NOT NULL |
| tags | JSONB | NOT NULL DEFAULT '[]' |
| importance | FLOAT | NOT NULL DEFAULT 0.5 |
| source | JSONB | NOT NULL DEFAULT '{}' |
| privacy | JSONB | NOT NULL DEFAULT '{}' |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| updated_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |
| expires_at | TIMESTAMP(tz) | NULL |

**Indexes**: `ix_memory_scope` on (scope_type, scope_id)

### 16. notifications

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| user_id | GUID | FK→users NOT NULL |
| kind | TEXT | NOT NULL |
| payload | JSONB | NOT NULL |
| project_id | GUID | FK→projects NULL |
| run_id | GUID | FK→runs NULL |
| read_at | TIMESTAMP(tz) | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Indexes**: `ix_notifications_user_unread` on (user_id, read_at, created_at DESC)

### 17. audit_log

| Column | Type | Constraints |
|--------|------|-------------|
| id | GUID | PK |
| user_id | GUID | FK→users NULL |
| action | TEXT | NOT NULL |
| resource_type | TEXT | NOT NULL |
| resource_id | TEXT | NULL |
| details | JSONB | NOT NULL DEFAULT '{}' |
| ip_address | TEXT | NULL |
| created_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

**Indexes**: `ix_audit_log_user_id`, `ix_audit_log_action`, `ix_audit_log_created_at`

### 18. settings

| Column | Type | Constraints |
|--------|------|-------------|
| key | TEXT | PK |
| value | JSONB | NOT NULL |
| updated_at | TIMESTAMP(tz) | NOT NULL, server_default=now() |

---

## V1 Tables NOT Carried Over
These V1 tables are consolidated or dropped:

| V1 Table | Disposition |
|----------|-------------|
| `auth_identities` | Merged into `users` |
| `message_attachments` | Merged into `messages.attachments` JSONB |
| `artifact_links` | Merged into `artifacts.run_id` + `metadata` |
| `artifact_uploads` | Dropped (new upload API uses direct writes) |
| `tool_correlations` | Merged into `tool_calls` |
| `approvals` | Merged into `tool_calls.status` |
| `memory_provenance` | Merged into `memory_entries.source` JSONB |
| `memory_fts` | Use Postgres `tsvector` or pg_trgm instead |
| `notification_state` | Computed from `notifications.read_at` |
| `user_project_state` | Computed from activity queries |
| `registry_*` (5 tables) | Deferred — registry is a separate concern |
| `mcp_*` (2 tables) | Deferred — MCP is a separate concern |
| `system_counters/gauges` | Replaced by Prometheus metrics |
| `idempotency_keys` | Handled at API layer |
| `provenance_cache` | Computed on demand |
| `run_metrics/tool_metrics` | Derived from run_events + tool_calls |
| `policy_grants` | Moved to project-level JSONB config |
| `research_*` (2 tables) | Merged into artifacts + tool_calls |
| `collections` | Deferred with registry |

---

## Query Hot Paths

| Query | Tables | Index Used |
|-------|--------|------------|
| List threads for project | threads | ix_threads_project_created |
| List messages in thread | messages | ix_messages_thread_created |
| Stream run events | run_events | UNIQUE(run_id, seq) |
| Append event (next seq) | run_events | UNIQUE(run_id, seq) for MAX+1 |
| Get user by username | users | ix_users_username |
| List notifications | notifications | ix_notifications_user_unread |
| List artifacts for run | artifacts | ix_artifacts_run_id |

---

## ERD (Simplified)

```
users ──┬── sessions
        ├── api_keys
        ├── project_members ── projects ── threads ── messages
        │                                     └── runs ── run_events
        │                                            ├── tool_calls
        │                                            ├── artifacts
        │                                            └── workflow_runs ── workflow_steps
        ├── notifications                                  └── workflow_templates
        └── audit_log

memory_entries (standalone, scope-based)
settings (standalone KV)
```
