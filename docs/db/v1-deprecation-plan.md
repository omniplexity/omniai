# V1 Database Deprecation Plan

## Overview
Phased migration from V1 (raw SQLite in `db.py`) to V2 (async SQLAlchemy + Postgres).
V1 endpoints continue working throughout; V2 endpoints light up incrementally.

---

## Cutover Strategy

### Stage 1: Dual-Write (Current)
- V1 remains primary — all 93 endpoints operate on V1 SQLite
- V2 endpoints (`/v2/*`) operate on V2 Postgres independently
- `OMNI_V2_DB_ACTIVE=false` (default)
- Data migration script available for bulk transfer

### Stage 2: V2 Active
- Set `OMNI_V2_DB_ACTIVE=true`
- V2 endpoints switch to V2 Postgres via repository layer
- V1 endpoints still operational (unchanged)
- Run data migration: `python -m omni_backend.v2.migrations.data.migrate_v1_to_v2`
- Verify: compare row counts, spot-check FK integrity

### Stage 3: V1 Read-Only
- V1 `Database` class switched to read-only mode (remove writes)
- All new writes go through V2 endpoints
- V1 GET endpoints still work for backwards compatibility
- Add `Deprecation: true` header to V1 responses

### Stage 4: V1 Removal
- Remove V1 endpoints from `app.py`
- Remove `db.py` (V1 Database class)
- Remove V1 middleware (`RequestSizeLimitMiddleware`, `SessionBaselineMiddleware`)
- V2 sub-app becomes the main app
- Archive V1 SQLite file as backup

---

## Endpoint Migration Map

| V1 Endpoint | V2 Equivalent | Status |
|-------------|---------------|--------|
| POST /v1/auth/login | POST /v2/auth/login | Planned |
| GET /v1/projects | GET /v2/projects | Planned |
| POST /v1/projects | POST /v2/projects | Planned |
| GET /v1/projects/{id}/threads | GET /v2/projects/{id}/threads | Planned |
| POST /v1/threads/{id}/runs | POST /v2/runs | **Done** |
| GET /v1/runs/{id}/events | GET /v2/runs/{id}/events | **Done** |
| GET /v1/runs/{id}/events/stream | GET /v2/runs/{id}/events/stream | **Done** |
| POST /v1/runs/{id}/events | POST /v2/runs/{id}/events | **Done** |
| GET /v2/health | GET /v2/health | **Done** |

---

## V1 Tables → V2 Tables Mapping

| V1 Table(s) | V2 Table | Migration |
|-------------|----------|-----------|
| auth_identities + users | users | Merge on user_id |
| sessions | sessions | Direct copy |
| projects | projects | Direct copy |
| project_members | project_members | Direct copy |
| threads | threads | Direct copy |
| runs | runs | pins_json → model_config JSONB |
| run_events | run_events | payload_json → payload JSONB |
| tool_correlations + approvals | tool_calls | Normalize |
| artifacts + artifact_links | artifacts | Merge, add run_id |
| workflows | workflow_templates | Rename, graph as JSONB |
| workflow_runs | workflow_runs | Direct copy |
| memory_items + memory_provenance | memory_entries | Merge provenance into source JSONB |
| notifications | notifications | Direct copy |
| comments, activity, etc. | audit_log | Consolidate into audit events |

---

## V1 Tables Dropped (Not Migrated)

| Table | Reason |
|-------|--------|
| registry_* (5 tables) | Separate concern, deferred to registry service |
| mcp_* (2 tables) | Separate concern, deferred to MCP service |
| system_counters/gauges | Replaced by Prometheus metrics |
| idempotency_keys | Handled at API layer |
| provenance_cache | Computed on demand |
| run_metrics/tool_metrics | Derived from run_events + tool_calls |
| policy_grants | Moved to project-level config |
| research_sources/links | Merged into artifacts + tool_calls |
| collections | Deferred with registry |
| memory_fts | Replaced by Postgres tsvector/pg_trgm |
| notification_state | Computed from notifications.read_at |
| user_project_state | Computed from activity queries |
| artifact_uploads | New upload API uses direct writes |

---

## Rollback Plan
- If V2 issues found: set `OMNI_V2_DB_ACTIVE=false` to revert to V1
- V1 SQLite file preserved as backup indefinitely
- No destructive changes until Stage 4 (which requires explicit decision)

---

## Feature Flag Rollout

```
# Stage 1 (current)
OMNI_V2_DB_ACTIVE=false

# Stage 2 (after data migration verified)
OMNI_V2_DB_ACTIVE=true

# Stage 3 (after V2 endpoints cover all needed functionality)
# Add deprecation headers to V1 via middleware

# Stage 4 (after monitoring confirms no V1 usage)
# Remove V1 code paths
```
