# AGENTS.md — OmniAI Workspace Program (Master Plan Execution)

## Goals 🎯
- Build **OmniAI**, a modular AI-powered web workspace unifying **Chat**, **Editor**, **Dashboard**, **Tools**, **MCP Browser**, **Deep Research/Workflows**, and a **Tool Marketplace**.
- Enforce the program non-negotiables:
  1) **Everything is a Run** (append-only event log → projections/audit/replay)  
  2) **Plugin-first** (tools/connectors = manifests + policy + sandbox)  
  3) **Secure-by-default** (deny-by-default scopes; approvals for sensitive actions)  
  4) **Provider-agnostic** (OpenAI/Anthropic/xAI/local behind one interface)  
  5) **Reproducible** (pin tool + model versions per run/project)

---

## Operating Model (How work happens) 🧭

### “Everything is a Run”
All user interactions and system actions are recorded as **RunEvents** (append-only). The UI is a **projection** of RunEvents. No hidden state.

**Canonical event sequence**
1. `run_created`
2. `user_message`
3. (optional) `assistant_message_delta*`
4. `assistant_message`
5. `tool_call`
6. `tool_result | tool_error`
7. `artifact_ref` (for blobs/large outputs)
8. `system_event` (approvals, policy denials, gates, etc.)

### Agent Workflow Loop
Agents operate in a repeatable loop that maps to the UI “Agent mode” toggle:

1) **Plan** → propose steps, constraints, touched modules, acceptance tests  
2) **Execute** → minimal diffs, strictly scoped changes  
3) **Verify** → run tests, include outputs  
4) **Finalize** → summarize changes, document decisions, update docs/contracts

### Definition of Done (per PR)
- ✅ Acceptance tests implemented and passing
- ✅ Contract schemas validated (if touched)
- ✅ Security checks and redaction rules respected
- ✅ Docs updated (RFD/DECISIONS/AGENTS if behavior changes)
- ✅ Reproducibility: pins/version bumps where required

---

## Repos & Responsibilities 🗂️

### `omni-contracts/`
**Source of truth** for schemas and typed contracts.
- RunEvent envelope + per-kind payload schemas
- ToolManifest schema
- Policy schema
- Artifact reference schema
- Contract tests (goldens + round-trip)

### `omni-backend/` (FastAPI modular monolith)
**System of record** and execution plane.
- Auth/session baseline (minimal early; expand later)
- Projects/threads/runs persistence
- RunEvent append + read APIs
- SSE stream per run
- Tool runtime (registry + policy + executors)
- Artifact store

### `omni-web/` (SPA)
**Projection layer** and operator console.
- 3-pane shell (nav / center tabs / right drawer)
- Chat, Editor, Dashboard
- Run timeline and tool cards
- Approvals UI and citations/provenance panel
- SSE client + reconnect

---

## Agent Roles (Capabilities, Inputs/Outputs, Success Criteria) 🤖

### 1) Program Architect (Lead)
**Owns:** system shape, boundaries, contracts between repos  
**Inputs:** master plan, milestone goals, risk constraints  
**Outputs:**
- RFDs (Request For Discussion docs)
- Architectural diagrams (text-based ok)
- DECISIONS.md entries (why + tradeoffs)
- Interface boundaries (APIs, contracts, projections)
**Success:**
- Minimal rewrites between milestones
- Clean separation: UI/API/core/runtime/storage
- Compatibility strategy documented (schema/versioning)

---

### 2) Contracts Engineer (Lead for Phase 0)
**Owns:** `omni-contracts` schemas + typed libs  
**Outputs:**
- JSON Schemas for RunEvent, ToolManifest, Policy, ArtifactRef
- Typed packages (e.g., pydantic models)
- Contract test harness
**Success:**
- Schema validation at boundaries is strict
- Backwards-compatible evolutions are possible (versioning)

---

### 3) Backend Platform Engineer (Lead for Milestone A/B)
**Owns:** persistence, event store, SSE, baseline API  
**Outputs:**
- SQLite schema + migrations
- Append-only event endpoints
- SSE streaming endpoints with reconnect + heartbeat
- Rate limits, request size limits, structured logs + redaction hooks
**Success:**
- Create project → thread → run; stream events; reload reproduces timeline identically

---

### 4) Frontend Workspace Engineer (Lead for Milestone A/B)
**Owns:** SPA shell, projections, timeline renderer  
**Outputs:**
- 3-pane layout
- RunTimeline projection components
- Tool call/result cards
- SSE client with robust reconnect strategy
**Success:**
- Timeline deterministic + stable rendering
- Tool cards typed and extensible

---

### 5) Tool Runtime Engineer (Lead for Phase 2)
**Owns:** tool registry, policy engine, executor bindings  
**Outputs:**
- Tool registry with pinned version resolution
- Policy engine (deny-by-default) + approvals pipeline
- Executor interfaces for: `inproc_safe`, `sandbox_job`, `mcp_remote`, `openapi_proxy`
- Event emission: `tool_call` → `tool_result|tool_error`
**Success:**
- Tools are “just manifests” + validated IO
- No tool executes without policy authorization

---

### 6) Sandbox/Compute Engineer (Phase 2)
**Owns:** ephemeral job runner, resource caps, egress control  
**Outputs:**
- sandbox runner (no network by default)
- resource limits (CPU/mem/time)
- artifact export from sandbox workspace
**Success:**
- Deterministic behavior where possible
- Clear failure modes → structured `tool_error` events

---

### 7) Security & Compliance Agent (Always-on)
**Owns:** secure defaults, threat modeling, approvals, redaction  
**Outputs:**
- Threat model notes per milestone
- CORS allowlist + host binding checks
- Secrets handling rules + log redaction patterns
- Approval UX requirements (write scopes, external egress)
**Success:**
- “Unsafe by default” never ships
- Any external write requires explicit approval event trail

---

### 8) QA / Verification Agent (Always-on)
**Owns:** acceptance tests, regression harness, replay validation  
**Outputs:**
- pytest (backend), Playwright (frontend)
- Ordering tests (seq monotonicity, SSE ordering)
- Replay tests (persist/reload identical projections)
**Success:**
- Prevents drift from event-sourcing invariants
- Evidence attached to PRs (test outputs)

---

### 9) MCP Integrations Agent (Phase 3)
**Owns:** MCP server registry, catalog caching, tool wrapping  
**Outputs:**
- MCP server CRUD + health checks
- catalog cache + schema viewer endpoints
- “Try Tool” console → normal `tool_call` events
- “Pin as installed tool” wrapper creation
**Success:**
- MCP tools behave like first-class tools with manifests/policy

---

### 10) Memory & Knowledge Agent (Phase 4)
**Owns:** scoped memory store, provenance, retrieval budget rules  
**Outputs:**
- Memory item schemas (episodic/semantic/procedural)
- Retrieval pipeline (hybrid: keyword+semantic+recency+importance)
- UI controls (view/edit/delete, retention windows, redaction)
**Success:**
- Memory is auditable and attributable to runs/events
- Prompt budget is enforced

---

### 11) Deep Research & Workflows Agent (Phase 5)
**Owns:** research run type, citation store, workflow engine  
**Outputs:**
- Research pipeline stages: decompose → search → cluster → extract → synthesize → critique → finalize
- Workflow graph runner (seq/parallel/branch/retry/approval)
- Citation artifacts + provenance links
**Success:**
- Reports are reproducible with citations
- Workflow runs emit structured events at each node

---

### 12) Marketplace Agent (Phase 6+)
**Owns:** tool packages, signing, validation, registries  
**Outputs:**
- Registry tiers (Core/Verified/Community/Private)
- Package formats (manifest bundles, MCP wrappers, workflow packs)
- Verification pipeline (schema lint, license scan, static checks, contract tests)
- Yank/revoke and pinning UX
**Success:**
- Install is policy-aware and permissioned
- Version pinning is enforced per project/run

---

## Milestone Ownership Map 🧩

### Milestone A — Run Event Backbone
- Lead: Backend Platform Engineer + Frontend Workspace Engineer
- Support: Contracts Engineer, QA, Security

### Milestone B — Workspace Shell
- Lead: Frontend Workspace Engineer
- Support: Backend Platform Engineer, QA, Security

### Milestone C — Tool Runtime v1
- Lead: Tool Runtime Engineer
- Support: Sandbox/Compute, Security, QA

### Milestone D — MCP Browser v1
- Lead: MCP Integrations Agent
- Support: Tool Runtime Engineer, Frontend, QA, Security

### Milestone E — Memory v1
- Lead: Memory & Knowledge Agent
- Support: Backend, Frontend, Security, QA

### Milestone F — Deep Research v1
- Lead: Deep Research & Workflows Agent
- Support: Tool Runtime, Frontend, QA, Security

### Milestone G/H — Marketplace + Community/Verified
- Lead: Marketplace Agent
- Support: Security, QA, Tool Runtime, MCP Integrations

---

## Engineering Standards (Non-negotiable implementation rules) 🧱

### Contracts & Versioning
- Schemas are the integration boundary.
- Additive changes preferred; breaking changes require:
  - contract version bump
  - migration plan
  - compatibility shims (where practical)

### Event Store Invariants
- `seq` monotonic per run; assigned by server
- Append-only; no edits in place
- Any derived state must be reconstructible from events

### Tool IO Validation
- Every tool call/result must validate against its manifest schema.
- Large payloads must be moved to artifacts (content-hash addressed) and referenced via `artifact_ref`.

### Security Defaults
- Backend binds to `127.0.0.1` by default
- Strict CORS allowlist (explicit origins only)
- Deny-by-default scopes
- Approvals required for:
  - write scopes
  - external writes
  - network egress from sandbox
- Structured logs + secret redaction; never log raw secrets

### Reproducibility
- Runs pin:
  - model provider + model id + params (+ seed if applicable)
  - tool versions + executor versions
- Store tool inputs and outputs (or artifact refs) to support replay/audit

---

## Deliverable Format (What agents must produce) 📦

For any implementation task, the agent response must include:
1) **Touched file tree** (paths only)
2) **Minimal diffs** (or full contents for new files)
3) **Commands to run** (format/lint/test)
4) **Test output** (copy/paste text)
5) **Edge cases + failure modes** handled/remaining

---

## Codex/CLI Task Template (paste into issues) 🧾

**Title:** (imperative verb)  
**Goal:**  
**Acceptance Tests:**  
- …  
**Touched Modules:**  
- …  
**Constraints:**  
- security, schema validation, no breaking changes, etc.  
**Commands:**  
- `pytest -q`  
- `pnpm test` / `pnpm e2e`  
**Output Required:** file tree + diffs + test outputs + notes

---

## RFD / Decisions Policy 📝
- Any cross-cutting change (contracts, replay semantics, policy model, tool runtime) requires:
  - an RFD (short, focused)
  - a DECISIONS.md entry (choice + tradeoffs + implications)

---

## Risk Register (continuous)
Agents must flag (as `system_event` equivalents in docs/PR notes) when introducing:
- new write/egress capability
- new secret store path
- non-deterministic behavior that affects replay
- schema-breaking changes

---

## Quick Start (Phase 0 checklist) ✅
1) `omni-contracts`: RunEvent/ToolManifest/Policy/ArtifactRef schemas + tests  
2) `omni-backend`: project/thread/run + run_events store + SSE stream  
3) `omni-web`: 3-pane shell + SSE client + RunTimeline projection  
4) Acceptance: create→stream→reload gives identical timeline

---
