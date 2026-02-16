# V1 Database Inventory

## Overview
- **Engine**: raw `sqlite3` (no ORM)
- **File**: `omni-backend/omni_backend/db.py` (~2235 lines)
- **Tables**: 39 + 1 FTS virtual table
- **Schema evolution**: `ALTER TABLE` in `init_db()` (no migration framework)
- **Connection**: `isolation_level=None`, `PRAGMA foreign_keys = ON`, retry on lock

---

## Tables

### Core Domain

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `projects` | `id TEXT` | name, created_at | |
| `threads` | `id TEXT` | project_id FK, title, created_at | |
| `runs` | `id TEXT` | thread_id FK, status, pins_json, created_by_user_id | |
| `run_events` | `event_id TEXT` | run_id FK, seq INT, kind, payload_json, actor, privacy_json, pins_json | `UNIQUE(run_id, seq)` — critical invariant |

### Artifacts

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `artifacts` | `artifact_id TEXT` | kind, media_type, size_bytes, content_hash, storage_ref, storage_path, storage_kind, etag, created_by_user_id | Multi-part upload support |
| `artifact_links` | `(run_id, event_id, artifact_id)` | source_event_id, correlation_id, tool_id, tool_version, purpose | M2M join |
| `artifact_uploads` | `upload_id TEXT` | artifact_id, status, parts_json | Chunked upload tracking |

### Tools & Correlations

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `tools` | `(tool_id, version)` | manifest_json, installed_at | |
| `tool_correlations` | `(run_id, correlation_id)` | tool_call_event_id, tool_outcome_event_id | Links call→result events |
| `policy_grants` | `(project_id, scope)` | granted_by, granted_at | Per-project tool permissions |
| `approvals` | `approval_id TEXT` | run_id, tool_call_event_id, tool_id, inputs_json, status | Human-in-the-loop |
| `project_tool_pins` | `(project_id, tool_id)` | tool_version, pinned_at | |

### Auth & Users

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `auth_identities` | `user_id TEXT` | username UNIQUE, password_hash | Argon2id hashes |
| `sessions` | `session_id TEXT` | user_id, expires_at, csrf_secret | HTTP-only cookies |
| `users` | `user_id TEXT` | display_name, avatar_url, created_at | Profile data |
| `project_members` | `(project_id, user_id)` | role, added_at | |

### Social & Activity

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `comments` | `comment_id TEXT` | project_id, run_id, thread_id, target_type, target_id, author_id, body | Soft-deletable |
| `activity` | `activity_id TEXT` | project_id, kind, ref_type, ref_id, actor_id, activity_seq | Auto-increment seq via ALTER |
| `user_project_state` | `(user_id, project_id)` | last_seen_activity_seq | Unread tracking |
| `notifications` | `notification_id TEXT` | user_id, project_id, kind, payload_json, read_at, activity_seq | |
| `notification_state` | `user_id TEXT` | last_seen_notification_seq | |

### Registry

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `registry_packages` | `(package_id, version)` | tier, manifest_json, files_json, signature_json, status, checks_json | Tool marketplace |
| `registry_keys` | `public_key_id TEXT` | public_key_base64 | Signature verification |
| `registry_reports` | `report_id TEXT` | package_id, version, reporter, reason_code, status | Abuse reports |
| `collections` | `collection_id TEXT` | name, packages_json | Curated tool lists |

### MCP (Model Context Protocol)

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `mcp_servers` | `server_id TEXT` | scope_type, name, transport, endpoint_url, stdio_cmd_json, status | |
| `mcp_catalog` | `server_id TEXT` | tools_json, next_cursor | Cached tool listings |

### Research & Provenance

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `research_sources` | `source_id TEXT` | run_id, title, url, snippet, correlation_id, tool_id | |
| `research_source_links` | `(run_id, source_id)` | correlation_id, tool_call_event_id | |
| `provenance_cache` | `run_id TEXT` | graph_json, last_seq | Computed provenance DAG |

### Memory

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `memory_items` | `memory_id TEXT` | type, scope_type, scope_id, content, tags_json, importance, privacy_json | |
| `memory_provenance` | `memory_id TEXT` | project_id, thread_id, run_id, event_id, source_kind | |
| `memory_fts` | (FTS5 virtual) | memory_id, title, content, tags | Full-text search |

### Workflows

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `workflows` | `workflow_id TEXT` | name, version, graph_artifact_id | |
| `workflow_runs` | `workflow_run_id TEXT` | workflow_id, run_id, status, inputs_json, state_json | |

### Metrics & System

| Table | PK | Key Columns | Notes |
|-------|------|-------------|-------|
| `run_metrics` | `run_id TEXT` | duration_ms, event_count, tool_calls, bytes_in, bytes_out | |
| `tool_metrics` | `(tool_id, tool_version)` | calls, errors, last_latency_ms | |
| `system_counters` | `name TEXT` | value INT | Global counters |
| `system_gauges` | `name TEXT` | value_real, value_text | Global gauges |
| `idempotency_keys` | `key TEXT` | user_id, endpoint, response_json | Request dedup |

---

## Indexes

| Index | Table | Columns |
|-------|-------|---------|
| `idx_run_events_run_seq` | run_events | (run_id, seq) |
| `idx_run_events_correlation_id` | run_events | (correlation_id) |
| `idx_notifications_user_read_id` | notifications | (user_id, read_at, notification_id) |
| `idx_notifications_user_created_desc` | notifications | (user_id, created_at DESC) |
| `idx_notifications_user_activity_seq` | notifications | (user_id, activity_seq) |

---

## Schema Evolution (ALTER TABLE in init_db)
- `activity` → ADD `activity_seq INTEGER`
- `runs` → ADD `created_by_user_id TEXT`
- `artifact_links` → ADD `source_event_id`, `correlation_id`, `tool_id`, `tool_version`, `purpose`, `created_at`
- `artifacts` → ADD `storage_path`, `storage_kind`, `etag`, `created_by_user_id`

---

## API Endpoints (93 total)

### Auth (6)
- POST /v1/auth/login, /register, /logout, /rotate
- GET /v1/auth/csrf
- GET /v1/me, PATCH /v1/me

### Projects (3)
- POST /v1/projects, GET /v1/projects
- GET/POST/PATCH/DELETE /v1/projects/{id}/members

### Threads & Runs (5)
- POST/GET /v1/projects/{id}/threads
- POST/GET /v1/threads/{id}/runs
- GET /v1/runs/{id}/summary, /metrics

### Events & Streaming (4)
- GET/POST /v1/runs/{id}/events
- GET /v1/runs/{id}/events:stream, /events/stream

### Artifacts (7)
- POST /v1/artifacts, /artifacts/init
- PUT /v1/artifacts/{id}/parts/{n}
- POST /v1/artifacts/{id}/finalize
- GET /v1/artifacts/{id}, /download
- GET/POST /v1/runs/{id}/artifacts

### Tools & Registry (18)
- GET/POST tools, install, invoke, approve/deny
- Registry: keys, packages CRUD, import, yank, report, verify, status, mirror
- Collections, project pins

### MCP (8)
- CRUD servers, health, catalog, tools, try_tool, pin_tool

### Social (11)
- Comments CRUD, activity stream, unread, mark_seen
- Notifications list, unread_count, state, mark_read, stream

### Memory (7)
- CRUD memory items, search, promote

### Research & Provenance (5)
- Research start, sources, report
- Provenance graph, why

### Workflows (6)
- CRUD workflows, start, list/get runs, resume

### System (4)
- Health, stats, config, agent_stub
