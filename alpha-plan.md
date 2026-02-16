# OmniAI Master Plan (Program-Level) - Workspace, Agents, Tools, MCP, Community Marketplace
## North Star
A modular AI-powered web workspace ("OmniAI") unifying:
- **Chat**: Agent-based, tool-using, multimodal.
- **Editor**: Content/code with patch-based AI.
- **Dashboard**: Projects, runs, artifacts, costs, provenance.
- **Tools Layer**: Universal connector runtime.
- **MCP Browser**: Discover, inspect, try MCP tools.
- **Tool Marketplace**: Core, verified, community, and private registries.
- **Deep Research + Workflows**: Run graphs with citations, audit, replay.
## Non-Negotiables
- **Everything is a Run:** Persistent event log → UI projections, audit, replay.
- **Plugin-first:** Tools/connectors are manifests + policy + sandbox.
- **Secure-by-default:** Deny-by-default write scopes; approvals required for sensitive actions.
- **Provider-agnostic models:** OpenAI/Anthropic/xAI/local behind a single interface.
- **Reproducible:** Pin tool and model versions per run/project.
---
## Phase 0 — Foundation Contracts (1–2 weeks)
**Deliverables:**
- Contracts repo/package (`omni-contracts`)
- RunEvent, ToolManifest, Artifact, and Policy schemas
- Backend skeleton (FastAPI modular monolith):
- auth/session baseline
- project/thread/run storage
- SSE stream for run events
- Frontend skeleton (GitHub Pages SPA):
- 3-pane shell: nav / center tabs / right drawer
- Connect to SSE, render run timeline
- Acceptance tests:
- Create project → thread → run; stream events; persist/reload identical timeline
## Phase 1 — Core Workspace v1 (Chat + Editor + Dashboard)
**Chat (Intelligent Chat):**
- Streaming responses, tool-call cards, citations panel
- Message types: user/assistant/tool_call/tool_result/artifact_ref/system_event
- "Agent mode" toggle: plan → execute → verify → finalize
**Editor:**
- Markdown/code editing
- AI actions: rewrite/refine/outline/critique
- Refactor/code patch (diff view + approve)
- Document versioning; "promote snippet to memory"
**Dashboard:**
- Project list, recent runs, artifact gallery
- Run detail: steps, tool calls, cost/time, errors, provenance
**Acceptance tests:**
- "Apply patch" bumps version and provides reversible diff
- Tool call outputs render as typed components (table/json/diff)
## Phase 2 — Tool Runtime v1 (Universal Connector Layer)
**Tool model:**
- Manifest + JSON Schema IO + risk metadata + execution binding:
- inproc_safe
- sandbox_job
- mcp_remote
- openapi_proxy
**Policy & permissions:**
- Scopes: read_web, read_files, write_files, read_github, write_github, send_email, etc.
- Workspace → project → user grants
- Approvals needed for external_write=true or elevated scopes
**Sandbox compute:**
- Ephemeral job runner (no network by default, resource caps)
- Run-scoped workspace dir, artifact export
**Initial tools:**
- web.search, web.fetch_extract
- files.ingest, files.write_patch
- python.compute (sandbox)
- git.diff, git.apply_patch (server-side only initially)
## Phase 3 — MCP Browser (UI + backend sessions)
*Codex CLI* supports MCP and agent workflows; align OmniAI’s runtime to this model. MCP servers expose tool catalogs; OmniAI browses and pins them.
**MCP Browser UI:**
- Add/register MCP server (workspace/project scope)
- Health, latency, auth state
- Tool catalog explorer (schema viewer)
- "Try Tool" console (inputs, preview outputs)
- "Pin as Installed Tool" (wrap MCP tool with stable ID, policy)
**Backend:**
- MCP registry, sessions, catalog caching
- Tool call adapter: run step → MCP call → tool_result event
**Acceptance tests:**
- Add MCP server → list tools → execute "Try tool" → view as tool card + run event
## Phase 4 — Memory + Knowledge (Project Intelligence)
**Memory types/scope:**
- Scopes: user-private, workspace, project, thread, document
- Types: episodic (summaries), semantic (facts/entities), procedural (workflows/macros)
**Retrieval:**
- Hybrid (keyword + semantic + recency + importance)
- Strict prompt memory budget
- Memory provenance: link memory items to runs/messages
**Controls:**
- View/edit/delete; retention windows; "do not store" toggles
- Redact secrets/PII in logs and memory
## Phase 5 — Deep Research + Smart Workflows
**Deep Research run type:**
- Pipeline: decompose → search → cluster → extract → synthesize → critique → finalize report/citations
**Workflow engine:**
- Graph runner: sequential, parallel, branch, retry, approval
- Templates: research briefing, repo review/patch/tests, content pipeline, triggers (schedule/webhook)
## Phase 6 — Tool Marketplace + Community Registry
**Registry tiers:**
- Core (built-in), Verified (scanning/review), Community (open publishing with constraints), Private (per org/workspace)
**Package types:**
- Tool wrapper (MCP/OpenAPI), code tool (sandboxed), MCP server descriptor, workflow/agent recipe pack
**Trust & safety:**
- Signed packages (publisher/registry keys)
- Auto pipeline: schema lint, license scan, static checks, contract tests
- Yank/revoke versions, pin per project
- Install UI: permissions, egress, secrets, risk label
**Marketplace UI:**
- Search/facets: category, execution type, risk, verified, compatibility
- Collections, publish MCP wrappers
- Org mirroring: approve → copy into private registry
## Phase 7 — Collaboration + Operations
**Collaboration:**
- Shared projects, roles
- Comments/annotations on artifacts and diffs
- Activity feed, notifications
**Observability:**
- Run tracing UI, cost/latency dashboards (model/tool)
- Tool failure rates, provider health
**Hardening:**
- Quotas: tokens, tool calls, runtime, storage
- Data rooms (policy templates)
- Offline/limited mode (drafts queued)
## Feature Brainstorm (pre-v1 scope lock)
"AI OS" polish features:
- Command Palette: universal actions
- Run Replay: rerun with pinned versions
- Provenance Graph: artifact ← run steps ← tools ← sources
- Typed Outputs for workflows
- Agent Roles Marketplace: publish planner/researcher/coder presets
- Evaluation Suite: prompt/workflow regression tests
- Secrets Firewall: output scan for leaks
- Worktree/Branch Orchestration: parallel agent worktrees
**Creator features:**
- Multi-image jobs, variant management
- Doc-to-deck/blog pipelines
- Reusable brand/style profiles per project
---
## Step-by-Step Build Plan Using Codex CLI
Codex CLI is for agent coding and approvals. Use MCP integration; supervise with gates/tests.
### Agent Workflow (Repeatable Loop)
**0) Repo hygiene/gates:**
- RFD docs + DECISIONS.md
- make test/lint/fmt/ci scripts
- "Definition of Done" checklist per PR:
- Tests updated
- Schemas validated
- Security checks
- Docs updated
**1) Task decomposition (per milestone):**
- Convert phase to issues (vertical slice: UI/API/persistence/tests)
- For each issue: acceptance tests, touched modules, constraints
**2) CLI execution (per issue):**
- Safe parallelism: worktrees/branches per issue (one agent per worktree)
- Approvals for risky actions (network/commands)
- Codex prompt: goal, tests, schema, file constraints; implement minimal changes, add/adjust tests, run CI, report output
**3) Review and merge:**
- Diff review (focus: policy/tool runtime)
- Schema validation
- Run replay sanity check
---
## Concrete Milestone Sequence
- **Milestone A — Run Event Backbone:** Runs, run_event persistence, SSE, UI run timeline/trace; tests: create run, events, stream order
- **Milestone B — Workspace Shell:** 3-pane UI, routing, chat streaming/message types, editor v1/versioning
- **Milestone C — Tool Runtime v1:** Registry, manifest validation, policy grants, approval hooks, three starter tools
- **Milestone D — MCP Browser v1:** Registry, catalog caching, browser UI, pin tool
- **Milestone E — Memory v1:** Scoped store, provenance, retrieval, memory UI
- **Milestone F — Deep Research v1:** Pipeline, citation store, report/viewer, evaluation
- **Milestone G — Marketplace v1:** Registry API, signing, validation, marketplace UI
- **Milestone H — Community + Verified:** Moderation, reporting, verified pipeline, collections, org mirroring
