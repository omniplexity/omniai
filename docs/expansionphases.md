# OmniAI v1 Phased Plan (Agent-driven, Flag-gated, Contract-stable)

## Goals
- Keep **primary UX always shippable**: boot → login → chat → stream → cancel → retry.
- Make all new capability **additive** and **safe to disable** (feature flags + agent boundaries).
- Maintain **contract stability** (OpenAPI + JSON schemas + stable error codes).
- Enforce **security invariants** (static SPA, backend-only secrets, strict CORS/CSRF/cookies, request limits).
- Keep the system **scalable-by-design** (swap in Redis for distributed limits; provider abstraction). :contentReference[oaicite:0]{index=0}

## Non-negotiables (v1)
- Frontend is **static** (GitHub Pages); no secrets; never calls providers directly. :contentReference[oaicite:1]{index=1}
- Backend is the sole integration point (provider proxy, auth, storage, rate limiting). :contentReference[oaicite:2]{index=2}
- Agents define boundaries (Provider/Auth/Conversation/Tool/etc.). :contentReference[oaicite:3]{index=3}
- v1 feature scope is gated and incremental (workspace, memory, knowledge, workflows, etc.). :contentReference[oaicite:4]{index=4}

---

# Architecture anchors

## API lanes
1. **UI lane**: `/v1/*`
   - Cookie session + CSRF, CORS **on** (allowlist), strict Origin handling.
2. **Public lane**: `/v1/public/*`
   - Bearer tokens + scopes, CORS **off**, separate middleware.
3. **Dev/Admin lane**: `/v1/dev/*`
   - Cookie + CSRF + role requirements.
4. **Legacy lane**: `/api/*` (deprecated only)
   - No new routes; keep compat with explicit deprecation notes in contracts. :contentReference[oaicite:5]{index=5}

## Agents (hard boundaries)
- **Provider Agent**: `list_models()`, `chat_stream()`, `chat_once()`, `healthcheck()`, `capabilities()`. :contentReference[oaicite:6]{index=6}
- **Auth Agent**: invite-only, sessions, CSRF, audit log on auth events. :contentReference[oaicite:7]{index=7}
- **Conversation Agent**: threads/messages CRUD, rename/delete, branching hooks, pin/context blocks. :contentReference[oaicite:8]{index=8}
- **Tool/Knowledge/Memory/Voice/Admin/Planner Agents**: behind explicit interfaces; no cross-cutting “helpers” that bypass boundaries. :contentReference[oaicite:9]{index=9}

---

# Contract rules (v1 freeze principles)

## Contract sources of truth
- `contracts/` contains:
  - OpenAPI (canonical `/v1/*`)
  - JSON schema definitions (requests/responses)
  - Error code registry + stable response envelope

## Response envelopes
- **Success**: normal JSON objects per route schema.
- **Error**: single normalized envelope everywhere:
  - `error.code` (stable string)
  - `error.message` (user-safe)
  - `error.detail` (optional, user-safe)
  - `request_id` (always present)

## Error code conventions
- `E_AUTH_*`: auth/session/csrf issues
- `E_CAPABILITY_DISABLED`: feature flag off or capability not enabled
- `E_RATE_LIMITED`: rate limits / concurrency slots
- `E_PROVIDER_*`: provider timeouts, model not found, upstream errors
- `E_VALIDATION`: request schema violations
- `E_INTERNAL`: unknown failure (no stack traces to clients)

---

# Feature flags (server authoritative)
- Server returns flags in `GET /v1/meta`; frontend treats meta as source-of-truth.
- Frontend may also load static defaults from `runtime-config.json` and **merge**, but backend decides enforcement.
- Disabling flags must result in `E_CAPABILITY_DISABLED` and UI hiding routes/panels.

---

# Gates, evidence, rollback

## Always-required gates per phase
- Backend: `pytest` green; no new `/api/*`; contracts updated if shape changes. :contentReference[oaicite:10]{index=10}
- Frontend: `npm run build`; Playwright e2e smoke path(s) for the phase.
- Manual: Phase B cross-site browser checklist. :contentReference[oaicite:11]{index=11}
- Smoke: v1 smoke checklist after deploy. :contentReference[oaicite:12]{index=12}
- Each phase PR includes at least **one**: new/updated test, doc update, or ops/metric improvement.

## Rollback principles
- Primary rollback lever = **feature flags off** (server authoritative).
- Contract rollback = revert `contracts/` to prior tag + deploy.
- Runtime rollback = revert commit / image to last known-good.

---

# Phase 0 — Contract, Flag, and CI Baseline (Freeze v1 shape)

## Goal
Freeze the v1 surface so later phases are strictly additive and flag-gated.

## Deliverables
- `contracts/`:
  - Canonical endpoint map with lane classification (UI/Public/Dev/Legacy)
  - Error/schema definitions + error-code registry
  - Feature-flag schema/defaults
- Frontend boot:
  - loads `runtime-config.json`
  - calls `GET /v1/meta`
  - renders app shell; shows **error banner** if backend unreachable
- Playwright smoke tests:
  - login → load chat/workspace → stream → cancel → retry (minimal baseline)
- CI stabilization:
  - deterministic env, seeded user for tests where applicable, stable selectors

## DoD gates
- Backend: `pytest` green; no new `/api/*`; `/api/*` explicitly labeled deprecated.
- Frontend: `npm run build` + Playwright baseline smoke.
- Manual: Phase B cross-site checks. :contentReference[oaicite:13]{index=13}

## Rollback
- Flags default off (new work hidden)
- Revert to prior `contracts/` tag + redeploy

---

# Phase 1 — Auth + CSRF Lifecycle “Locked”

## Goal
Cross-site cookie auth is deterministic and reliable.

## Deliverables
- Backend:
  - `/v1/auth/csrf/bootstrap` is the **only unauthenticated** CSRF endpoint
  - normalized auth errors + consistent handling
  - audit log for auth events (login/logout/register/invite failures) :contentReference[oaicite:14]{index=14}
- Frontend:
  - centralized `apiClient` with:
    - `credentials: "include"`
    - CSRF header injection
    - normalized error mapping
  - on `401`: allow only `GET /v1/meta`, then route to login/boot

## DoD gates
- Phase B checklist passes (Secure/SameSite=None cookies; strict CORS; validated SSE Origin). :contentReference[oaicite:15]{index=15}
- Smoke + Playwright auth path

## Rollback
- `strict_auth=false` permitted only in dev/test; production must remain strict.

---

# Phase 2 — Workspace Shell (UI-only)

## Goal
Introduce workspace metaphor without destabilizing chat.

## Deliverables
- Frontend:
  - routes: `/workspace`, `/workspace/:projectId`
  - panes: Chat | Editor | Results (stubs)
  - project navigation stub list
  - fully hidden when `workspace=false`
- Backend:
  - optional stub: `GET /v1/projects` returns empty list (flag gated)

## DoD gates
- Workspace renders; when disabled, routes/navigation hidden; legacy chat remains.
- CSP meta ordering valid; no violations. :contentReference[oaicite:16]{index=16}

## Rollback
- `workspace=false` removes navigation/routes

---

# Phase 3 — Embedded Intelligent Chat (SSE parity in Workspace)

## Goal
Streaming is default within workspace; parity with legacy chat (cancel/retry/no dupes).

## Deliverables
- Backend:
  - Provider abstraction routing (LM Studio first; Ollama/OpenAI-compat pluggable) :contentReference[oaicite:17]{index=17}
  - enforce concurrency + rate limits; Redis as scaling switch :contentReference[oaicite:18]{index=18}
- Frontend:
  - streaming adapter:
    - chunk buffering/batching
    - cancel is authoritative and immediate (AbortController)
    - deterministic retry (same payload/settings)
  - no duplicate messages on retry/cancel boundary

## DoD gates
- E2E: login → pick project → send → stream → cancel → retry (no duplicates)

## Rollback
- `intelligent_chat=false` falls back to legacy chat

---

# Phase 4 — Projects + Docs + “Apply to Doc”

## Goal
Project persistence + AI outputs can be inserted into docs safely.

## Deliverables
- Backend (Project/Docs Agent module):
  - Projects + Docs CRUD (SQLite default; Postgres ready) :contentReference[oaicite:19]{index=19}
  - optional versioning
  - CSRF required for mutations
  - structured “analysis” endpoint (strict schema)
  - rate limits on doc mutation endpoints
- Frontend:
  - markdown editor pane (sanitized rendering)
  - results cards support: insert/replace/append/new doc
  - safe UX for conflicts (last-write-wins or optimistic revision IDs)

## DoD gates
- Backend: pytest covers CRUD/authz
- Frontend: Playwright covers apply-to-doc
- Limits: sane doc mutation rate limiting + size caps

## Rollback
- `editor=false` disables editor/docs UI and endpoints return `E_CAPABILITY_DISABLED`

---

# Phase 5 — Images + Artifacts

## Goal
Project-scoped media generation + artifact listing, securely.

## Deliverables
- Backend (Media Agent):
  - store under `MEDIA_STORAGE_PATH`
  - enforce size/type limits; auth required
  - path traversal hard-block; per-project scoping
- Frontend:
  - generate image from chat/editor (flag gated)
  - artifacts panel (list/preview; lazy-load)

## DoD gates
- File limits enforced; traversal blocked; auth required (tests)
- Manual verification for upload/download behavior

## Rollback
- `images=false` disables endpoints/UI

---

# Phase 6 — Workflows (Sequential only)

## Goal
Deterministic, restartable workflow runner (v1-safe, no background jobs).

## Deliverables
- Backend (Workflow Agent):
  - schema-validated workflow spec
  - sequential steps only
  - SSE stream for execution
  - persist inputs + step outputs
  - pluggable executor registry (explicit allowlist)
- Frontend:
  - workflow builder (minimal)
  - runner + inspector (step timeline, logs, outputs)

## DoD gates
- Backend: pytest for schema + executors
- Frontend: Playwright sample workflow E2E

## Rollback
- `workflows=false` disables workflow UI/API

---

# Phase 7 — Project Intelligence (User-overridable)

## Goal
Explicit, refresh-on-demand summarization/tagging (no background jobs).

## Deliverables
- Backend:
  - activity events stored (append-only)
  - explicit “refresh intelligence” endpoint returns structured JSON
  - no periodic tasks in v1
- Frontend:
  - dashboard cards (summary/tags/related)
  - edit + refresh controls; clear “stale” indicators

## Rollback
- `project_intel=false` returns empty/disabled capability response

---

# Phase 8 — Public API lane

## Goal
Integrations with minimal browser risk.

## Deliverables
- Backend:
  - `/v1/public/*` router with bearer tokens + scopes + usage counters
  - CORS off; separate middleware chain
  - strict rate limits distinct from UI lane

## DoD gates
- pytest: cookie auth stays CORS-enabled only on `/v1/*`; public lane no CORS
- stable error codes + usage counters covered by tests

## Rollback
- `public_api=false` disables router

---

# Tracking + onboarding workflow

## Recommended milestone order
1) Phase 0 → 2) Phase 1 → 3) Phases 2–3 → 4) Phase 4 → 5) Phases 5–6 → 6) Phase 7 → 7) Phase 8+

## Work item template (per phase)
For each phase, create a tracking epic with sections:
- **Contracts**: endpoints + schemas + error codes
- **Backend**: agent/module + router + persistence + limits
- **Frontend**: gated UI + routing + adapters
- **Tests**: pytest + Playwright additions
- **Ops/Docs**: runbook + smoke updates
- **Rollback**: flags + revert plan

## Required checklists (use these as gate references)
- Phase B Cross-Site Verification Checklist :contentReference[oaicite:20]{index=20}
- v1 Smoke Test Checklist :contentReference[oaicite:21]{index=21}
- Security/CSP guidance :contentReference[oaicite:22]{index=22}
- Scaling/Redis limits notes :contentReference[oaicite:23]{index=23}
- Agent boundary reference :contentReference[oaicite:24]{index=24}

## Deployment expectations
- Keep deployment/runbook docs current with each phase. :contentReference[oaicite:25]{index=25}
- Never introduce frontend secrets; any provider or token work stays backend-only. :contentReference[oaicite:26]{index=26}
