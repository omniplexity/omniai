# OmniAI Project Structure

**Purpose:** Quick reference for understanding OmniAI's architecture, features, and capabilities.

---

## What is OmniAI?

OmniAI is an **AI-powered workspace** that unifies:
- Chat interface for AI conversations
- Code/text editor with version history
- Dashboard with analytics and provenance tracking
- Tool marketplace with MCP integration
- Memory system for persistent knowledge
- Workflow automation engine
- Deep research capabilities

---

## Architecture Overview

### Three Repositories

```
┌─────────────────────────────────────────────────────────────┐
│                        OmniAI                                │
├─────────────────┬─────────────────────┬─────────────────────┤
│  omni-backend   │   omni-contracts    │     omni-web        │
│    (API)       │     (Schemas)       │    (Frontend)       │
├─────────────────┼─────────────────────┼─────────────────────┤
│ FastAPI         │ JSON Schema         │ React + TypeScript  │
│ SQLite          │ Pydantic Models     │ Vite                │
│ Event Sourcing  │ Validation          │ SSE Client          │
└─────────────────┴─────────────────────┴─────────────────────┘
```

---

## Core Concepts

### 1. Event-First Design
Every action creates an immutable **RunEvent**. The UI is just a projection of these events.

**Event Types (46+):**
- `user_message` / `assistant_message` - Chat
- `tool_call` / `tool_result` / `tool_error` - Tool execution
- `memory_item_created` / `memory_item_updated` - Memory
- `workflow_node_started` / `workflow_node_completed` - Workflows
- `research_stage_started` / `research_report_created` - Research
- `artifact_ref` / `artifact_linked` - File handling

### 2. Hierarchical Organization
```
Project → Thread → Run
```
- **Project**: Container for collaboration, has members with roles
- **Thread**: Conversation thread within a project
- **Run**: Execution context with pinned tools/models

### 3. Policy Engine
- **Deny-by-default**: All tool access requires explicit scope grants
- **Approvals**: Elevated-risk tools (external writes, network egress) need approval
- **Scopes**: Project-level permissions (viewer/editor/owner)

---

## Features & Implementation

### Authentication & Security
| Feature | Implementation |
|---------|---------------|
| Password Hashing | Argon2 with SHA256 legacy upgrade |
| Sessions | Secure HTTP-only cookies |
| CSRF Protection | HMAC-based tokens |
| Access Control | Role-based (viewer/editor/owner) |

**Endpoints:**
- `POST /v1/auth/login` - Session login
- `POST /v1/auth/register` - New user registration
- `POST /v1/auth/logout` - Session revocation
- `GET /v1/me` - Current user info

### Chat & AI
| Feature | Implementation |
|---------|---------------|
| Chat Interface | React component with SSE |
| AI Responses | `/agent_stub` endpoint (stub) |
| Streaming | Server-Sent Events |
| Context | Full conversation history in events |

**Endpoint:** `POST /v1/runs/{run_id}/agent_stub`

### Tools & MCP
| Feature | Implementation |
|---------|---------------|
| Tool Registry | Built-in manifests + MCP servers |
| MCP Integration | HTTP transport, stdio transport |
| Policy Engine | Scope-based access control |
| Invocation | Synchronous with approval flow |

**Endpoints:**
- `GET /v1/tools` - List available tools
- `POST /v1/runs/{run_id}/tools/invoke` - Execute tool
- `POST /v1/mcp/servers` - Register MCP server

### Memory System
| Feature | Implementation |
|---------|---------------|
| Storage | SQLite with FTS5 search |
| Types | Semantic, episodic, procedural |
| Search | Hybrid keyword + importance scoring |
| Provenance | Linked to source events/artifacts |

**Endpoints:**
- `POST /v1/memory/items` - Create memory
- `GET /v1/memory/items` - List memories
- `POST /v1/memory/search` - Search memories

### Workflows
| Feature | Implementation |
|---------|---------------|
| Definition | Graph-based (nodes + edges) |
| Execution | Sequential with approval gates |
| Retry | Configurable backoff |
| State | Persisted to artifacts |

**Endpoints:**
- `POST /v1/workflows` - Define workflow
- `POST /v1/runs/{run_id}/workflows/{id}/{version}/start` - Run workflow

### Deep Research
| Feature | Implementation |
|---------|---------------|
| Pipeline | decompose → search → cluster → extract → synthesize → critique → finalize |
| Sources | Web search results stored |
| Output | Markdown report with citations |
| Provenance | Full trace to sources |

**Endpoint:** `POST /v1/runs/{run_id}/research/start`

### Provenance Tracking
| Feature | Implementation |
|---------|---------------|
| Graph | Event → Tool → Artifact → Source |
| Caching | Optimized for common queries |
| Paths | "Why" queries for any artifact |

**Endpoints:**
- `GET /v1/runs/{run_id}/provenance/graph` - Full graph
- `GET /v1/runs/{run_id}/provenance/why` - Explain artifact

### Artifacts
| Feature | Implementation |
|---------|---------------|
| Storage | File-based with hash addressing |
| Upload | Multi-part chunked uploads |
| Linking | Events reference artifacts |
| Types | Text, JSON, binary |

**Endpoints:**
- `POST /v1/artifacts` - Create artifact
- `POST /v1/artifacts/init` - Start upload
- `PUT /v1/artifacts/{id}/parts/{n}` - Upload chunk
- `POST /v1/artifacts/{id}/finalize` - Complete upload

### Registry & Marketplace
| Feature | Implementation |
|---------|---------------|
| Packages | Tool bundles with manifests |
| Signing | Ed25519 signatures |
| Verification | Schema + signature + static checks |
| Tiers | Core, Verified, Community, Private |

**Endpoints:**
- `GET /v1/registry/packages` - Browse packages
- `POST /v1/registry/packages/import` - Add package
- `POST /v1/projects/{id}/tools/install` - Install to project

---

## Running OmniAI

### Prerequisites
- Python 3.13+
- Node.js 18+
- npm or pnpm

### Backend
```bash
cd omni-backend
pip install -e .
python -m omni_backend.main
# Runs on http://127.0.0.1:8000
```

### Frontend
```bash
cd omni-web
npm install
npm run dev
# Runs on http://127.0.0.1:5173
```

### Docker
```bash
docker-compose up --build
```

---

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app.py` | FastAPI routes & business logic |
| `db.py` | SQLite database layer |
| `config.py` | Settings management |
| `tools_runtime.py` | Tool execution engine |
| `mcp_client.py` | MCP server client |

### Contracts
| File | Purpose |
|------|---------|
| `schemas/*.schema.json` | JSON Schema definitions |
| `python/omni_contracts/models.py` | Pydantic models |
| `python/omni_contracts/validate.py` | Schema validation |

### Frontend
| File | Purpose |
|------|---------|
| `src/App.tsx` | Main application (monolithic) |
| `src/components/auth/LandingPage.tsx` | Login/Register UI |
| `src/components/center-panel/` | Chat, Editor, Dashboard |
| `src/sse.ts` | Server-Sent Events client |

---

## Roadmap & Next Steps

### P0 - Must Have
1. **Real LLM Integration** - Replace stub with OpenAI/Anthropic/xAI
2. **Streaming Responses** - SSE for chat responses

### P1 - Should Have
3. **Real Web Search** - Replace deterministic research
4. **Frontend Refactoring** - Split App.tsx
5. **Rate Limiting** - API protection

### P2 - Nice to Have
6. **Real-time Collaboration** - WebSocket for editor
7. **PostgreSQL Option** - For production scale
8. **API Versioning** - Breaking change handling

---

## Summary

OmniAI provides a complete AI workspace with:
- ✅ Strong event-sourcing foundation
- ✅ Comprehensive tool & MCP integration
- ✅ Memory and provenance tracking
- ✅ Workflow automation
- 🟡 AI responses (stub - needs LLM)
- 🟡 Research (stub - needs real search)

The codebase is well-tested (176 tests) and follows security best practices. Main gaps are replacing stub implementations with real AI/LLM providers.
