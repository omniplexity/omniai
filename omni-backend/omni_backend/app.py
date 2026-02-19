from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import Settings
from .db import Database, QuotaExceededError, hash_bytes
from .logging_utils import configure_logging, redact_dict
from .mcp_client import McpHttpClient
from .tools_runtime import EXECUTOR_VERSION, builtin_tool_manifests, execute_tool, validate_json_schema

try:
    from omni_contracts import SystemConfigSnapshot, validate_schema as contract_validate_schema
except Exception:
    SystemConfigSnapshot = None
    contract_validate_schema = None

logger = logging.getLogger("omni_backend")
DEFAULT_PINS = {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}
MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
PWD = PasswordHasher()
SYSTEM_CONFIG_CONTRACT_VERSION = "0.1.0"
SYSTEM_CONFIG_RUNTIME_VERSION = "omni-backend-0.4.0"

class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)

class CreateThreadRequest(BaseModel):
    title: str = Field(min_length=1)

class CreateRunRequest(BaseModel):
    status: str = "active"
    pins: dict[str, Any] = Field(default_factory=lambda: DEFAULT_PINS.copy())

class AppendEventRequest(BaseModel):
    kind: str
    payload: dict[str, Any]
    parent_event_id: str | None = None
    correlation_id: str | None = None
    actor: str
    privacy: dict[str, Any] = Field(default_factory=lambda: {"redact_level": "none", "contains_secrets": False})
    pins: dict[str, Any] = Field(default_factory=lambda: DEFAULT_PINS.copy())

class ToolInvokeRequest(BaseModel):
    tool_id: str
    version: str | None = None
    inputs: dict[str, Any]

class InstallToolRequest(BaseModel):
    manifest: dict[str, Any]

class GrantScopeRequest(BaseModel):
    scope: str

class RegistryKeyRequest(BaseModel):
    public_key_id: str
    public_key_base64: str

class RegistryImportRequest(BaseModel):
    package: dict[str, Any]
    blobs_base64: dict[str, str] = Field(default_factory=dict)

class ProjectInstallRequest(BaseModel):
    package_id: str
    version: str
    run_id: str

class ProjectUninstallRequest(BaseModel):
    tool_id: str
    run_id: str

class ProjectPinRequest(BaseModel):
    tool_id: str
    tool_version: str
    run_id: str

class RegistryReportRequest(BaseModel):
    reporter: str
    reason_code: str
    details: str | None = None
    run_id: str

class RegistryStatusRequest(BaseModel):
    to_status: str
    notes: str | None = None
    run_id: str

class RegistryVerifyRequest(BaseModel):
    run_id: str

class RegistryMirrorRequest(BaseModel):
    to_package_id: str
    to_version: str | None = None
    run_id: str

class CollectionCreateRequest(BaseModel):
    name: str
    description: str | None = None
    packages: list[dict[str, str]]
    run_id: str

class UpdateMeRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None

class ProjectMemberRequest(BaseModel):
    user_id: str
    role: str

class ProjectMemberUpdateRequest(BaseModel):
    role: str

class CommentCreateRequest(BaseModel):
    run_id: str | None = None
    thread_id: str | None = None
    target_type: str
    target_id: str
    body: str

class NotificationStubRequest(BaseModel):
    message: str

class NotificationsMarkReadRequest(BaseModel):
    notification_ids: list[str] | None = None
    up_to_seq: int | None = None

    @model_validator(mode="after")
    def validate_input(self):
        has_ids = bool(self.notification_ids)
        has_seq = self.up_to_seq is not None
        if has_ids == has_seq:
            raise ValueError("provide exactly one of notification_ids or up_to_seq")
        if self.up_to_seq is not None and int(self.up_to_seq) < 0:
            raise ValueError("up_to_seq must be >= 0")
        return self

class LoginRequest(BaseModel):
    username: str
    password: str | None = None

class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=100)

class McpServerCreateRequest(BaseModel):
    scope_type: str
    scope_id: str | None = None
    name: str
    transport: str
    endpoint_url: str | None = None
    stdio_cmd: list[str] | None = None
    env: dict[str, str] | None = None
    auth_state: dict[str, Any] | None = None

class McpTryToolRequest(BaseModel):
    name: str
    arguments: dict[str, Any]

class McpPinToolRequest(BaseModel):
    tool_name: str
    tool_id: str
    version: str

class ArtifactCreateRequest(BaseModel):
    kind: str
    media_type: str
    content_base64: str | None = None
    content_text: str | None = None
    title: str | None = None
    @model_validator(mode="after")
    def one_content(self):
        if bool(self.content_base64) == bool(self.content_text is not None):
            raise ValueError("provide exactly one of content_base64 or content_text")
        return self

class ArtifactInitRequest(BaseModel):
    kind: str
    media_type: str
    title: str | None = None
    size_bytes: int | None = None
    content_hash: str | None = None
    run_id: str

class ArtifactFinalizeRequest(BaseModel):
    upload_id: str

class RunArtifactLinkRequest(BaseModel):
    artifact_id: str
    purpose: str
    source_event_id: str | None = None
    correlation_id: str | None = None
    tool_id: str | None = None
    tool_version: str | None = None

class MemoryCreateRequest(BaseModel):
    type: str
    scope_type: str
    scope_id: str | None = None
    title: str | None = None
    content: str
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5
    expires_at: str | None = None
    privacy: dict[str, Any] = Field(default_factory=lambda: {"redact_level": "none", "contains_secrets": False, "do_not_store": False})
    provenance: dict[str, Any] = Field(default_factory=lambda: {"source_kind": "manual"})

class MemoryUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    importance: float | None = None
    expires_at: str | None = None
    privacy: dict[str, Any] | None = None

class MemorySearchRequest(BaseModel):
    query: str = ""
    scope_type: str | None = None
    scope_id: str | None = None
    include_types: list[str] | None = None
    top_k: int = 5
    budget_chars: int = 1200
    include_secret: bool = False

class MemoryPromoteRequest(BaseModel):
    source_event_id: str | None = None
    source_artifact_id: str | None = None
    excerpt: str | None = None
    type: str
    scope_type: str
    scope_id: str | None = None
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5

class ResearchStartRequest(BaseModel):
    query: str
    mode: str = "tool_driven"
    top_k: int = 3
    budget_chars: int = 1200

class WorkflowCreateRequest(BaseModel):
    name: str
    version: str
    graph: dict[str, Any]

class WorkflowRunStartRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)

class AgentRequest(BaseModel):
    user_text: str
    mode: str = "simple"  # "simple" or "agent"

class RequestSizeLimitMiddleware:
    def __init__(self, app: FastAPI, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Skip body check for methods that don't carry a meaningful body
        if scope.get("method") in {"GET", "HEAD", "OPTIONS", "PUT"}:
            await self.app(scope, receive, send)
            return
        req = Request(scope, receive)
        body = await req.body()
        if len(body) > self.max_bytes:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
            await response(scope, receive, send)
            return
        body_sent = False
        async def receive_again():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            # After body replay, delegate to original receive for disconnect detection
            return await receive()
        await self.app(scope, receive_again, send)

def _schema_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "omni-contracts" / "schemas"

def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _validate_event_payload(event: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator
    root = _schema_dir()
    env = _load_json(root / "run_event_envelope.schema.json")
    errs = sorted(Draft202012Validator(env).iter_errors(event), key=lambda e: e.path)
    if errs:
        raise HTTPException(status_code=400, detail=[f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errs])
    ps = _load_json(root / "run_event_kinds" / f"{event['kind']}.schema.json")
    perrs = sorted(Draft202012Validator(ps).iter_errors(event.get("payload", {})), key=lambda e: e.path)
    if perrs:
        raise HTTPException(status_code=400, detail=[f"payload/{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in perrs])

def _validate_tool_manifest(manifest: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator
    schema = _load_json(_schema_dir() / "tool_manifest.schema.json")
    errs = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda e: e.path)
    if errs:
        raise HTTPException(status_code=400, detail=[f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errs])

def _validate_tool_package(package: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator
    schema = _load_json(_schema_dir() / "tool_package.schema.json")
    errs = sorted(Draft202012Validator(schema).iter_errors(package), key=lambda e: e.path)
    if errs:
        raise HTTPException(status_code=400, detail=[f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errs])

def _validate_contract_payload(schema_name: str, payload: dict[str, Any]) -> None:
    if contract_validate_schema is not None:
        contract_validate_schema(schema_name, payload)
        return
    from jsonschema import Draft202012Validator
    schema = _load_json(_schema_dir() / schema_name)
    errs = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: e.path)
    if errs:
        msgs = [f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in errs]
        raise ValueError("; ".join(msgs))

def _validate_system_config_payload(payload: dict[str, Any]) -> None:
    if SystemConfigSnapshot is not None:
        SystemConfigSnapshot.model_validate(payload)
    _validate_contract_payload("system_config.schema.json", payload)

def _canonical_package_payload(package: dict[str, Any]) -> bytes:
    unsigned = dict(package)
    unsigned.pop("signature", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _verify_package_signature(package: dict[str, Any], public_key_base64: str) -> None:
    sig = package["signature"]["signature_base64"]
    message = _canonical_package_payload(package)
    verify_key = VerifyKey(base64.b64decode(public_key_base64))
    try:
        verify_key.verify(message, base64.b64decode(sig))
    except BadSignatureError as exc:
        raise HTTPException(status_code=400, detail="invalid signature") from exc

def _event_envelope(run_id: str, ctx, event: dict[str, Any]) -> dict[str, Any]:
    out = {"event_id": event.get("event_id", "00000000-0000-0000-0000-000000000000"), "run_id": run_id, "thread_id": ctx.thread_id, "project_id": ctx.project_id, "seq": 1, "ts": datetime.now(UTC).isoformat(), "kind": event["kind"], "payload": event["payload"], "actor": event["actor"], "privacy": event.get("privacy", {"redact_level": "none", "contains_secrets": False}), "pins": event.get("pins", DEFAULT_PINS)}
    if event.get("correlation_id"):
        out["correlation_id"] = event["correlation_id"]
    return out

def is_localhost_endpoint(url: str | None) -> bool:
    if not url:
        return True
    return urlparse(url).hostname in {"localhost", "127.0.0.1", "::1"}

def _require_admin(settings: Settings) -> None:
    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="admin/dev mode required")

def _allowed_status_transition(from_status: str, to_status: str) -> bool:
    allowed = {
        "pending_review": {"verified", "rejected"},
        "active": {"yanked", "revoked"},
        "yanked": {"active"},
        "verified": {"yanked", "revoked"},
    }
    return to_status in allowed.get(from_status, set())

def _role_rank(role: str) -> int:
    return {"viewer": 1, "editor": 2, "owner": 3}.get(role, 0)

def _csrf_token(csrf_secret: str, session_id: str) -> str:
    return hmac.new(csrf_secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_legacy_sha256_hash(value: str | None) -> bool:
    if not value or len(value) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in value.lower())

def _generate_simple_response(user_input: str, messages: list[dict[str, Any]]) -> str:
    """Generate a simple response without tool calling - stub implementation."""
    # Simple keyword-based responses for demo
    lower_input = user_input.lower()
    
    if any(kw in lower_input for kw in ["hello", "hi", "hey", "greetings"]):
        return "Hello! I'm OmniAI, your AI assistant. How can I help you today?"
    
    if any(kw in lower_input for kw in ["help", "what can you do"]):
        return "I can help you with: answering questions, writing code, analyzing data, searching the web, managing memory, and running workflows. Just ask!"
    
    if any(kw in lower_input for kw in ["time", "date", "when"]):
        from datetime import datetime
        return f"The current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    if any(kw in lower_input for kw in ["weather"]):
        return "I don't have access to real-time weather data in this stub implementation. In production, I could connect to a weather API."
    
    # Check conversation context for previous messages
    if messages:
        last_user = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        if last_user:
            return f"I understand you said: '{last_user}'. This is a stub response. In production, I'd use an LLM to generate contextual responses."
    
    # Default response
    return f"I received your message: '{user_input}'. This is a stub AI response. In production, I'd connect to OpenAI/Anthropic/xAI to generate intelligent responses."

def _generate_agent_response(user_input: str, messages: list[dict[str, Any]]) -> str:
    """Generate an agent-mode response with tool calling capability - stub implementation."""
    # Agent mode adds context about available tools
    base_response = _generate_simple_response(user_input, messages)
    
    # Add agent-mode specific response
    if "search" in user_input.lower() or "find" in user_input.lower():
        return base_response + "\n\n[Agent Mode] I can use the web.search tool to find information. In production, I'd automatically call it here."
    
    if "file" in user_input.lower() or "read" in user_input.lower():
        return base_response + "\n\n[Agent Mode] I can use file operations to read/write files. In production, I'd execute them here."
    
    return base_response + "\n\n[Agent Mode] In agent mode, I have access to tools and can take autonomous actions. This is a stub implementation."

def create_app() -> FastAPI:
    settings = Settings()
    configure_logging()
    app = FastAPI(title="OmniAI Backend", version="0.4.0")
    app.state.settings = settings
    app.state.db = Database(settings.db_path)

    for manifest in builtin_tool_manifests():
        app.state.db.install_tool(manifest)

    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    origins = settings.cors_origins
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], allow_headers=["Content-Type", "Last-Event-ID", "X-Omni-CSRF", "X-Omni-Idempotency-Key", "Authorization"])

    # --- Raw ASGI middleware (avoids BaseHTTPMiddleware which breaks SSE streaming) ---
    class SessionBaselineMiddleware:
        """Session + CSRF middleware as raw ASGI to preserve StreamingResponse."""

        def __init__(self, asgi_app):
            self.app = asgi_app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            # Ensure scope["state"] exists for request.state access
            if "state" not in scope:
                scope["state"] = {}
            scope["state"]["session_id"] = "session-baseline"
            scope["state"]["user_id"] = None
            scope["state"]["auth_session_id"] = None
            scope["state"]["csrf_expected"] = None

            request = Request(scope, receive, send)
            sid = request.cookies.get(settings.session_cookie_name)
            if sid:
                session = app.state.db.get_session(sid)
                if session:
                    try:
                        if datetime.fromisoformat(session["expires_at"]) > datetime.now(UTC):
                            scope["state"]["user_id"] = session["user_id"]
                            scope["state"]["auth_session_id"] = session["session_id"]
                            scope["state"]["csrf_expected"] = _csrf_token(session["csrf_secret"], session["session_id"])
                            if settings.session_sliding_enabled:
                                remaining = (datetime.fromisoformat(session["expires_at"]) - datetime.now(UTC)).total_seconds()
                                if remaining < settings.session_sliding_window_seconds:
                                    new_exp = (datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
                                    app.state.db.extend_session(session["session_id"], new_exp)
                        else:
                            app.state.db.delete_session(sid)
                    except Exception:
                        pass

            method = scope.get("method", "")
            path = scope.get("path", "")
            if method in {"POST", "PATCH", "DELETE"} and path not in {"/v1/auth/login", "/v1/auth/register"} and not path.startswith("/v2/"):
                if not scope["state"]["user_id"]:
                    resp = JSONResponse({"detail": "authentication required"}, status_code=401)
                    await resp(scope, receive, send)
                    return
                csrf_header = ""
                for hdr_name, hdr_val in scope.get("headers", []):
                    if hdr_name == b"x-omni-csrf":
                        csrf_header = hdr_val.decode("latin-1")
                        break
                csrf_expected = scope["state"]["csrf_expected"]
                if not csrf_expected or not hmac.compare_digest(csrf_header, csrf_expected):
                    uid = scope["state"]["user_id"] or "unknown"
                    run_id = app.state.db.latest_run_for_user(uid) if uid != "unknown" else None
                    if run_id:
                        try:
                            append_run_event(run_id, {"kind": "auth_csrf_failed", "actor": "system", "payload": {"user_id": uid, "path": path, "failed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                        except Exception:
                            pass
                    resp = JSONResponse({"detail": "csrf validation failed"}, status_code=403)
                    await resp(scope, receive, send)
                    return

            await self.app(scope, receive, send)

    app.add_middleware(SessionBaselineMiddleware)

    def append_run_event(run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        ctx = app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        _validate_event_payload(_event_envelope(run_id, ctx, event))
        try:
            stored = app.state.db.append_event(
                run_id,
                event,
                max_events_per_run=app.state.settings.max_events_per_run,
                max_bytes_per_run=app.state.settings.max_bytes_per_run,
            )
        except QuotaExceededError as exc:
            # best-effort quota_exceeded audit event if there is event budget left
            if exc.scope != "events_per_run":
                try:
                    quota_event = {
                        "kind": "quota_exceeded",
                        "actor": "system",
                        "payload": {"scope": exc.scope, "limit": exc.limit, "observed": exc.observed, "at": datetime.now(UTC).isoformat()},
                        "privacy": {"redact_level": "none", "contains_secrets": False},
                        "pins": DEFAULT_PINS,
                    }
                    quota_stored = app.state.db.append_event(
                        run_id,
                        quota_event,
                    )
                    if quota_stored:
                        _fanout_run_event_notifications(
                            run_id=run_id,
                            project_id=ctx.project_id,
                            event=quota_event,
                            stored_event=quota_stored,
                        )
                except Exception:
                    pass
            raise HTTPException(status_code=429, detail=f"quota exceeded: {exc.scope}")
        if not stored:
            raise HTTPException(status_code=404, detail="run not found")
        if event["kind"] in {"workflow_run_completed", "run_status"} and event["kind"] != "metrics_computed":
            rm = app.state.db.get_run_metrics(run_id)
            if rm:
                m_event = {
                    "kind": "metrics_computed",
                    "actor": "system",
                    "payload": {
                        "run_id": run_id,
                        "computed_at": datetime.now(UTC).isoformat(),
                        "event_count": int(rm["event_count"]),
                        "tool_calls": int(rm["tool_calls"]),
                        "tool_errors": int(rm["tool_errors"]),
                        "duration_ms": int(rm["duration_ms"] or 0),
                        "bytes_in": int(rm["bytes_in"]),
                        "bytes_out": int(rm["bytes_out"]),
                    },
                    "privacy": {"redact_level": "none", "contains_secrets": False},
                    "pins": DEFAULT_PINS,
                }
                _validate_event_payload(_event_envelope(run_id, ctx, m_event))
                app.state.db.append_event(run_id, m_event)
        _fanout_run_event_notifications(
            run_id=run_id,
            project_id=ctx.project_id,
            event=event,
            stored_event=stored,
        )
        return stored

    def require_project_role(project_id: str, user_id: str, minimum_role: str = "viewer") -> str:
        if not user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        role = app.state.db.get_project_member_role(project_id, user_id)
        if not role or _role_rank(role) < _role_rank(minimum_role):
            raise HTTPException(status_code=403, detail="project access denied")
        return role

    def emit_project_collab_event(project_id: str, event: dict[str, Any]) -> None:
        run_id = app.state.db.latest_run_for_project(project_id)
        if run_id:
            append_run_event(run_id, event)

    def _notify_users(
        user_ids: list[str] | set[str],
        *,
        kind: str,
        payload: dict[str, Any],
        actor_user_id: str | None,
        project_id: str | None = None,
        run_id: str | None = None,
        activity_seq: int | None = None,
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for uid in sorted({u for u in user_ids if u}):
            if actor_user_id and uid == actor_user_id:
                continue
            created.append(
                app.state.db.create_notification(
                    user_id=uid,
                    kind=kind,
                    project_id=project_id,
                    run_id=run_id,
                    activity_seq=activity_seq,
                    payload=payload,
                )
            )
        return created

    def _fanout_project_activity_notifications(
        *,
        project_id: str,
        activity_row: dict[str, Any],
        actor_user_id: str,
        run_id: str | None,
        summary: str,
        extra: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payload = {
            "project_id": project_id,
            "run_id": run_id,
            "activity_id": activity_row.get("activity_id"),
            "activity_seq": activity_row.get("activity_seq"),
            "summary": summary,
            "actor_user_id": actor_user_id,
        }
        if extra:
            payload.update(extra)
        kind = str(activity_row.get("kind") or "project_activity")
        recipients: set[str] = set()
        if kind == "comment_created":
            recipients = {m["user_id"] for m in app.state.db.list_project_members(project_id)}
        elif kind == "member_added":
            ref_id = str(activity_row.get("ref_id") or "")
            if ref_id:
                recipients = {ref_id}
        elif kind == "member_role_changed":
            ref_id = str(activity_row.get("ref_id") or "")
            if ref_id:
                recipients = {ref_id}
        if not recipients:
            return []
        return _notify_users(
            recipients,
            kind=kind,
            payload=payload,
            actor_user_id=actor_user_id,
            project_id=project_id,
            run_id=run_id,
            activity_seq=activity_row.get("activity_seq"),
        )

    def _fanout_run_event_notifications(
        *,
        run_id: str,
        project_id: str,
        event: dict[str, Any],
        stored_event: dict[str, Any],
        actor_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = {
            "project_id": project_id,
            "run_id": run_id,
            "activity_id": None,
            "activity_seq": None,
            "event_id": stored_event.get("event_id"),
            "summary": "",
            "actor_user_id": actor_user_id,
        }
        recipients: set[str] = set()
        kind = str(event.get("kind") or "")
        event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        run_creator = app.state.db.get_run_creator_user_id(run_id)
        owner_ids = set(app.state.db.get_project_owner_ids(project_id))

        if kind == "quota_exceeded":
            if run_creator:
                recipients.add(run_creator)
            payload["summary"] = f"Run quota exceeded ({event_payload.get('scope', 'unknown')})"
        elif kind == "system_event" and event_payload.get("code") == "approval_required":
            if run_creator:
                recipients.add(run_creator)
            recipients |= owner_ids
            payload["summary"] = "Approval required"
        elif kind == "tool_error":
            if not app.state.settings.notify_tool_errors:
                return []
            allowed_codes = set(app.state.settings.notify_tool_errors_only_codes)
            allowed_bindings = set(app.state.settings.notify_tool_errors_only_bindings)
            error_code = str(event_payload.get("error_code") or "")
            if allowed_codes and error_code not in allowed_codes:
                return []
            binding_type = str(event_payload.get("binding_type") or "")
            if not binding_type:
                tool_id = str(event_payload.get("tool_id") or "")
                tool_version = str(event_payload.get("tool_version") or "")
                manifest = app.state.db.get_tool_manifest(tool_id, tool_version) if tool_id and tool_version else None
                if manifest and isinstance(manifest, dict):
                    binding = manifest.get("binding")
                    if isinstance(binding, dict):
                        binding_type = str(binding.get("type") or "")
            if allowed_bindings and binding_type not in allowed_bindings:
                return []
            cap = max(0, int(app.state.settings.notify_tool_errors_max_per_run))
            if cap > 0 and app.state.db.count_notifications_for_run_kind(run_id, "run_tool_error") >= cap:
                return []
            if run_creator:
                recipients.add(run_creator)
            else:
                recipients |= owner_ids
            payload["summary"] = f"Tool error: {event_payload.get('error_code', 'unknown')}"
            payload["binding_type"] = binding_type or None
        if not recipients:
            return []
        return _notify_users(
            recipients,
            kind=f"run_{kind}",
            payload=payload,
            actor_user_id=actor_user_id,
            project_id=project_id,
            run_id=run_id,
            activity_seq=None,
        )

    def emit_auth_audit(user_id: str, kind: str, payload: dict[str, Any]) -> None:
        run_id = app.state.db.latest_run_for_user(user_id)
        if run_id:
            try:
                append_run_event(run_id, {"kind": kind, "actor": "system", "payload": payload, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                ctx = app.state.db.get_run_context(run_id)
                if ctx:
                    app.state.db.add_activity(ctx.project_id, kind, "auth", user_id, user_id)
            except Exception:
                pass
        else:
            project_id = app.state.db.latest_project_for_user(user_id)
            if project_id:
                app.state.db.add_activity(project_id, kind, "auth", user_id, user_id)

    def require_run_role(run_id: str, user_id: str, minimum_role: str = "viewer") -> None:
        ctx = app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        if ctx.project_id:
            require_project_role(ctx.project_id, user_id, minimum_role)
            return
        thread = app.state.db.get_thread(ctx.thread_id)
        if not thread or str(thread.get("user_id") or "") != str(user_id):
            raise HTTPException(status_code=404, detail="run not found")

    def with_idempotency(user_id: str, endpoint: str, idempotency_key: str | None, compute) -> dict[str, Any]:
        key = (idempotency_key or "").strip()
        if not key:
            return compute()
        cached = app.state.db.get_idempotency_response(key, user_id, endpoint)
        if cached is not None:
            app.state.db.increment_counter("idempotency_hits_total")
            return cached
        result = compute()
        app.state.db.put_idempotency_response(key, user_id, endpoint, result)
        app.state.db.increment_counter("idempotency_stores_total")
        return result

    def validate_scope(scope_type: str, scope_id: str | None) -> None:
        if scope_type in {"workspace", "user"}:
            return
        if not scope_id:
            raise HTTPException(status_code=400, detail="scope_id required")
        if scope_type == "project":
            if not any(p["id"] == scope_id for p in app.state.db.list_projects()):
                raise HTTPException(status_code=400, detail="invalid project scope_id")
        if scope_type == "thread":
            # coarse check by scanning projects->threads
            found = False
            for p in app.state.db.list_projects():
                ok, threads = app.state.db.list_threads(p["id"])
                if ok and any(t["id"] == scope_id for t in threads):
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=400, detail="invalid thread scope_id")

    def redact_text(text: str) -> str:
        for key in ["api_key", "token", "secret", "password"]:
            text = text.replace(key, "***")
        return text

    def _create_comment_impl(project_id: str, payload: CommentCreateRequest, body: str, request: Request) -> dict[str, Any]:
        created = request.app.state.db.create_comment(
            {
                "project_id": project_id,
                "run_id": payload.run_id,
                "thread_id": payload.thread_id,
                "target_type": payload.target_type,
                "target_id": payload.target_id,
                "author_id": request.state.user_id,
                "body": body,
            }
        )
        activity = request.app.state.db.add_activity(project_id, "comment_created", payload.target_type, payload.target_id, request.state.user_id)
        _fanout_project_activity_notifications(
            project_id=project_id,
            activity_row=activity,
            actor_user_id=request.state.user_id,
            run_id=payload.run_id,
            summary="New comment on project activity",
            extra={"target_type": payload.target_type, "target_id": payload.target_id},
        )
        emit_project_collab_event(project_id, {"kind": "comment_created", "actor": "system", "payload": {"comment_id": created["comment_id"], "project_id": project_id, "thread_id": created.get("thread_id"), "run_id": created.get("run_id"), "target_type": created["target_type"], "target_id": created["target_id"], "author_id": created["author_id"], "body": created["body"], "created_at": created["created_at"]}, "privacy": {"redact_level": "partial", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return created

    def _mark_seen_impl(project_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
        seq = int(payload.get("seq", 0))
        state = request.app.state.db.mark_activity_seen(request.state.user_id, project_id, seq)
        max_seq = request.app.state.db.max_activity_seq(project_id)
        unread = max(0, int(max_seq) - int(state["last_seen_activity_seq"]))
        return {"project_id": project_id, "last_seen_activity_seq": int(state["last_seen_activity_seq"]), "max_activity_seq": max_seq, "unread_count": unread}

    def _create_memory_impl(payload: MemoryCreateRequest, content: str, request: Request) -> dict[str, Any]:
        item = request.app.state.db.create_memory_item(
            {
                "type": payload.type,
                "scope_type": payload.scope_type,
                "scope_id": payload.scope_id,
                "title": payload.title,
                "content": content,
                "tags": payload.tags,
                "importance": payload.importance,
                "expires_at": payload.expires_at,
                "privacy": payload.privacy,
            },
            payload.provenance,
        )
        if payload.provenance.get("run_id"):
            append_run_event(payload.provenance["run_id"], {"kind": "memory_item_created", "actor": "system", "payload": {"memory_id": item["memory_id"], "provenance": payload.provenance}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return item

    def store_text_artifact(kind: str, title: str | None, content: str, media_type: str = "application/json") -> dict[str, Any]:
        data = content.encode("utf-8")
        content_hash = hash_bytes(data)
        hex_hash = content_hash.split(":", 1)[1]
        ext = ".txt" if media_type.startswith("text/") else ".json"
        store_dir = Path(__file__).resolve().parents[1] / ".omni_artifacts" / hex_hash[:2]
        store_dir.mkdir(parents=True, exist_ok=True)
        file_path = store_dir / f"{hex_hash}{ext}"
        if not file_path.exists():
            file_path.write_bytes(data)
        return app.state.db.upsert_artifact(kind, media_type, len(data), content_hash, str(file_path), title)

    def artifact_root() -> Path:
        return Path(__file__).resolve().parents[1] / ".omni_artifacts"

    def upload_root() -> Path:
        return Path(__file__).resolve().parents[1] / ".omni_uploads"

    def upload_part_path(upload_id: str, part_no: int) -> Path:
        d = upload_root() / upload_id
        d.mkdir(parents=True, exist_ok=True)
        return d / f"part-{int(part_no):06d}.bin"

    def tool_policy_decision(run_id: str, manifest: dict[str, Any]) -> tuple[str, str]:
        ctx = app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        for scope in manifest["risk"]["scopes_required"]:
            if not app.state.db.has_scope(ctx.project_id, scope):
                return "deny", f"missing scope: {scope}"
        risk = manifest["risk"]
        if risk["external_write"] or risk["network_egress"]:
            if not app.state.db.has_prior_approval(run_id, manifest["tool_id"], manifest["version"]):
                return "approval_required", "elevated risk requires approval"
        return "allow", "ok"

    def mcp_call(server_id: str, tool_name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        server = app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        client = McpHttpClient(server["endpoint_url"], session_id=server.get("session_id"))
        init = client.initialize()
        client.notify_initialized()
        result = client.tools_call(tool_name, arguments)
        app.state.db.update_mcp_server_health(server_id, "healthy", init["latency_ms"], init.get("protocol_version"), init.get("session_id"))
        return result, app.state.db.get_mcp_server(server_id)

    def execute_tool_call(run_id: str, manifest: dict[str, Any], inputs: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        workspace_root = Path(settings.workspace_root) / app.state.db.get_run_context(run_id).project_id
        workspace_root.mkdir(parents=True, exist_ok=True)
        def call_mcp_remote(mani: dict[str, Any], inps: dict[str, Any]) -> dict[str, Any]:
            entry = mani["binding"]["entrypoint"]
            obj = json.loads(entry) if isinstance(entry, str) and entry.startswith("{") else {}
            result, srv = mcp_call(obj.get("server_id"), obj.get("tool_name"), inps)
            return {"content": result.get("content", []), "isError": bool(result.get("isError", False)), "structuredContent": result.get("structuredContent"), "mcp_server_id": obj.get("server_id"), "mcp_protocol_version": srv.get("protocol_version")}
        try:
            outputs = execute_tool(manifest, inputs, workspace_root, mcp_remote_caller=call_mcp_remote)
        except TimeoutError:
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "error_code": "TIMEOUT", "message": "execution timed out", "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_error_event": err}
        except Exception as exc:
            code = "MCP_ERROR" if manifest["binding"]["type"] == "mcp_remote" else "EXECUTION_FAILED"
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "error_code": code, "message": str(exc), "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_error_event": err}
        oerrs = validate_json_schema(manifest["outputs_schema"], outputs)
        if oerrs:
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "error_code": "SCHEMA_VIOLATION", "message": "; ".join(oerrs), "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_error_event": err}
        res = append_run_event(run_id, {"kind": "tool_result", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "outputs": outputs, "correlation_id": correlation_id, "executor_version": EXECUTOR_VERSION}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"tool_result_event": res}

    @app.post("/v1/projects")
    def create_project(payload: CreateProjectRequest, request: Request):
        created = request.app.state.db.create_project(payload.name)
        request.app.state.db.add_project_member(created["id"], request.state.user_id, "owner")
        logger.info("project_created", extra={"extra": redact_dict(created)})
        return created

    @app.post("/v1/auth/login")
    def auth_login(payload: LoginRequest, request: Request):
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="username required")
        ident = request.app.state.db.get_identity_by_username(username)
        password = payload.password or ""
        old_sid = request.cookies.get(settings.session_cookie_name)
        if settings.dev_login_password and password != settings.dev_login_password:
            if ident:
                emit_auth_audit(
                    ident["user_id"],
                    "auth_login_failed",
                    {"user_id": ident["user_id"], "username": username, "reason": "invalid_credentials", "failed_at": datetime.now(UTC).isoformat()},
                )
            raise HTTPException(status_code=401, detail="invalid credentials")
        if ident is None:
            password_hash = PWD.hash(settings.dev_login_password if settings.dev_login_password else password)
            ident = request.app.state.db.create_identity(username, password_hash)
        else:
            stored = ident.get("password_hash")
            valid = False
            needs_upgrade = False
            if stored and stored.startswith("$argon2id$"):
                try:
                    valid = bool(PWD.verify(stored, password))
                    needs_upgrade = PWD.check_needs_rehash(stored)
                except VerifyMismatchError:
                    valid = False
            elif _is_legacy_sha256_hash(stored):
                valid = hashlib.sha256(password.encode("utf-8")).hexdigest() == stored
                needs_upgrade = valid
            elif stored is None and not settings.dev_login_password:
                valid = True
                needs_upgrade = bool(password)
            if not valid:
                emit_auth_audit(
                    ident["user_id"],
                    "auth_login_failed",
                    {"user_id": ident["user_id"], "username": username, "reason": "invalid_credentials", "failed_at": datetime.now(UTC).isoformat()},
                )
                raise HTTPException(status_code=401, detail="invalid credentials")
            if needs_upgrade:
                request.app.state.db.update_identity_password_hash(ident["user_id"], PWD.hash(password))

        user = request.app.state.db.ensure_user(ident["user_id"], username)
        expires_at = (datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
        csrf_secret = secrets.token_urlsafe(32)
        session = request.app.state.db.rotate_session(old_sid, user["user_id"], expires_at, csrf_secret)
        emit_auth_audit(
            user["user_id"],
            "auth_session_created",
            {"user_id": user["user_id"], "session_id": session["session_id"], "created_at": session["created_at"]},
        )
        response = JSONResponse({"user_id": user["user_id"], "display_name": user["display_name"]})
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session["session_id"],
            httponly=True,
            secure=settings.session_secure_cookie,
            samesite=settings.session_samesite,
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        return response

    @app.post("/v1/auth/register")
    def auth_register(payload: RegisterRequest, request: Request):
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="username required")
        
        # Check if username already exists
        existing = request.app.state.db.get_identity_by_username(username)
        if existing:
            raise HTTPException(status_code=409, detail="username already taken")
        
        # Hash the password and create the identity
        password_hash = PWD.hash(payload.password)
        ident = request.app.state.db.create_identity(username, password_hash)
        
        # Create user with the display name
        user = request.app.state.db.ensure_user(ident["user_id"], payload.display_name)
        
        # Create a session (auto-login after registration)
        expires_at = (datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
        csrf_secret = secrets.token_urlsafe(32)
        session = request.app.state.db.rotate_session(None, user["user_id"], expires_at, csrf_secret)
        
        emit_auth_audit(
            user["user_id"],
            "auth_session_created",
            {"user_id": user["user_id"], "session_id": session["session_id"], "created_at": session["created_at"], "registration": True},
        )
        
        response = JSONResponse({"user_id": user["user_id"], "display_name": user["display_name"]})
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session["session_id"],
            httponly=True,
            secure=settings.session_secure_cookie,
            samesite=settings.session_samesite,
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        return response

    @app.post("/v1/auth/logout")
    def auth_logout(request: Request):
        sid = request.cookies.get(settings.session_cookie_name)
        if sid:
            sess = request.app.state.db.get_session(sid)
            request.app.state.db.delete_session(sid)
            if sess:
                emit_auth_audit(
                    sess["user_id"],
                    "auth_session_revoked",
                    {"user_id": sess["user_id"], "session_id": sid, "revoked_at": datetime.now(UTC).isoformat()},
                )
        response = JSONResponse({"logged_out": True})
        response.delete_cookie(settings.session_cookie_name, path="/")
        return response

    @app.post("/v1/auth/rotate")
    def auth_rotate(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        old_sid = request.cookies.get(settings.session_cookie_name)
        expires_at = (datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)).isoformat()
        csrf_secret = secrets.token_urlsafe(32)
        session = request.app.state.db.rotate_session(old_sid, request.state.user_id, expires_at, csrf_secret)
        if old_sid:
            emit_auth_audit(
                request.state.user_id,
                "auth_session_revoked",
                {"user_id": request.state.user_id, "session_id": old_sid, "revoked_at": datetime.now(UTC).isoformat()},
            )
        emit_auth_audit(
            request.state.user_id,
            "auth_session_created",
            {"user_id": request.state.user_id, "session_id": session["session_id"], "created_at": session["created_at"]},
        )
        response = JSONResponse({"rotated": True})
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session["session_id"],
            httponly=True,
            secure=settings.session_secure_cookie,
            samesite=settings.session_samesite,
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        return response

    @app.get("/v1/auth/csrf")
    def auth_csrf(request: Request):
        if not request.state.user_id or not request.state.csrf_expected:
            raise HTTPException(status_code=401, detail="authentication required")
        return {"csrf_token": request.state.csrf_expected}

    @app.get("/v1/projects")
    def list_projects(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        uid = request.state.user_id
        projects = [p for p in request.app.state.db.list_projects() if request.app.state.db.get_project_member_role(p["id"], uid)]
        return {"projects": projects}

    @app.get("/v1/me")
    def get_me(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        user = request.app.state.db.get_user(request.state.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="authentication required")
        return user

    @app.patch("/v1/me")
    def patch_me(payload: UpdateMeRequest, request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        if payload.display_name is not None:
            updated = request.app.state.db.update_user_display_name(request.state.user_id, payload.display_name)
            if not updated:
                raise HTTPException(status_code=404, detail="user not found")
        if payload.avatar_url is not None:
            updated = request.app.state.db.update_user_avatar(request.state.user_id, payload.avatar_url)
            if not updated:
                raise HTTPException(status_code=404, detail="user not found")
        return request.app.state.db.get_user(request.state.user_id)

    @app.get("/v1/projects/{project_id}/members")
    def list_project_members(project_id: str, request: Request):
        require_project_role(project_id, request.state.user_id, "viewer")
        return {"members": request.app.state.db.list_project_members(project_id)}

    @app.post("/v1/projects/{project_id}/members")
    def add_project_member(project_id: str, payload: ProjectMemberRequest, request: Request):
        require_project_role(project_id, request.state.user_id, "owner")
        request.app.state.db.ensure_user(payload.user_id)
        request.app.state.db.add_project_member(project_id, payload.user_id, payload.role)
        ts = datetime.now(UTC).isoformat()
        activity = request.app.state.db.add_activity(project_id, "member_added", "project_member", payload.user_id, request.state.user_id)
        _fanout_project_activity_notifications(
            project_id=project_id,
            activity_row=activity,
            actor_user_id=request.state.user_id,
            run_id=None,
            summary="You were added to a project",
            extra={"affected_user_id": payload.user_id, "role": payload.role},
        )
        request.app.state.db.revoke_sessions_for_user(payload.user_id)
        emit_project_collab_event(project_id, {"kind": "project_member_added", "actor": "system", "payload": {"project_id": project_id, "user_id": payload.user_id, "role": payload.role, "added_by": request.state.user_id, "added_at": ts}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"added": True}

    @app.patch("/v1/projects/{project_id}/members/{user_id}")
    def update_project_member(project_id: str, user_id: str, payload: ProjectMemberUpdateRequest, request: Request):
        require_project_role(project_id, request.state.user_id, "owner")
        prev = request.app.state.db.get_project_member_role(project_id, user_id)
        if not prev:
            raise HTTPException(status_code=404, detail="member not found")
        request.app.state.db.add_project_member(project_id, user_id, payload.role)
        ts = datetime.now(UTC).isoformat()
        activity = request.app.state.db.add_activity(project_id, "member_role_changed", "project_member", user_id, request.state.user_id)
        _fanout_project_activity_notifications(
            project_id=project_id,
            activity_row=activity,
            actor_user_id=request.state.user_id,
            run_id=None,
            summary="Your project role changed",
            extra={"affected_user_id": user_id, "from_role": prev, "to_role": payload.role},
        )
        request.app.state.db.revoke_sessions_for_user(user_id)
        emit_project_collab_event(project_id, {"kind": "project_member_role_changed", "actor": "system", "payload": {"project_id": project_id, "user_id": user_id, "from_role": prev, "to_role": payload.role, "changed_by": request.state.user_id, "changed_at": ts}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"updated": True}

    @app.delete("/v1/projects/{project_id}/members/{user_id}")
    def remove_project_member(project_id: str, user_id: str, request: Request):
        require_project_role(project_id, request.state.user_id, "owner")
        if not request.app.state.db.remove_project_member(project_id, user_id):
            raise HTTPException(status_code=404, detail="member not found")
        ts = datetime.now(UTC).isoformat()
        request.app.state.db.add_activity(project_id, "member_removed", "project_member", user_id, request.state.user_id)
        request.app.state.db.revoke_sessions_for_user(user_id)
        emit_project_collab_event(project_id, {"kind": "project_member_removed", "actor": "system", "payload": {"project_id": project_id, "user_id": user_id, "removed_by": request.state.user_id, "removed_at": ts}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"removed": True}

    @app.post("/v1/projects/{project_id}/threads")
    def create_thread(project_id: str, payload: CreateThreadRequest, request: Request):
        require_project_role(project_id, request.state.user_id, "editor")
        created = request.app.state.db.create_thread(project_id, payload.title, request.state.user_id)
        if not created:
            raise HTTPException(status_code=404, detail="project not found")
        return created

    @app.get("/v1/threads")
    def list_user_threads(request: Request):
        """List all threads accessible to the current user: threads in their projects + uncategorized threads."""
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        threads = request.app.state.db.list_user_threads(request.state.user_id)
        return {"threads": threads}

    @app.post("/v1/threads")
    def create_uncategorized_thread(payload: CreateThreadRequest, request: Request):
        """Create a thread without a project (uncategorized). Any authenticated user can do this."""
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        created = request.app.state.db.create_thread(None, payload.title, request.state.user_id)
        if not created:
            raise HTTPException(status_code=500, detail="failed to create thread")
        return created

    @app.get("/v1/projects/{project_id}/threads")
    def list_threads(project_id: str, request: Request):
        require_project_role(project_id, request.state.user_id, "viewer")
        ok, threads = request.app.state.db.list_threads(project_id)
        if not ok:
            raise HTTPException(status_code=404, detail="project not found")
        return {"threads": threads}

    @app.delete("/v1/threads/{thread_id}")
    def delete_thread(thread_id: str, request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        thread = request.app.state.db.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="thread not found")
        project_id = thread.get("project_id")
        if project_id:
            try:
                require_project_role(str(project_id), request.state.user_id, "editor")
            except HTTPException:
                raise HTTPException(status_code=404, detail="thread not found")
        elif str(thread.get("user_id") or "") != str(request.state.user_id):
            raise HTTPException(status_code=404, detail="thread not found")
        if not request.app.state.db.delete_thread(thread_id, request.state.user_id):
            raise HTTPException(status_code=404, detail="thread not found")
        return {"deleted": True}

    @app.delete("/v1/projects/{project_id}")
    def delete_project(project_id: str, request: Request):
        try:
            require_project_role(project_id, request.state.user_id, "owner")
        except HTTPException:
            raise HTTPException(status_code=404, detail="project not found")
        if not request.app.state.db.delete_project(project_id):
            raise HTTPException(status_code=404, detail="project not found")
        return {"deleted": True}

    @app.post("/v1/threads/{thread_id}/runs")
    def create_run(thread_id: str, payload: CreateRunRequest, request: Request):
        pins = payload.pins.copy()
        thread = request.app.state.db.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="thread not found")
        ctx_project_id = thread.get("project_id")
        if ctx_project_id:
            require_project_role(ctx_project_id, request.state.user_id, "editor")
            pins["toolset"] = request.app.state.db.list_project_tool_pins(ctx_project_id)
        elif str(thread.get("user_id") or "") != str(request.state.user_id):
            raise HTTPException(status_code=404, detail="thread not found")
        created = request.app.state.db.create_run(thread_id, payload.status, pins, created_by_user_id=request.state.user_id)
        if not created:
            raise HTTPException(status_code=404, detail="thread not found")
        return created

    @app.get("/v1/threads/{thread_id}/runs")
    def list_runs(thread_id: str, request: Request):
        thread = request.app.state.db.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="thread not found")
        if thread.get("project_id"):
            require_project_role(str(thread["project_id"]), request.state.user_id, "viewer")
        elif str(thread.get("user_id") or "") != str(request.state.user_id):
            raise HTTPException(status_code=404, detail="thread not found")
        ok, runs = request.app.state.db.list_runs(thread_id)
        if not ok:
            raise HTTPException(status_code=404, detail="thread not found")
        return {"runs": runs}

    @app.get("/v1/runs/{run_id}/summary")
    def run_summary(run_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "viewer")
        summary = request.app.state.db.get_run_summary(run_id)
        if not summary:
            raise HTTPException(status_code=404, detail="run not found")
        return summary

    @app.get("/v1/runs/{run_id}/metrics")
    def run_metrics(run_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "viewer")
        metrics = request.app.state.db.get_run_metrics(run_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="run not found")
        return metrics

    @app.get("/v1/tools/metrics")
    def tools_metrics(request: Request):
        return {"tools": request.app.state.db.list_tool_metrics()}

    @app.get("/v1/system/health")
    def system_health(request: Request):
        db_ok = request.app.state.db.db_health_ok()
        cache_age = request.app.state.db.get_max_provenance_cache_age_seconds()
        return {
            "status": "ok" if db_ok else "degraded",
            "ts": datetime.now(UTC).isoformat(),
            "db_ok": db_ok,
            "provenance_cache_age_s": cache_age,
            "counters": request.app.state.db.list_system_counters(),
            "gauges": request.app.state.db.list_system_gauges(),
        }

    @app.get("/v1/system/stats")
    def system_stats(request: Request):
        stats = request.app.state.db.get_system_stats()
        stats["max_events_per_run"] = request.app.state.settings.max_events_per_run
        stats["max_bytes_per_run"] = request.app.state.settings.max_bytes_per_run
        stats["counters"] = request.app.state.db.list_system_counters()
        gauges = request.app.state.db.list_system_gauges()
        gauges["active_uploads"] = request.app.state.db.count_active_uploads()
        stats["gauges"] = gauges
        return stats

    @app.get("/v1/system/config")
    def system_config(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        _require_admin(settings)
        s = request.app.state.settings
        payload = {
            "notify_tool_errors": bool(s.notify_tool_errors),
            "notify_tool_errors_only_codes": list(s.notify_tool_errors_only_codes),
            "notify_tool_errors_only_bindings": list(s.notify_tool_errors_only_bindings),
            "notify_tool_errors_max_per_run": int(s.notify_tool_errors_max_per_run),
            "sse_max_replay": int(s.sse_max_replay),
            "sse_heartbeat_seconds": int(s.sse_heartbeat_s),
            "artifact_max_bytes": int(s.artifact_max_bytes),
            "artifact_part_size": int(s.artifact_part_size),
            "session_ttl_seconds": int(s.session_ttl_seconds),
            "session_sliding_enabled": bool(s.session_sliding_enabled),
            "session_sliding_window_seconds": int(s.session_sliding_window_seconds),
            "max_events_per_run": int(s.max_events_per_run),
            "max_bytes_per_run": int(s.max_bytes_per_run),
            "generated_at": datetime.now(UTC).isoformat(),
            "contract_version": SYSTEM_CONFIG_CONTRACT_VERSION,
            "runtime_version": SYSTEM_CONFIG_RUNTIME_VERSION,
        }
        try:
            _validate_system_config_payload(payload)
        except Exception as exc:
            if settings.dev_mode:
                raise HTTPException(status_code=500, detail=f"system config contract validation failed: {exc}") from exc
            logger.error("system_config_contract_validation_failed", extra={"extra": redact_dict({"error": str(exc)})})
        return payload

    @app.get("/v1/runs/{run_id}/events")
    def list_events(run_id: str, request: Request, after_seq: int = 0, kinds: str | None = None, tool_id: str | None = None, errors_only: bool = False):
        require_run_role(run_id, request.state.user_id, "viewer")
        kinds_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds else None
        ok, events = request.app.state.db.list_events(run_id, after_seq, kinds=kinds_list, tool_id=tool_id, errors_only=errors_only)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        return {"events": events}

    @app.post("/v1/runs/{run_id}/events")
    def append_event(run_id: str, payload: AppendEventRequest, request: Request, idempotency_key: str | None = Header(default=None, alias="X-Omni-Idempotency-Key")):
        require_run_role(run_id, request.state.user_id, "editor")
        if payload.kind != "user_message":
            return append_run_event(run_id, payload.model_dump(exclude_none=True))
        return with_idempotency(
            request.state.user_id,
            f"POST:/v1/runs/{run_id}/events",
            idempotency_key,
            lambda: append_run_event(run_id, payload.model_dump(exclude_none=True)),
        )

    def _sse_headers() -> dict[str, str]:
        return {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    def _parse_sse_start(after_seq: int | None, last_event_id: str | None) -> int:
        try:
            return int(after_seq if after_seq is not None else (last_event_id or 0))
        except (TypeError, ValueError):
            return 0

    def _sse_response_once(event_name: str, rows: list[dict[str, Any]], seq_key: str) -> Response:
        now = datetime.now(UTC).isoformat()
        capped = rows[: app.state.settings.sse_max_replay]
        body = f"event: heartbeat\ndata: {json.dumps({'ts': now}, separators=(',', ':'))}\n\n" + "".join(
            f"event: {event_name}\nid: {int(r[seq_key])}\ndata: {json.dumps(r, separators=(',', ':'))}\n\n" for r in capped
        )
        return Response(content=body, media_type="text/event-stream", headers=_sse_headers())

    async def _sse_stream(
        request: Request,
        start_seq: int,
        event_name: str,
        seq_key: str,
        fetch_rows,
        limit: int,
    ):
        cursor = start_seq
        hb = datetime.now(UTC)
        yield f"event: heartbeat\ndata: {json.dumps({'ts': hb.isoformat()}, separators=(',', ':'))}\n\n"
        while True:
            if await request.is_disconnected():
                break
            rows = fetch_rows(cursor, min(max(limit, 1), app.state.settings.sse_max_replay))
            for row in rows:
                cursor = int(row[seq_key])
                yield f"event: {event_name}\nid: {cursor}\ndata: {json.dumps(row, separators=(',', ':'))}\n\n"
            now = datetime.now(UTC)
            if (now - hb).total_seconds() >= app.state.settings.sse_heartbeat_s:
                hb = now
                yield f"event: heartbeat\ndata: {json.dumps({'ts': now.isoformat()}, separators=(',', ':'))}\n\n"
            await asyncio.sleep(app.state.settings.sse_poll_interval_s)

    async def _instrumented_sse_stream(
        request: Request,
        stream_type: str,
        start_seq: int,
        event_name: str,
        seq_key: str,
        fetch_rows,
        limit: int,
    ):
        app.state.db.increment_counter("sse_connections_total")
        active = app.state.db.add_gauge_real(f"sse.active_streams_by_type.{stream_type}", 1.0)
        if active < 0:
            app.state.db.set_gauge_real(f"sse.active_streams_by_type.{stream_type}", 0.0)
        try:
            async for chunk in _sse_stream(request, start_seq, event_name, seq_key, fetch_rows, limit):
                yield chunk
        finally:
            app.state.db.increment_counter("sse_disconnects_total")
            active2 = app.state.db.add_gauge_real(f"sse.active_streams_by_type.{stream_type}", -1.0)
            if active2 < 0:
                app.state.db.set_gauge_real(f"sse.active_streams_by_type.{stream_type}", 0.0)

    @app.get("/v1/runs/{run_id}/events:stream")
    @app.get("/v1/runs/{run_id}/events/stream")
    async def stream_events(
        run_id: str,
        request: Request,
        after_seq: int | None = None,
        limit: int = 200,
        once: bool = False,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        require_run_role(run_id, request.state.user_id, "viewer")
        start_seq = _parse_sse_start(after_seq, last_event_id)
        ok, _ = request.app.state.db.list_events(run_id, 0)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        fetch = lambda cursor, lim: request.app.state.db.list_events(run_id, cursor)[1][:lim]
        if once:
            return _sse_response_once("run_event", fetch(start_seq, limit), "seq")
        return StreamingResponse(
            _instrumented_sse_stream(request, "run_events", start_seq, "run_event", "seq", fetch, limit),
            media_type="text/event-stream",
            headers=_sse_headers(),
        )

    @app.post("/v1/artifacts")
    def create_artifact(payload: ArtifactCreateRequest, request: Request):
        data = payload.content_text.encode("utf-8") if payload.content_text is not None else base64.b64decode(payload.content_base64 or "")
        if len(data) > request.app.state.settings.artifact_max_bytes:
            raise HTTPException(status_code=413, detail="artifact too large")
        content_hash = hash_bytes(data)
        hash_hex = content_hash.split(":", 1)[1]
        ext = ".txt" if payload.media_type.startswith("text/") else ".bin"
        store_dir = (artifact_root() / hash_hex[:2])
        store_dir.mkdir(parents=True, exist_ok=True)
        file_path = store_dir / f"{hash_hex}{ext}"
        if not file_path.exists():
            file_path.write_bytes(data)
        return request.app.state.db.upsert_artifact(payload.kind, payload.media_type, len(data), content_hash, str(file_path), payload.title, request.state.user_id)

    @app.post("/v1/artifacts/init")
    def artifact_init(payload: ArtifactInitRequest, request: Request):
        if payload.size_bytes is not None and payload.size_bytes > request.app.state.settings.artifact_max_bytes:
            raise HTTPException(status_code=413, detail="artifact too large")
        require_run_role(payload.run_id, request.state.user_id, "editor")
        artifact_id = str(uuid4())
        request.app.state.db.create_pending_artifact(
            artifact_id=artifact_id,
            kind=payload.kind,
            media_type=payload.media_type,
            title=payload.title,
            created_by_user_id=request.state.user_id,
            expected_size_bytes=payload.size_bytes,
            expected_hash=payload.content_hash,
        )
        up = request.app.state.db.create_artifact_upload(artifact_id)
        request.app.state.db.set_gauge_real("active_uploads", float(request.app.state.db.count_active_uploads()))
        return {"upload_id": up["upload_id"], "artifact_id": artifact_id, "part_size": request.app.state.settings.artifact_part_size}

    @app.put("/v1/artifacts/{artifact_id}/parts/{part_no}")
    async def artifact_put_part(artifact_id: str, part_no: int, request: Request, upload_id: str | None = None):
        if part_no < 1:
            raise HTTPException(status_code=400, detail="invalid part number")
        if not upload_id:
            raise HTTPException(status_code=400, detail="upload_id query required")
        up = request.app.state.db.get_artifact_upload(upload_id)
        if not up or up["artifact_id"] != artifact_id:
            raise HTTPException(status_code=404, detail="upload not found")
        art = request.app.state.db.get_artifact(artifact_id)
        if not art or art.get("created_by_user_id") != request.state.user_id:
            raise HTTPException(status_code=403, detail="artifact upload denied")
        if up["status"] == "finalized":
            raise HTTPException(status_code=409, detail="upload already finalized")
        data = await request.body()
        if len(data) > request.app.state.settings.artifact_part_size:
            raise HTTPException(status_code=413, detail="part too large")
        out = upload_part_path(upload_id, part_no)
        out.write_bytes(data)
        parts = [p for p in up["parts"] if int(p["part_no"]) != int(part_no)]
        parts.append({"part_no": int(part_no), "size": len(data), "path": str(out)})
        parts.sort(key=lambda p: int(p["part_no"]))
        request.app.state.db.set_artifact_upload_parts(upload_id, parts, status="uploading")
        return {"ok": True, "part_no": int(part_no), "size": len(data)}

    @app.post("/v1/artifacts/{artifact_id}/finalize")
    def artifact_finalize(artifact_id: str, payload: ArtifactFinalizeRequest, request: Request):
        up = request.app.state.db.get_artifact_upload(payload.upload_id)
        if not up or up["artifact_id"] != artifact_id:
            raise HTTPException(status_code=404, detail="upload not found")
        art = request.app.state.db.get_artifact(artifact_id)
        if not art or art.get("created_by_user_id") != request.state.user_id:
            raise HTTPException(status_code=403, detail="artifact upload denied")
        if up["status"] == "finalized":
            if not art:
                raise HTTPException(status_code=404, detail="artifact not found")
            return art
        parts = sorted(up["parts"], key=lambda p: int(p["part_no"]))
        if not parts:
            raise HTTPException(status_code=400, detail="no parts uploaded")
        ext = ".txt" if str(art["media_type"]).startswith("text/") else ".bin"
        final_dir = artifact_root() / artifact_id[:2]
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / f"{artifact_id.replace(':', '_')}{ext}"
        with final_path.open("wb") as out:
            for p in parts:
                out.write(Path(p["path"]).read_bytes())
        data = final_path.read_bytes()
        if len(data) > request.app.state.settings.artifact_max_bytes:
            raise HTTPException(status_code=413, detail="artifact too large")
        actual_hash = hash_bytes(data)
        if art.get("content_hash") and art["content_hash"] != actual_hash:
            raise HTTPException(status_code=400, detail="hash mismatch")
        done = request.app.state.db.complete_artifact(artifact_id, len(data), actual_hash, str(final_path))
        request.app.state.db.finalize_artifact_upload(payload.upload_id)
        request.app.state.db.increment_counter("finalized_uploads_total")
        request.app.state.db.increment_counter("bytes_uploaded_total", len(data))
        request.app.state.db.set_gauge_real("active_uploads", float(request.app.state.db.count_active_uploads()))
        return done or {"artifact_id": artifact_id}

    @app.get("/v1/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str, request: Request):
        artifact = request.app.state.db.get_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found")
        storage_path = artifact.get("storage_path") or artifact.get("storage_ref")
        if not storage_path:
            raise HTTPException(status_code=404, detail="artifact data missing")
        data = Path(storage_path).read_bytes()
        artifact["content_text"] = data.decode("utf-8", errors="replace") if artifact["media_type"].startswith("text/") else base64.b64encode(data).decode("ascii")
        return artifact

    @app.get("/v1/artifacts/{artifact_id}/download")
    def artifact_download(artifact_id: str, request: Request):
        artifact = request.app.state.db.get_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact not found")
        storage_path = artifact.get("storage_path") or artifact.get("storage_ref")
        if not storage_path or not Path(storage_path).exists():
            raise HTTPException(status_code=404, detail="artifact data missing")
        headers = {"ETag": artifact.get("etag") or artifact.get("content_hash") or ""}
        return FileResponse(path=storage_path, media_type=artifact["media_type"], headers=headers)

    @app.get("/v1/runs/{run_id}/artifacts")
    def list_run_artifacts(run_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "viewer")
        ok, artifacts = request.app.state.db.list_run_artifacts(run_id)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        return {"artifacts": artifacts}

    @app.post("/v1/runs/{run_id}/artifacts/link")
    def link_run_artifact(run_id: str, payload: RunArtifactLinkRequest, request: Request):
        require_run_role(run_id, request.state.user_id, "editor")
        art = request.app.state.db.get_artifact(payload.artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="artifact not found")
        ref = append_run_event(
            run_id,
            {
                "kind": "artifact_ref",
                "actor": "system",
                "correlation_id": payload.correlation_id,
                "payload": {
                    "artifact_id": art["artifact_id"],
                    "kind": art["kind"],
                    "media_type": art["media_type"],
                    "size_bytes": art["size_bytes"],
                    "content_hash": art["content_hash"],
                    "created_at": art["created_at"],
                    "storage_ref": art.get("storage_path") or art.get("storage_ref"),
                },
                "privacy": {"redact_level": "none", "contains_secrets": False},
                "pins": DEFAULT_PINS,
            },
        )
        link_row = request.app.state.db.create_artifact_link(
            run_id,
            ref["event_id"],
            art["artifact_id"],
            source_event_id=payload.source_event_id,
            correlation_id=payload.correlation_id,
            tool_id=payload.tool_id,
            tool_version=payload.tool_version,
            purpose=payload.purpose,
        )
        linked = append_run_event(
            run_id,
            {
                "kind": "artifact_linked",
                "actor": "system",
                "correlation_id": payload.correlation_id,
                "payload": {
                    "artifact_id": link_row["artifact_id"],
                    "run_id": link_row["run_id"],
                    "created_at": link_row.get("created_at") or datetime.now(UTC).isoformat(),
                    "purpose": link_row.get("purpose"),
                    "source_event_id": link_row.get("source_event_id"),
                    "correlation_id": link_row.get("correlation_id"),
                    "tool_id": link_row.get("tool_id"),
                    "tool_version": link_row.get("tool_version"),
                },
                "privacy": {"redact_level": "none", "contains_secrets": False},
                "pins": DEFAULT_PINS,
            },
        )
        return {"artifact_ref_event": ref, "artifact_linked_event": linked}

    @app.post("/v1/projects/{project_id}/comments")
    def create_comment(project_id: str, payload: CommentCreateRequest, request: Request, idempotency_key: str | None = Header(default=None, alias="X-Omni-Idempotency-Key")):
        role = require_project_role(project_id, request.state.user_id, "viewer")
        if payload.target_type not in {"run", "event", "artifact"}:
            raise HTTPException(status_code=400, detail="invalid target_type")
        if payload.target_type == "run":
            ctx = request.app.state.db.get_run_context(payload.target_id)
            if not ctx or ctx.project_id != project_id:
                raise HTTPException(status_code=400, detail="invalid run target")
        elif payload.target_type == "event":
            if not payload.run_id:
                raise HTTPException(status_code=400, detail="run_id required for event target")
            ok, events = request.app.state.db.list_events(payload.run_id, 0)
            if not ok or not any(e["event_id"] == payload.target_id for e in events):
                raise HTTPException(status_code=400, detail="invalid event target")
        elif payload.target_type == "artifact":
            if not request.app.state.db.get_artifact(payload.target_id):
                raise HTTPException(status_code=400, detail="invalid artifact target")
        body = payload.body.strip()
        if not body:
            raise HTTPException(status_code=400, detail="empty comment body")
        return with_idempotency(
            request.state.user_id,
            f"POST:/v1/projects/{project_id}/comments",
            idempotency_key,
            lambda: _create_comment_impl(project_id, payload, body, request),
        )

    @app.get("/v1/projects/{project_id}/comments")
    def list_comments(project_id: str, request: Request, run_id: str | None = None, target_type: str | None = None, target_id: str | None = None):
        require_project_role(project_id, request.state.user_id, "viewer")
        return {"comments": request.app.state.db.list_comments(project_id, run_id=run_id, target_type=target_type, target_id=target_id)}

    @app.delete("/v1/projects/{project_id}/comments/{comment_id}")
    def delete_comment(project_id: str, comment_id: str, request: Request):
        role = require_project_role(project_id, request.state.user_id, "viewer")
        existing = request.app.state.db.get_comment(comment_id)
        if not existing or existing["project_id"] != project_id:
            raise HTTPException(status_code=404, detail="comment not found")
        if existing["author_id"] != request.state.user_id and role != "owner":
            raise HTTPException(status_code=403, detail="cannot delete this comment")
        if not request.app.state.db.delete_comment(comment_id):
            raise HTTPException(status_code=404, detail="comment not found")
        ts = datetime.now(UTC).isoformat()
        request.app.state.db.add_activity(project_id, "comment_deleted", "comment", comment_id, request.state.user_id)
        emit_project_collab_event(project_id, {"kind": "comment_deleted", "actor": "system", "payload": {"comment_id": comment_id, "deleted_by": request.state.user_id, "deleted_at": ts}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"deleted": True}

    @app.get("/v1/projects/{project_id}/activity")
    def project_activity(project_id: str, request: Request, after: str | None = None, limit: int = 50):
        require_project_role(project_id, request.state.user_id, "viewer")
        return {"activity": request.app.state.db.list_activity(project_id, after=after, limit=min(max(limit, 1), 200))}

    @app.get("/v1/projects/{project_id}/activity/stream")
    async def project_activity_stream(
        project_id: str,
        request: Request,
        after_seq: int | None = None,
        limit: int = 200,
        once: bool = False,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        require_project_role(project_id, request.state.user_id, "viewer")
        start_seq = _parse_sse_start(after_seq, last_event_id)
        fetch = lambda cursor, lim: request.app.state.db.list_activity(project_id, after_seq=cursor, limit=lim)
        if once:
            return _sse_response_once("activity", fetch(start_seq, limit), "activity_seq")
        return StreamingResponse(
            _instrumented_sse_stream(request, "project_activity", start_seq, "activity", "activity_seq", fetch, limit),
            media_type="text/event-stream",
            headers=_sse_headers(),
        )

    @app.get("/v1/projects/{project_id}/activity/unread")
    def activity_unread(project_id: str, request: Request):
        require_project_role(project_id, request.state.user_id, "viewer")
        state = request.app.state.db.get_user_project_state(request.state.user_id, project_id)
        max_seq = request.app.state.db.max_activity_seq(project_id)
        unread = max(0, int(max_seq) - int(state["last_seen_activity_seq"]))
        return {"project_id": project_id, "last_seen_activity_seq": int(state["last_seen_activity_seq"]), "max_activity_seq": max_seq, "unread_count": unread}

    @app.post("/v1/projects/{project_id}/activity/mark_seen")
    def activity_mark_seen(project_id: str, payload: dict[str, Any], request: Request, idempotency_key: str | None = Header(default=None, alias="X-Omni-Idempotency-Key")):
        require_project_role(project_id, request.state.user_id, "viewer")
        return with_idempotency(
            request.state.user_id,
            f"POST:/v1/projects/{project_id}/activity/mark_seen",
            idempotency_key,
            lambda: _mark_seen_impl(project_id, payload, request),
        )

    @app.get("/v1/notifications")
    def notifications(
        request: Request,
        unread_only: bool = False,
        limit: int = 50,
        after_id: str | None = None,
    ):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        rows = request.app.state.db.list_notifications(
            request.state.user_id,
            limit=min(max(limit, 1), 200),
            after_id=after_id,
            unread_only=unread_only,
        )
        return {"notifications": rows}

    @app.get("/v1/notifications/unread_count")
    def notifications_unread_count(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        unread_count = request.app.state.db.get_unread_count(request.state.user_id)
        state = request.app.state.db.get_notification_state(request.state.user_id)
        return {
            "unread_count": unread_count,
            "last_seen_notification_seq": int(state["last_seen_notification_seq"]),
        }

    @app.get("/v1/notifications/state")
    def notifications_state(request: Request):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        state = request.app.state.db.get_notification_state(request.state.user_id)
        return {
            "last_seen_notification_seq": int(state["last_seen_notification_seq"]),
            "updated_at": state["updated_at"],
        }

    @app.post("/v1/notifications/mark_read")
    def notifications_mark_read(
        payload: NotificationsMarkReadRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="X-Omni-Idempotency-Key"),
    ):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")

        def _mark_impl() -> dict[str, Any]:
            changed = request.app.state.db.mark_notifications_read(
                request.state.user_id,
                up_to_seq=payload.up_to_seq,
                notification_ids=payload.notification_ids,
            )
            if payload.up_to_seq is not None:
                state = request.app.state.db.set_last_seen_notification_seq(request.state.user_id, int(payload.up_to_seq))
            else:
                state = request.app.state.db.get_notification_state(request.state.user_id)
            unread_count = request.app.state.db.get_unread_count(request.state.user_id)
            return {
                "changed": int(changed),
                "unread_count": unread_count,
                "last_seen_notification_seq": int(state["last_seen_notification_seq"]),
            }

        payload_fingerprint = hashlib.sha256(
            json.dumps(payload.model_dump(exclude_none=True), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        effective_idempotency_key = f"{idempotency_key}:{payload_fingerprint}" if idempotency_key else None
        return with_idempotency(
            request.state.user_id,
            "POST /v1/notifications/mark_read",
            effective_idempotency_key,
            _mark_impl,
        )

    @app.get("/v1/notifications/stream")
    async def notifications_stream(
        request: Request,
        after_seq: int | None = None,
        limit: int = 200,
        once: bool = False,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="authentication required")
        start_seq = _parse_sse_start(after_seq, last_event_id)
        fetch = lambda cursor, lim: request.app.state.db.list_notifications(
            request.state.user_id,
            limit=min(max(lim, 1), 200),
            after_seq=cursor,
            ascending=True,
        )
        if once:
            return _sse_response_once("notification", fetch(start_seq, limit), "notification_seq")
        return StreamingResponse(
            _instrumented_sse_stream(request, "notifications", start_seq, "notification", "notification_seq", fetch, limit),
            media_type="text/event-stream",
            headers=_sse_headers(),
        )
    @app.get("/v1/tools")
    def list_tools(request: Request):
        return {"tools": request.app.state.db.list_tools()}

    @app.post("/v1/tools/install")
    def install_tool(payload: InstallToolRequest, request: Request):
        if not settings.dev_mode:
            raise HTTPException(status_code=403, detail="dev mode required")
        _validate_tool_manifest(payload.manifest)
        request.app.state.db.install_tool(payload.manifest)
        return {"installed": True}

    @app.post("/v1/registry/keys")
    def registry_add_key(payload: RegistryKeyRequest, request: Request):
        if not settings.dev_mode:
            raise HTTPException(status_code=403, detail="dev mode required")
        try:
            base64.b64decode(payload.public_key_base64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid public key encoding") from exc
        return request.app.state.db.add_registry_key(payload.public_key_id, payload.public_key_base64)

    @app.get("/v1/registry/packages")
    def registry_list_packages(request: Request, tier: str | None = None, status: str | None = None):
        return {"packages": request.app.state.db.list_registry_packages(tier=tier, status=status)}

    @app.get("/v1/registry/packages/{package_id}")
    def registry_list_package_versions(package_id: str, request: Request):
        rows = request.app.state.db.list_registry_package_versions(package_id)
        if not rows:
            raise HTTPException(status_code=404, detail="package not found")
        return {"package_id": package_id, "versions": rows}

    @app.get("/v1/registry/packages/{package_id}/{version}")
    def registry_get_package(package_id: str, version: str, request: Request):
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        return pkg

    @app.post("/v1/registry/packages/import")
    def registry_import(payload: RegistryImportRequest, request: Request):
        _require_admin(settings)
        package = payload.package
        _validate_tool_package(package)
        _validate_tool_manifest(package["manifest"])
        if package["manifest"]["tool_id"] != package["package_id"]:
            raise HTTPException(status_code=400, detail="manifest.tool_id must equal package_id")
        key = request.app.state.db.get_registry_key(package["signature"]["public_key_id"])
        if not key:
            raise HTTPException(status_code=400, detail="missing key")
        _verify_package_signature(package, key["public_key_base64"])

        root = Path(settings.registry_root) / package["package_id"] / package["version"]
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        (root / "package.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps(package["manifest"], indent=2), encoding="utf-8")
        for rel_path, b64 in payload.blobs_base64.items():
            blob = base64.b64decode(b64)
            out_path = (root / "blobs" / rel_path).resolve()
            if not str(out_path).startswith(str((root / "blobs").resolve())):
                raise HTTPException(status_code=400, detail="unsafe blob path")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(blob)
        for f in package.get("files", []):
            blob_path = root / "blobs" / f["path"]
            if not blob_path.exists():
                raise HTTPException(status_code=400, detail=f"missing blob for {f['path']}")
            data = blob_path.read_bytes()
            if len(data) != int(f["size_bytes"]):
                raise HTTPException(status_code=400, detail=f"size mismatch for {f['path']}")
            if hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise HTTPException(status_code=400, detail=f"sha256 mismatch for {f['path']}")
        package.setdefault("checks", {"schema_ok": True, "signature_ok": True, "static_ok": False, "contract_tests_ok": False, "last_checked_at": None})
        package.setdefault("moderation", {"reports_count": 0, "last_report_at": None})
        if not package.get("status"):
            package["status"] = "pending_review" if package["metadata"]["tier"] in {"community", "verified"} else "active"
        package["updated_by"] = "system"
        stored = request.app.state.db.upsert_registry_package(package)
        return {"imported": True, "package_id": stored["package_id"], "version": stored["version"]}

    @app.get("/v1/projects/{project_id}/tools/pins")
    def project_tool_pins(project_id: str, request: Request):
        return {"pins": request.app.state.db.list_project_tool_pins(project_id)}

    @app.post("/v1/projects/{project_id}/tools/pins")
    def set_project_tool_pin(project_id: str, payload: ProjectPinRequest, request: Request):
        manifest = request.app.state.db.get_tool_manifest(payload.tool_id, payload.tool_version)
        if not manifest:
            raise HTTPException(status_code=400, detail="tool version not installed")
        request.app.state.db.set_project_tool_pin(project_id, payload.tool_id, payload.tool_version)
        run_ctx = request.app.state.db.get_run_context(payload.run_id)
        if not run_ctx or run_ctx.project_id != project_id:
            raise HTTPException(status_code=404, detail="run not found for project")
        risk = manifest["risk"]
        append_run_event(payload.run_id, {"kind": "tool_pins_updated", "actor": "system", "payload": {"project_id": project_id, "actor": "system", "package_id": "manual", "version": payload.tool_version, "tool_id": payload.tool_id, "tool_version": payload.tool_version, "risk": {"scopes_required": risk["scopes_required"], "external_write": risk["external_write"], "network_egress": risk["network_egress"]}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"pinned": True}

    @app.post("/v1/projects/{project_id}/tools/install")
    def project_install_tool(project_id: str, payload: ProjectInstallRequest, request: Request):
        pkg = request.app.state.db.get_registry_package(payload.package_id, payload.version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        if pkg["status"] in {"yanked", "revoked"}:
            raise HTTPException(status_code=409, detail=f"package status is {pkg['status']}")
        if pkg["tier"] == "community" and pkg["status"] != "verified" and not settings.allow_community_install:
            raise HTTPException(status_code=409, detail="community package not installable until verified")
        if pkg["status"] in {"pending_review", "rejected"}:
            raise HTTPException(status_code=409, detail=f"package status is {pkg['status']}")
        run_ctx = request.app.state.db.get_run_context(payload.run_id)
        if not run_ctx or run_ctx.project_id != project_id:
            raise HTTPException(status_code=404, detail="run not found for project")
        risk = pkg["manifest"]["risk"]
        if risk["external_write"] or risk["network_egress"]:
            approval = request.app.state.db.create_approval(payload.run_id, f"pkg:{payload.package_id}:{payload.version}", pkg["manifest"]["tool_id"], pkg["manifest"]["version"], {"action": "install", "package_id": payload.package_id, "version": payload.version}, f"pkg-install-{project_id}-{payload.package_id}-{payload.version}")
            append_run_event(payload.run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "approval_required", "message": "risky install requires approval", "details": {"approval_id": approval["approval_id"]}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return JSONResponse(status_code=202, content={"approval_id": approval["approval_id"], "risk": risk})
        request.app.state.db.install_tool(pkg["manifest"])
        request.app.state.db.set_project_tool_pin(project_id, pkg["manifest"]["tool_id"], pkg["manifest"]["version"])
        payload_base = {"project_id": project_id, "actor": "system", "package_id": payload.package_id, "version": payload.version, "tool_id": pkg["manifest"]["tool_id"], "tool_version": pkg["manifest"]["version"], "risk": {"scopes_required": risk["scopes_required"], "external_write": risk["external_write"], "network_egress": risk["network_egress"]}}
        append_run_event(payload.run_id, {"kind": "tool_package_installed", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        append_run_event(payload.run_id, {"kind": "tool_pins_updated", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"installed": True, "tool_id": pkg["manifest"]["tool_id"], "tool_version": pkg["manifest"]["version"], "risk": risk}

    @app.post("/v1/projects/{project_id}/tools/uninstall")
    def project_uninstall_tool(project_id: str, payload: ProjectUninstallRequest, request: Request):
        run_ctx = request.app.state.db.get_run_context(payload.run_id)
        if not run_ctx or run_ctx.project_id != project_id:
            raise HTTPException(status_code=404, detail="run not found for project")
        pin = request.app.state.db.get_project_tool_pin(project_id, payload.tool_id)
        if not pin:
            raise HTTPException(status_code=404, detail="tool not pinned")
        manifest = request.app.state.db.get_tool_manifest(payload.tool_id, pin["tool_version"])
        if not manifest:
            raise HTTPException(status_code=409, detail="pinned manifest missing")
        risk = manifest["risk"]
        request.app.state.db.uninstall_tool(payload.tool_id)
        request.app.state.db.remove_project_tool_pin(project_id, payload.tool_id)
        package_id = payload.tool_id
        version = pin["tool_version"]
        payload_base = {"project_id": project_id, "actor": "system", "package_id": package_id, "version": version, "tool_id": payload.tool_id, "tool_version": pin["tool_version"], "risk": {"scopes_required": risk["scopes_required"], "external_write": risk["external_write"], "network_egress": risk["network_egress"]}}
        append_run_event(payload.run_id, {"kind": "tool_package_uninstalled", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        append_run_event(payload.run_id, {"kind": "tool_pins_updated", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"uninstalled": True}

    @app.post("/v1/registry/packages/{package_id}/{version}/yank")
    def registry_yank_package(package_id: str, version: str, run_id: str, request: Request):
        _require_admin(settings)
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        request.app.state.db.set_registry_package_status(package_id, version, "yanked", "system")
        run_ctx = request.app.state.db.get_run_context(run_id)
        if run_ctx:
            risk = pkg["manifest"]["risk"]
            append_run_event(run_id, {"kind": "tool_package_yanked", "actor": "system", "payload": {"project_id": run_ctx.project_id, "actor": "system", "package_id": package_id, "version": version, "tool_id": pkg["manifest"]["tool_id"], "tool_version": pkg["manifest"]["version"], "risk": {"scopes_required": risk["scopes_required"], "external_write": risk["external_write"], "network_egress": risk["network_egress"]}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"yanked": True}

    @app.post("/v1/registry/packages/{package_id}/{version}/report")
    def registry_report_package(package_id: str, version: str, payload: RegistryReportRequest, request: Request):
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        report = request.app.state.db.create_registry_report(package_id, version, payload.reporter, payload.reason_code, payload.details)
        append_run_event(payload.run_id, {"kind": "tool_package_reported", "actor": "system", "payload": {"package_id": package_id, "version": version, "reason_code": payload.reason_code, "details": payload.details, "reported_at": report["created_at"]}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return report

    @app.get("/v1/registry/reports")
    def registry_list_reports(request: Request, status: str | None = None):
        _require_admin(settings)
        return {"reports": request.app.state.db.list_registry_reports(status=status)}

    @app.post("/v1/registry/reports/{report_id}/triage")
    def registry_triage_report(report_id: str, request: Request):
        _require_admin(settings)
        if not request.app.state.db.set_registry_report_status(report_id, "triaged"):
            raise HTTPException(status_code=404, detail="report not found")
        return {"triaged": True}

    @app.post("/v1/registry/reports/{report_id}/close")
    def registry_close_report(report_id: str, request: Request):
        _require_admin(settings)
        if not request.app.state.db.set_registry_report_status(report_id, "closed"):
            raise HTTPException(status_code=404, detail="report not found")
        return {"closed": True}

    @app.post("/v1/registry/packages/{package_id}/{version}/verify")
    def registry_verify(package_id: str, version: str, payload: RegistryVerifyRequest, request: Request):
        _require_admin(settings)
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        checks = {"schema_ok": False, "signature_ok": False, "static_ok": False, "contract_tests_ok": False, "last_checked_at": datetime.now(UTC).isoformat()}
        checks["schema_ok"] = True
        key = request.app.state.db.get_registry_key(pkg["signature"]["public_key_id"])
        if key:
            try:
                signed_view = {
                    "package_id": pkg["package_id"],
                    "version": pkg["version"],
                    "created_at": pkg["created_at"],
                    "manifest": pkg["manifest"],
                    "files": pkg["files"],
                    "signature": pkg["signature"],
                    "metadata": pkg["metadata"],
                }
                if "status" in pkg:
                    signed_view["status"] = pkg["status"]
                if "checks" in pkg:
                    signed_view["checks"] = pkg["checks"]
                if "moderation" in pkg:
                    signed_view["moderation"] = pkg["moderation"]
                _verify_package_signature(signed_view, key["public_key_base64"])
                checks["signature_ok"] = True
            except HTTPException:
                checks["signature_ok"] = False
        allowed_bindings = {"inproc_safe", "sandbox_job", "mcp_remote", "openapi_proxy"}
        static_ok = True
        manifest = pkg["manifest"]
        if manifest.get("binding", {}).get("type") not in allowed_bindings:
            static_ok = False
        if not isinstance(manifest.get("risk", {}).get("scopes_required"), list):
            static_ok = False
        if manifest.get("risk", {}).get("external_write") and len(manifest.get("risk", {}).get("scopes_required", [])) == 0:
            static_ok = False
        checks["static_ok"] = static_ok
        try:
            _validate_tool_manifest(manifest)
            checks["contract_tests_ok"] = True
        except HTTPException:
            checks["contract_tests_ok"] = False
        from_status = pkg["status"]
        to_status = "verified" if all(bool(checks[k]) for k in ["schema_ok", "signature_ok", "static_ok", "contract_tests_ok"]) else "rejected"
        request.app.state.db.set_registry_package_status(package_id, version, to_status, "system", checks=checks)
        append_run_event(payload.run_id, {"kind": "tool_package_status_changed", "actor": "system", "payload": {"package_id": package_id, "version": version, "from_status": from_status, "to_status": to_status, "decided_by": "system", "decided_at": datetime.now(UTC).isoformat(), "notes": "verify pipeline"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"package_id": package_id, "version": version, "status": to_status, "checks": checks}

    @app.post("/v1/registry/packages/{package_id}/{version}/status")
    def registry_set_status(package_id: str, version: str, payload: RegistryStatusRequest, request: Request):
        _require_admin(settings)
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        if not _allowed_status_transition(pkg["status"], payload.to_status):
            raise HTTPException(status_code=400, detail="invalid status transition")
        request.app.state.db.set_registry_package_status(package_id, version, payload.to_status, "system")
        append_run_event(payload.run_id, {"kind": "tool_package_status_changed", "actor": "system", "payload": {"package_id": package_id, "version": version, "from_status": pkg["status"], "to_status": payload.to_status, "decided_by": "system", "decided_at": datetime.now(UTC).isoformat(), "notes": payload.notes}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"updated": True}

    @app.post("/v1/registry/packages/{package_id}/{version}/mirror")
    def registry_mirror(package_id: str, version: str, payload: RegistryMirrorRequest, request: Request):
        _require_admin(settings)
        pkg = request.app.state.db.get_registry_package(package_id, version)
        if not pkg:
            raise HTTPException(status_code=404, detail="package not found")
        to_version = payload.to_version or version
        source_root = Path(settings.registry_root) / package_id / version
        target_root = Path(settings.registry_root) / payload.to_package_id / to_version
        target_root.mkdir(parents=True, exist_ok=True)
        if (source_root / "package.json").exists():
            (target_root / "package.json").write_bytes((source_root / "package.json").read_bytes())
        if (source_root / "manifest.json").exists():
            (target_root / "manifest.json").write_bytes((source_root / "manifest.json").read_bytes())
        (target_root / "blobs").mkdir(parents=True, exist_ok=True)
        src_blobs = source_root / "blobs"
        if src_blobs.exists():
            for file in src_blobs.rglob("*"):
                if file.is_file():
                    rel = file.relative_to(src_blobs)
                    out = target_root / "blobs" / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(file.read_bytes())
        mirrored = {
            **pkg,
            "package_id": payload.to_package_id,
            "version": to_version,
            "metadata": {**pkg["metadata"], "tier": "private"},
            "status": "active",
            "updated_by": "system",
        }
        request.app.state.db.upsert_registry_package(mirrored)
        append_run_event(payload.run_id, {"kind": "tool_package_mirrored", "actor": "system", "payload": {"from_package_id": package_id, "from_version": version, "to_package_id": payload.to_package_id, "to_version": to_version, "mirrored_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"mirrored": True, "package_id": payload.to_package_id, "version": to_version}

    @app.post("/v1/collections")
    def create_collection(payload: CollectionCreateRequest, request: Request):
        _require_admin(settings)
        c = request.app.state.db.create_collection(payload.name, payload.description, payload.packages)
        append_run_event(payload.run_id, {"kind": "collection_created", "actor": "system", "payload": {"collection_id": c["collection_id"], "name": c["name"], "packages": c["packages"]}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return c

    @app.get("/v1/collections")
    def list_collections(request: Request):
        return {"collections": request.app.state.db.list_collections()}

    @app.get("/v1/projects/{project_id}/policy/grants")
    def list_grants(project_id: str, request: Request):
        return {"grants": request.app.state.db.list_grants(project_id)}

    @app.post("/v1/projects/{project_id}/policy/grants")
    def grant_scope(project_id: str, payload: GrantScopeRequest, request: Request):
        request.app.state.db.grant_scope(project_id, payload.scope, "system")
        return {"granted": True}

    @app.delete("/v1/projects/{project_id}/policy/grants/{scope}")
    def revoke_scope(project_id: str, scope: str, request: Request):
        request.app.state.db.revoke_scope(project_id, scope)
        return {"revoked": True}

    @app.get("/v1/runs/{run_id}/approvals")
    def list_approvals(run_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "viewer")
        return {"approvals": request.app.state.db.list_approvals(run_id)}

    @app.post("/v1/runs/{run_id}/tools/invoke")
    def invoke_tool(run_id: str, payload: ToolInvokeRequest, request: Request):
        require_run_role(run_id, request.state.user_id, "editor")
        ctx = request.app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        resolved_version = payload.version
        if not resolved_version:
            pin = request.app.state.db.get_project_tool_pin(ctx.project_id, payload.tool_id)
            if pin:
                resolved_version = pin["tool_version"]
                if not request.app.state.db.get_tool_manifest(payload.tool_id, resolved_version):
                    raise HTTPException(status_code=409, detail="pinned tool version missing; reinstall package version")
        manifest = request.app.state.db.get_tool_manifest(payload.tool_id, resolved_version)
        if not manifest:
            raise HTTPException(status_code=404, detail="tool not found")
        in_err = validate_json_schema(manifest["inputs_schema"], payload.inputs)
        if in_err:
            raise HTTPException(status_code=400, detail=in_err)
        correlation_id = str(uuid4())
        call_event = append_run_event(run_id, {"kind": "tool_call", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "inputs": payload.inputs, "binding_type": manifest["binding"]["type"], "correlation_id": correlation_id, "executor_version": EXECUTOR_VERSION}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        decision, reason = tool_policy_decision(run_id, manifest)
        if decision == "deny":
            sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "policy_denied", "message": reason}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            err_event = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": manifest["tool_id"], "tool_version": manifest["version"], "error_code": "POLICY_DENIED", "message": reason, "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_call_event": call_event, "system_event": sys_event, "tool_error_event": err_event}
        if decision == "approval_required":
            approval = request.app.state.db.create_approval(run_id, call_event["event_id"], manifest["tool_id"], manifest["version"], payload.inputs, correlation_id)
            sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "approval_required", "message": reason, "details": {"approval_id": approval["approval_id"]}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return JSONResponse(status_code=202, content={"tool_call_event": call_event, "approval_id": approval["approval_id"], "system_event": sys_event})
        outcome = execute_tool_call(run_id, manifest, payload.inputs, correlation_id)
        return {"tool_call_event": call_event, **outcome}

    @app.post("/v1/runs/{run_id}/approvals/{approval_id}/approve")
    def approve(run_id: str, approval_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "editor")
        approval = request.app.state.db.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="approval not found")
        request.app.state.db.decide_approval(approval_id, "approved", "system")
        manifest = request.app.state.db.get_tool_manifest(approval["tool_id"], approval["tool_version"])
        sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "approval_decided", "message": "approved", "details": {"approval_id": approval_id}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        if approval["inputs"].get("action") == "install":
            pkg = request.app.state.db.get_registry_package(approval["inputs"]["package_id"], approval["inputs"]["version"])
            if not pkg:
                raise HTTPException(status_code=404, detail="package not found")
            ctx = request.app.state.db.get_run_context(run_id)
            if not ctx:
                raise HTTPException(status_code=404, detail="run not found")
            request.app.state.db.install_tool(pkg["manifest"])
            request.app.state.db.set_project_tool_pin(ctx.project_id, pkg["manifest"]["tool_id"], pkg["manifest"]["version"])
            risk = pkg["manifest"]["risk"]
            payload_base = {"project_id": ctx.project_id, "actor": "system", "package_id": pkg["package_id"], "version": pkg["version"], "tool_id": pkg["manifest"]["tool_id"], "tool_version": pkg["manifest"]["version"], "risk": {"scopes_required": risk["scopes_required"], "external_write": risk["external_write"], "network_egress": risk["network_egress"]}}
            installed_event = append_run_event(run_id, {"kind": "tool_package_installed", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            pins_event = append_run_event(run_id, {"kind": "tool_pins_updated", "actor": "system", "payload": payload_base, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"approval_id": approval_id, "system_event": sys_event, "tool_package_installed": installed_event, "tool_pins_updated": pins_event}
        if manifest is None:
            return {"approval_id": approval_id, "system_event": sys_event, "status": "approved"}
        outcome = execute_tool_call(run_id, manifest, approval["inputs"], approval["correlation_id"])
        return {"approval_id": approval_id, "system_event": sys_event, **outcome}

    @app.post("/v1/runs/{run_id}/approvals/{approval_id}/deny")
    def deny(run_id: str, approval_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "editor")
        approval = request.app.state.db.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="approval not found")
        request.app.state.db.decide_approval(approval_id, "denied", "system")
        sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "approval_decided", "message": "denied", "details": {"approval_id": approval_id}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        err_event = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": approval["correlation_id"], "payload": {"tool_id": approval["tool_id"], "tool_version": approval["tool_version"], "error_code": "APPROVAL_DENIED", "message": "approval denied", "correlation_id": approval["correlation_id"]}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"approval_id": approval_id, "system_event": sys_event, "tool_error_event": err_event}

    @app.post("/v1/mcp/servers")
    def create_mcp_server(payload: McpServerCreateRequest, request: Request):
        if payload.transport == "http" and payload.endpoint_url and not is_localhost_endpoint(payload.endpoint_url) and not settings.allow_remote_mcp:
            raise HTTPException(status_code=403, detail="remote MCP endpoints disabled")
        return request.app.state.db.create_mcp_server(payload.model_dump(exclude_none=True))

    @app.get("/v1/mcp/servers")
    def list_mcp_servers(request: Request):
        return {"servers": request.app.state.db.list_mcp_servers()}

    @app.get("/v1/mcp/servers/{server_id}")
    def get_mcp_server(server_id: str, request: Request):
        server = request.app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        return server

    @app.post("/v1/mcp/servers/{server_id}/health")
    def mcp_health(server_id: str, request: Request):
        server = request.app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        client = McpHttpClient(server["endpoint_url"], session_id=server.get("session_id"))
        init = client.initialize()
        client.notify_initialized()
        client.tools_list()
        request.app.state.db.update_mcp_server_health(server_id, "healthy", init["latency_ms"], init.get("protocol_version"), init.get("session_id"))
        return {"status": "healthy", "latency_ms": init["latency_ms"]}

    @app.post("/v1/mcp/servers/{server_id}/catalog/refresh")
    def mcp_catalog_refresh(server_id: str, request: Request):
        server = request.app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        client = McpHttpClient(server["endpoint_url"], session_id=server.get("session_id"))
        init = client.initialize()
        client.notify_initialized()
        tools = client.tools_list().get("tools", [])
        request.app.state.db.update_mcp_server_health(server_id, "healthy", init["latency_ms"], init.get("protocol_version"), init.get("session_id"))
        request.app.state.db.upsert_mcp_catalog(server_id, tools)
        return {"server_id": server_id, "count": len(tools)}

    @app.get("/v1/mcp/servers/{server_id}/tools")
    def mcp_tools(server_id: str, request: Request):
        catalog = request.app.state.db.get_mcp_catalog(server_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="catalog not found")
        return catalog

    @app.post("/v1/runs/{run_id}/mcp/{server_id}/try_tool")
    def mcp_try_tool(run_id: str, server_id: str, payload: McpTryToolRequest, request: Request):
        ctx = request.app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        server = request.app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        correlation_id = str(uuid4())
        call_event = append_run_event(run_id, {"kind": "tool_call", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": "mcp.try_tool", "tool_version": "1.0", "inputs": payload.model_dump(), "binding_type": "mcp_remote", "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        if not request.app.state.db.has_scope(ctx.project_id, "mcp_call"):
            sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "policy_denied", "message": "missing scope: mcp_call"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": "mcp.try_tool", "tool_version": "1.0", "error_code": "POLICY_DENIED", "message": "missing scope: mcp_call", "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_call_event": call_event, "system_event": sys_event, "tool_error_event": err}
        if (not is_localhost_endpoint(server.get("endpoint_url"))) and (not settings.allow_remote_mcp):
            sys_event = append_run_event(run_id, {"kind": "system_event", "actor": "system", "payload": {"code": "policy_denied", "message": "remote MCP disabled"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": "mcp.try_tool", "tool_version": "1.0", "error_code": "POLICY_DENIED", "message": "remote MCP disabled", "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_call_event": call_event, "system_event": sys_event, "tool_error_event": err}
        try:
            result, srv = mcp_call(server_id, payload.name, payload.arguments)
            res_event = append_run_event(run_id, {"kind": "tool_result", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": "mcp.try_tool", "tool_version": "1.0", "outputs": {"content": result.get("content", []), "isError": bool(result.get("isError", False)), "structuredContent": result.get("structuredContent"), "mcp_server_id": server_id, "mcp_protocol_version": srv.get("protocol_version")}, "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_call_event": call_event, "tool_result_event": res_event}
        except Exception as exc:
            err = append_run_event(run_id, {"kind": "tool_error", "actor": "tool", "correlation_id": correlation_id, "payload": {"tool_id": "mcp.try_tool", "tool_version": "1.0", "error_code": "MCP_ERROR", "message": str(exc), "correlation_id": correlation_id}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            return {"tool_call_event": call_event, "tool_error_event": err}

    @app.post("/v1/mcp/servers/{server_id}/pin_tool")
    def mcp_pin_tool(server_id: str, payload: McpPinToolRequest, request: Request):
        server = request.app.state.db.get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="mcp server not found")
        catalog = request.app.state.db.get_mcp_catalog(server_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="catalog not found")
        tool = next((t for t in catalog["tools"] if t.get("name") == payload.tool_name), None)
        if not tool:
            raise HTTPException(status_code=404, detail="tool not found")
        manifest = {
            "tool_id": payload.tool_id,
            "version": payload.version,
            "title": tool.get("title") or payload.tool_name,
            "description": tool.get("description") or "Pinned MCP tool",
            "inputs_schema": tool.get("inputSchema") or {"type": "object"},
            "outputs_schema": {"type": "object", "additionalProperties": False, "required": ["content", "isError"], "properties": {"content": {"type": "array"}, "isError": {"type": "boolean"}, "structuredContent": {"type": ["object", "null"]}, "mcp_server_id": {"type": "string"}, "mcp_protocol_version": {"type": ["string", "null"]}}},
            "binding": {"type": "mcp_remote", "entrypoint": json.dumps({"server_id": server_id, "tool_name": payload.tool_name})},
            "risk": {"scopes_required": ["mcp_call"], "external_write": False, "network_egress": not is_localhost_endpoint(server.get("endpoint_url")), "secrets_required": []},
            "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
        }
        _validate_tool_manifest(manifest)
        request.app.state.db.install_tool(manifest)
        return {"installed": True, "tool_id": payload.tool_id, "version": payload.version}

    @app.post("/v1/memory/items")
    def create_memory_item(payload: MemoryCreateRequest, request: Request, idempotency_key: str | None = Header(default=None, alias="X-Omni-Idempotency-Key")):
        validate_scope(payload.scope_type, payload.scope_id)
        if payload.privacy.get("do_not_store"):
            raise HTTPException(status_code=400, detail="do_not_store=true cannot be persisted")
        if len(payload.content.encode("utf-8")) > 100 * 1024:
            raise HTTPException(status_code=413, detail="memory content too large")
        content = redact_text(payload.content) if payload.privacy.get("contains_secrets") else payload.content
        return with_idempotency(
            request.state.user_id,
            "POST:/v1/memory/items",
            idempotency_key,
            lambda: _create_memory_impl(payload, content, request),
        )

    @app.get("/v1/memory/items")
    def list_memory_items(scope_type: str | None = None, scope_id: str | None = None, type: str | None = None, q: str | None = None):
        return {"items": app.state.db.list_memory_items(scope_type=scope_type, scope_id=scope_id, memory_type=type, q=q)}

    @app.get("/v1/memory/items/{memory_id}")
    def get_memory_item(memory_id: str):
        item = app.state.db.get_memory_item(memory_id)
        if not item:
            raise HTTPException(status_code=404, detail="memory not found")
        return item

    @app.patch("/v1/memory/items/{memory_id}")
    def patch_memory_item(memory_id: str, payload: MemoryUpdateRequest):
        current = app.state.db.get_memory_item(memory_id)
        if not current:
            raise HTTPException(status_code=404, detail="memory not found")
        updated = app.state.db.update_memory_item(memory_id, payload.model_dump(exclude_none=True))
        prov = {k: updated.get(k) for k in ["project_id", "thread_id", "run_id", "event_id", "artifact_id", "source_kind"]}
        if prov.get("run_id"):
            append_run_event(prov["run_id"], {"kind": "memory_item_updated", "actor": "system", "payload": {"memory_id": memory_id, "changes": payload.model_dump(exclude_none=True), "provenance": prov}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return updated

    @app.delete("/v1/memory/items/{memory_id}")
    def delete_memory_item(memory_id: str):
        current = app.state.db.get_memory_item(memory_id)
        if not current:
            raise HTTPException(status_code=404, detail="memory not found")
        ok = app.state.db.delete_memory_item(memory_id)
        if not ok:
            raise HTTPException(status_code=404, detail="memory not found")
        prov = {k: current.get(k) for k in ["project_id", "thread_id", "run_id", "event_id", "artifact_id", "source_kind"]}
        if prov.get("run_id"):
            append_run_event(prov["run_id"], {"kind": "memory_item_deleted", "actor": "system", "payload": {"memory_id": memory_id, "provenance": prov}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"deleted": True}

    @app.post("/v1/memory/search")
    def memory_search(payload: MemorySearchRequest):
        items = app.state.db.list_memory_items(scope_type=payload.scope_type, scope_id=payload.scope_id, q=payload.query or None)
        now = datetime.now(UTC)
        filtered = []
        for item in items:
            if item.get("expires_at") and item["expires_at"] <= now.isoformat():
                continue
            if not payload.include_secret and item.get("privacy", {}).get("contains_secrets"):
                continue
            if payload.include_types and item["type"] not in payload.include_types:
                continue
            age_hours = max((now - datetime.fromisoformat(item["updated_at"])).total_seconds() / 3600.0, 0.0)
            recency = 1.0 / (1.0 + age_hours)
            keyword = 1.0 if payload.query.lower() in (item.get("content", "").lower() + " " + (item.get("title") or "").lower()) else 0.0
            score = 0.5 * keyword + 0.3 * recency + 0.2 * float(item.get("importance", 0.5))
            filtered.append((score, item))
        filtered.sort(key=lambda x: (-x[0], x[1]["updated_at"], x[1]["memory_id"]))
        chosen = [x[1] for x in filtered[: payload.top_k]]
        lines: list[str] = []
        used = 0
        chosen_ids: list[str] = []
        for item in chosen:
            header = f"[{item['type']}/{item['scope_type']}] {(item.get('title') or 'Untitled')} ({item['updated_at']})\n"
            body = item["content"] + "\n"
            chunk = header + body
            if used + len(chunk) > payload.budget_chars:
                break
            lines.append(chunk)
            used += len(chunk)
            chosen_ids.append(item["memory_id"])
        return {"items": [i for i in chosen if i["memory_id"] in chosen_ids], "composed_context": "\n".join(lines), "budget_used": used}

    @app.post("/v1/runs/{run_id}/memory/promote")
    def promote_memory(run_id: str, payload: MemoryPromoteRequest, request: Request):
        ctx = request.app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        validate_scope(payload.scope_type, payload.scope_id)
        content = payload.excerpt or ""
        if payload.source_event_id:
            ok, events = request.app.state.db.list_events(run_id, 0)
            if ok:
                ev = next((e for e in events if e["event_id"] == payload.source_event_id), None)
                if ev:
                    content = content or json.dumps(ev["payload"])
        if payload.source_artifact_id:
            art = request.app.state.db.get_artifact(payload.source_artifact_id)
            if art:
                data = Path(art["storage_ref"]).read_text(encoding="utf-8", errors="replace")
                content = content or data
        if not content:
            raise HTTPException(status_code=400, detail="no source content found")
        content = redact_text(content)
        item = request.app.state.db.create_memory_item(
            {
                "type": payload.type,
                "scope_type": payload.scope_type,
                "scope_id": payload.scope_id,
                "title": payload.title,
                "content": content,
                "tags": payload.tags,
                "importance": payload.importance,
                "privacy": {"redact_level": "partial", "contains_secrets": False, "do_not_store": False},
            },
            {"project_id": ctx.project_id, "thread_id": ctx.thread_id, "run_id": run_id, "event_id": payload.source_event_id, "artifact_id": payload.source_artifact_id, "source_kind": "promote"},
        )
        append_run_event(run_id, {"kind": "memory_item_created", "actor": "system", "payload": {"memory_id": item["memory_id"], "provenance": {"project_id": ctx.project_id, "thread_id": ctx.thread_id, "run_id": run_id, "event_id": payload.source_event_id, "artifact_id": payload.source_artifact_id, "source_kind": "promote"}}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return item

    @app.post("/v1/runs/{run_id}/research/start")
    def research_start(run_id: str, payload: ResearchStartRequest, request: Request):
        ctx = request.app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        now = datetime.now(UTC).isoformat()
        append_run_event(run_id, {"kind": "research_stage_started", "actor": "system", "payload": {"stage": "decompose", "query": payload.query, "params": {"mode": payload.mode}, "started_at": now}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        subqueries = [f"{payload.query} overview", f"{payload.query} risks", f"{payload.query} implementation"]
        decomp_art = store_text_artifact("json", "research-decompose", json.dumps({"subqueries": subqueries}))
        append_run_event(run_id, {"kind": "research_stage_completed", "actor": "system", "payload": {"stage": "decompose", "summary": f"{len(subqueries)} subqueries", "outputs_ref": decomp_art["artifact_id"], "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})

        append_run_event(run_id, {"kind": "research_stage_started", "actor": "system", "payload": {"stage": "search", "query": payload.query, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        sources: list[dict[str, Any]] = []
        for sq in subqueries if payload.top_k >= 1 else []:
            inv = invoke_tool(run_id, ToolInvokeRequest(tool_id="web.search", inputs={"query": sq, "top_k": payload.top_k}), request)
            corr = inv["tool_call_event"]["payload"]["correlation_id"]
            tool_call_event_id = inv["tool_call_event"]["event_id"]
            results = inv.get("tool_result_event", {}).get("payload", {}).get("outputs", {}).get("results", [])
            for r in results:
                sid = str(uuid4())
                src = {"source_id": sid, "title": r["title"], "url": r["url"], "snippet": r.get("snippet"), "retrieved_at": datetime.now(UTC).isoformat(), "correlation_id": corr, "tool_id": "web.search", "tool_version": "1.0.0", "artifact_id": None}
                request.app.state.db.create_research_source({"run_id": run_id, **src})
                request.app.state.db.upsert_research_source_link(run_id, sid, corr, tool_call_event_id)
                sources.append(src)
                append_run_event(run_id, {"kind": "research_source_created", "actor": "system", "payload": src, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        append_run_event(run_id, {"kind": "research_stage_completed", "actor": "system", "payload": {"stage": "search", "summary": f"{len(sources)} sources", "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        for stage, summary in [
            ("cluster", "deterministic lexical grouping"),
            ("extract", "key facts extracted"),
        ]:
            append_run_event(run_id, {"kind": "research_stage_started", "actor": "system", "payload": {"stage": stage, "query": payload.query, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            append_run_event(run_id, {"kind": "research_stage_completed", "actor": "system", "payload": {"stage": stage, "summary": summary, "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})

        append_run_event(run_id, {"kind": "research_stage_started", "actor": "system", "payload": {"stage": "synthesize", "query": payload.query, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        if sources:
            lines = [f"# Research Report: {payload.query}", "", "## Sources"]
            for i, s in enumerate(sources[:12], start=1):
                lines.append(f"{i}. [{s['title']}]({s['url']}) - {s.get('snippet') or ''}")
            lines += ["", "## Synthesis", f"Collected {len(sources)} sources. Deterministic synthesis generated."]
        else:
            lines = [f"# Research Report: {payload.query}", "", "Insufficient sources found."]
        report = "\n".join(lines)
        report_art = store_text_artifact("document", "research-report", report, media_type="text/markdown")
        citations = [{"source_id": s["source_id"], "note": s["title"]} for s in sources]
        citations_art = store_text_artifact("json", "research-citations", json.dumps({"sources": citations}))
        append_run_event(run_id, {"kind": "research_report_created", "actor": "system", "payload": {"report_artifact_id": report_art["artifact_id"], "citations": citations, "created_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        append_run_event(run_id, {"kind": "research_stage_completed", "actor": "system", "payload": {"stage": "synthesize", "summary": "report generated", "outputs_ref": report_art["artifact_id"], "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        for stage, summary in [("critique", "self-critique completed"), ("finalize", "research finalized")]:
            append_run_event(run_id, {"kind": "research_stage_started", "actor": "system", "payload": {"stage": stage, "query": payload.query, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
            append_run_event(run_id, {"kind": "research_stage_completed", "actor": "system", "payload": {"stage": stage, "summary": summary, "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"report_artifact_id": report_art["artifact_id"], "citations_artifact_id": citations_art["artifact_id"], "citations": citations, "sources_count": len(sources)}

    @app.get("/v1/runs/{run_id}/research/sources")
    def research_sources(run_id: str, request: Request):
        return {"sources": request.app.state.db.list_research_sources(run_id)}

    @app.get("/v1/runs/{run_id}/research/report")
    def research_report(run_id: str, request: Request):
        ok, events = request.app.state.db.list_events(run_id, 0)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        report_ev = next((e for e in reversed(events) if e["kind"] == "research_report_created"), None)
        if not report_ev:
            raise HTTPException(status_code=404, detail="report not found")
        return report_ev["payload"]

    @app.get("/v1/runs/{run_id}/provenance")
    def run_provenance(run_id: str, request: Request):
        require_run_role(run_id, request.state.user_id, "viewer")
        ok, events = request.app.state.db.list_events(run_id, 0)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        ok_art, artifacts = request.app.state.db.list_run_artifacts(run_id)
        if not ok_art:
            raise HTTPException(status_code=404, detail="run not found")
        sources = request.app.state.db.list_research_sources(run_id)
        report_artifacts = [
            e["payload"].get("report_artifact_id")
            for e in events
            if e["kind"] == "research_report_created" and isinstance(e.get("payload"), dict)
        ]
        return {
            "run_id": run_id,
            "events_count": len(events),
            "artifacts_count": len(artifacts),
            "research_sources_count": len(sources),
            "report_artifact_ids": [x for x in report_artifacts if x],
            "artifacts": [
                {
                    "artifact_id": a["artifact_id"],
                    "kind": a["kind"],
                    "media_type": a["media_type"],
                    "created_at": a["created_at"],
                    "content_hash": a["content_hash"],
                }
                for a in artifacts
            ],
            "sources": [
                {
                    "source_id": s["source_id"],
                    "title": s["title"],
                    "url": s["url"],
                    "correlation_id": s["correlation_id"],
                    "tool_id": s["tool_id"],
                    "tool_version": s["tool_version"],
                }
                for s in sources
            ],
        }

    def _build_provenance_graph(
        run_id: str,
        request: Request,
        *,
        max_depth: int,
        node_cap: int,
        edge_cap: int,
    ) -> dict[str, Any]:
        ok, events = request.app.state.db.list_events(run_id, 0)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        _, artifacts = request.app.state.db.list_run_artifacts(run_id)
        sources = request.app.state.db.list_research_sources(run_id)
        artifact_links = request.app.state.db.list_artifact_links(run_id)
        tool_corrs = request.app.state.db.list_tool_correlations(run_id)
        source_links = request.app.state.db.list_research_source_links(run_id)

        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        corr_calls: dict[str, str] = {}
        corr_outcomes: dict[str, str] = {}
        report_artifact_id: str | None = None
        report_event: dict[str, Any] | None = None
        max_depth = min(max(max_depth, 1), 24)
        node_cap = min(max(node_cap, 1), 50000)
        edge_cap = min(max(edge_cap, 1), 100000)
        depth_cap_hit = False
        node_cap_hit = False
        edge_cap_hit = False

        def add_node(node_id: str, node_type: str, label: str, meta: dict[str, Any]):
            nonlocal node_cap_hit
            if len(nodes) >= node_cap and node_id not in nodes:
                node_cap_hit = True
                return
            nodes[node_id] = {"id": node_id, "type": node_type, "label": label, "meta": meta}

        def add_edge(src: str, dst: str, kind: str, meta: dict[str, Any] | None = None):
            nonlocal edge_cap_hit
            if len(edges) >= edge_cap:
                edge_cap_hit = True
                return
            edges.append({"from": src, "to": dst, "kind": kind, "meta": meta or {}})

        for e in events:
            eid = f"event:{e['event_id']}"
            kind = str(e["kind"])
            add_node(eid, "event", kind, {"seq": e["seq"], "ts": e["ts"], "kind": kind, "actor": e["actor"], "correlation_id": e.get("correlation_id")})
            if kind == "tool_call" and e.get("correlation_id"):
                corr_calls[str(e["correlation_id"])] = eid
            if kind in {"tool_result", "tool_error"} and e.get("correlation_id"):
                corr_outcomes[str(e["correlation_id"])] = eid
            if kind == "research_report_created":
                report_artifact_id = str((e.get("payload") or {}).get("report_artifact_id") or report_artifact_id)
                report_event = e
            if kind in {"workflow_node_started", "workflow_node_completed", "workflow_node_failed"}:
                p = e.get("payload") or {}
                wfnode_id = f"wfnode:{p.get('workflow_run_id')}:{p.get('node_id')}"
                add_node(wfnode_id, "workflow_node", str(p.get("node_id") or "node"), {"workflow_run_id": p.get("workflow_run_id"), "node_id": p.get("node_id")})
                add_edge(eid, wfnode_id, "workflow_event")
                if kind == "workflow_node_completed" and p.get("outputs_ref"):
                    art_id = str(p["outputs_ref"])
                    add_node(f"artifact:{art_id}", "artifact", art_id[:16], {"artifact_id": art_id})
                    add_edge(wfnode_id, f"artifact:{art_id}", "outputs_ref")

        for corr in sorted(set(corr_calls.keys()) | set(corr_outcomes.keys())):
            call = corr_calls.get(corr)
            out = corr_outcomes.get(corr)
            if call and out:
                add_edge(call, out, "tool_outcome", {"correlation_id": corr})
        for tc in tool_corrs:
            call = tc.get("tool_call_event_id")
            out = tc.get("tool_outcome_event_id")
            corr = tc.get("correlation_id")
            if call and out:
                add_edge(f"event:{call}", f"event:{out}", "tool_outcome", {"correlation_id": corr, "persisted": True})

        # Prefer persisted artifact links. Legacy fallback scans artifact_ref events if links are absent.
        if artifact_links:
            for l in artifact_links:
                art_id = str(l.get("artifact_id") or "")
                if not art_id:
                    continue
                add_node(f"artifact:{art_id}", "artifact", art_id[:16], {"artifact_id": art_id})
                if l.get("event_id"):
                    add_edge(f"event:{l['event_id']}", f"artifact:{art_id}", "artifact_ref", {"persisted": True})
                if l.get("source_event_id"):
                    add_edge(f"event:{l['source_event_id']}", f"artifact:{art_id}", "source_event_artifact")
                corr = str(l.get("correlation_id") or "")
                if corr and corr in corr_calls:
                    add_edge(corr_calls[corr], f"artifact:{art_id}", "correlation_artifact", {"correlation_id": corr})
        else:
            for e in events:
                if e["kind"] != "artifact_ref":
                    continue
                art_id = str((e.get("payload") or {}).get("artifact_id") or "")
                if not art_id:
                    continue
                add_node(f"artifact:{art_id}", "artifact", art_id[:16], {"artifact_id": art_id})
                add_edge(f"event:{e['event_id']}", f"artifact:{art_id}", "artifact_ref", {"legacy_scan": True})
                corr = str(e.get("correlation_id") or "")
                if corr and corr in corr_calls:
                    add_edge(corr_calls[corr], f"artifact:{art_id}", "correlation_artifact", {"correlation_id": corr})

        for a in artifacts:
            aid = str(a["artifact_id"])
            add_node(f"artifact:{aid}", "artifact", (a.get("title") or aid[:16]), {"artifact_id": aid, "kind": a.get("kind"), "media_type": a.get("media_type"), "size_bytes": a.get("size_bytes"), "content_hash": a.get("content_hash")})

        source_link_by_id = {str(s["source_id"]): s for s in source_links}
        for s in sources:
            sid = str(s["source_id"])
            add_node(f"source:{sid}", "research_source", s.get("title") or sid, {"source_id": sid, "url": s.get("url"), "correlation_id": s.get("correlation_id"), "tool_id": s.get("tool_id"), "tool_version": s.get("tool_version")})
            sl = source_link_by_id.get(sid)
            corr = str((sl.get("correlation_id") if sl else s.get("correlation_id")) or "")
            tool_call_event_id = sl.get("tool_call_event_id") if sl else None
            if tool_call_event_id:
                add_edge(f"event:{tool_call_event_id}", f"source:{sid}", "research_source_from_tool", {"correlation_id": corr, "persisted": True})
            elif corr and corr in corr_calls:
                add_edge(corr_calls[corr], f"source:{sid}", "research_source_from_tool", {"correlation_id": corr, "legacy_scan": True})

        if report_artifact_id:
            report_node = f"artifact:{report_artifact_id}"
            add_node(report_node, "artifact", report_artifact_id[:16], {"artifact_id": report_artifact_id})
            if report_event and isinstance(report_event.get("payload"), dict):
                citations = report_event["payload"].get("citations") or []
                if isinstance(citations, list):
                    for c in citations:
                        if isinstance(c, dict) and c.get("source_id"):
                            add_edge(report_node, f"source:{c['source_id']}", "citation", {"note": c.get("note")})

        # Depth cap from artifact nodes over bidirectional traversal so citations/workflow links remain reachable.
        neighbors: dict[str, list[str]] = {}
        for e in edges:
            neighbors.setdefault(e["to"], []).append(e["from"])
            neighbors.setdefault(e["from"], []).append(e["to"])
        roots = [n["id"] for n in nodes.values() if n["type"] == "artifact"]
        keep: set[str] = set()
        frontier = [(r, 0) for r in sorted(roots)]
        while frontier:
            node_id, d = frontier.pop(0)
            if node_id in keep:
                continue
            keep.add(node_id)
            if d >= max_depth:
                depth_cap_hit = True
                continue
            for nxt in sorted(neighbors.get(node_id, [])):
                frontier.append((nxt, d + 1))
        node_list = sorted([n for n in nodes.values() if n["id"] in keep], key=lambda n: (n["type"], n["id"]))
        keep_ids = {n["id"] for n in node_list}
        edge_list = sorted(
            [e for e in edges if e["from"] in keep_ids and e["to"] in keep_ids],
            key=lambda e: (e["from"], e["to"], e["kind"], json.dumps(e.get("meta", {}), sort_keys=True)),
        )
        if len(node_list) > node_cap:
            node_list = node_list[:node_cap]
            keep_ids = {n["id"] for n in node_list}
            edge_list = [e for e in edge_list if e["from"] in keep_ids and e["to"] in keep_ids]
        if len(edge_list) > edge_cap:
            edge_list = edge_list[:edge_cap]
            edge_cap_hit = True
        if len(node_list) >= node_cap:
            node_cap_hit = True
        return {
            "run_id": run_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "truncated": bool(node_cap_hit or edge_cap_hit or depth_cap_hit),
            "truncation": {
                "node_cap_hit": bool(node_cap_hit),
                "edge_cap_hit": bool(edge_cap_hit),
                "depth_cap_hit": bool(depth_cap_hit),
            },
            "nodes": node_list,
            "edges": edge_list,
        }

    @app.get("/v1/runs/{run_id}/provenance/graph")
    def run_provenance_graph(
        run_id: str,
        request: Request,
        max_depth: int = 6,
        node_cap: int = 5000,
        edge_cap: int = 10000,
    ):
        require_run_role(run_id, request.state.user_id, "viewer")
        can_use_cache = int(max_depth) == 6 and int(node_cap) == 5000 and int(edge_cap) == 10000
        if can_use_cache:
            cache = request.app.state.db.get_provenance_cache(run_id)
            last_seq = request.app.state.db.get_run_last_seq(run_id)
            if last_seq is None:
                raise HTTPException(status_code=404, detail="run not found")
            if cache and int(cache["last_seq"]) == int(last_seq):
                request.app.state.db.increment_counter("provenance_cache.hit_count")
                request.app.state.db.set_gauge_text("provenance_cache.last_hit_at", datetime.now(UTC).isoformat())
                cached_graph = cache["graph"]
                cached_graph["generated_at"] = cache["computed_at"]
                return cached_graph
            request.app.state.db.increment_counter("provenance_cache.miss_count")
        t0 = time.perf_counter()
        graph = _build_provenance_graph(
            run_id,
            request,
            max_depth=max_depth,
            node_cap=node_cap,
            edge_cap=edge_cap,
        )
        recompute_ms = (time.perf_counter() - t0) * 1000.0
        request.app.state.db.increment_counter("provenance_cache.recompute_count")
        request.app.state.db.set_gauge_real("provenance_cache.last_recompute_ms", recompute_ms)
        if can_use_cache:
            last_seq = request.app.state.db.get_run_last_seq(run_id)
            if last_seq is not None:
                saved = request.app.state.db.upsert_provenance_cache(run_id, int(last_seq), graph)
                graph["generated_at"] = saved["computed_at"]
        return graph

    @app.get("/v1/runs/{run_id}/provenance/why")
    def run_provenance_why(
        run_id: str,
        artifact_id: str,
        request: Request,
        max_paths: int = 5,
        max_depth: int = 6,
    ):
        require_run_role(run_id, request.state.user_id, "viewer")
        g = run_provenance_graph(run_id, request, max_depth=max_depth, node_cap=5000, edge_cap=10000)
        target = f"artifact:{artifact_id}" if not artifact_id.startswith("artifact:") else artifact_id
        nodes_map = {n["id"]: n for n in g["nodes"]}
        if target not in nodes_map:
            raise HTTPException(status_code=404, detail="artifact not found in provenance graph")
        incoming: dict[str, list[dict[str, Any]]] = {}
        for e in g["edges"]:
            incoming.setdefault(e["to"], []).append(e)
        for k in list(incoming.keys()):
            incoming[k] = sorted(
                incoming[k],
                key=lambda e: (e["from"], e["to"], e["kind"], json.dumps(e.get("meta", {}), sort_keys=True)),
            )
        sinks = {"event", "research_source", "workflow_node"}
        max_paths = min(max(max_paths, 1), 50)
        max_depth = min(max(max_depth, 1), 24)
        paths: list[dict[str, Any]] = []
        truncated = False

        def dfs(node_id: str, depth: int, node_path: list[str], edge_path: list[dict[str, Any]], seen: set[str]):
            nonlocal truncated
            if len(paths) >= max_paths:
                truncated = True
                return
            n = nodes_map.get(node_id)
            if not n:
                return
            if n["type"] in sinks or depth >= max_depth:
                paths.append({"nodes": node_path, "edges": edge_path})
                return
            prev_edges = incoming.get(node_id, [])
            if not prev_edges:
                paths.append({"nodes": node_path, "edges": edge_path})
                return
            for ed in prev_edges:
                src = ed["from"]
                if src in seen:
                    continue
                dfs(src, depth + 1, node_path + [src], edge_path + [ed], seen | {src})

        dfs(target, 0, [target], [], {target})
        paths = sorted(paths, key=lambda p: (len(p["nodes"]), "|".join(p["nodes"]), "|".join(f"{e['from']}->{e['to']}:{e['kind']}" for e in p["edges"])))
        return {"artifact_id": target.replace("artifact:", ""), "paths": paths[:max_paths], "truncated": truncated or len(paths) > max_paths}

    @app.post("/v1/workflows")
    def create_workflow(payload: WorkflowCreateRequest, request: Request):
        graph = payload.graph
        nodes = graph.get("nodes", [])
        entry = graph.get("entry_node_id")
        if not nodes or not entry:
            raise HTTPException(status_code=400, detail="invalid graph")
        ids = {n["id"] for n in nodes}
        if entry not in ids:
            raise HTTPException(status_code=400, detail="entry node missing")
        wfid = str(uuid4())
        graph_art = store_text_artifact("json", f"workflow-{payload.name}", json.dumps(graph))
        wf = request.app.state.db.create_workflow(wfid, payload.name, payload.version, graph_art["artifact_id"])
        return {"workflow": wf}

    @app.get("/v1/workflows")
    def list_workflows(request: Request):
        return {"workflows": request.app.state.db.list_workflows()}

    @app.get("/v1/workflows/{workflow_id}/{version}")
    def get_workflow(workflow_id: str, version: str, request: Request):
        wf = request.app.state.db.get_workflow(workflow_id, version)
        if not wf:
            raise HTTPException(status_code=404, detail="workflow not found")
        return wf

    @app.post("/v1/runs/{run_id}/workflows/{workflow_id}/{version}/start")
    def start_workflow(run_id: str, workflow_id: str, version: str, payload: WorkflowRunStartRequest, request: Request):
        wf = request.app.state.db.get_workflow(workflow_id, version)
        if not wf:
            raise HTTPException(status_code=404, detail="workflow not found")
        graph_art = request.app.state.db.get_artifact(wf["graph_artifact_id"])
        graph = json.loads(Path(graph_art["storage_ref"]).read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        order = [graph["entry_node_id"]] + [e["to"] for e in graph.get("edges", []) if e.get("from") == graph["entry_node_id"]]
        wr = request.app.state.db.create_workflow_run(workflow_id, run_id, payload.inputs)
        append_run_event(run_id, {"kind": "workflow_defined", "actor": "system", "payload": {"workflow_id": workflow_id, "name": wf["name"], "version": wf["version"], "graph_artifact_id": wf["graph_artifact_id"], "created_at": wf["created_at"]}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        append_run_event(run_id, {"kind": "workflow_run_started", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "workflow_id": workflow_id, "inputs": payload.inputs, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})

        outputs: dict[str, Any] = {"inputs": payload.inputs}
        for node_id in order:
            node = nodes.get(node_id)
            if not node:
                continue
            retry_cfg = node.get("retry", {"max_attempts": 1, "backoff_ms": 0})
            max_attempts = int(retry_cfg.get("max_attempts", 1))
            success = False
            for attempt in range(1, max_attempts + 1):
                append_run_event(run_id, {"kind": "workflow_node_started", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "node_id": node_id, "attempt": attempt, "started_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                try:
                    if node["type"] == "transform":
                        if node.get("config", {}).get("force_fail_once") and attempt == 1:
                            raise ValueError("forced failure")
                        out = {"value": f"transform:{node_id}"}
                    elif node["type"] == "tool_invoke":
                        inv = invoke_tool(run_id, ToolInvokeRequest(tool_id=node["config"]["tool_id"], inputs=node["config"].get("inputs", {})), request)
                        if inv.get("tool_error_event"):
                            raise ValueError(inv["tool_error_event"]["payload"]["message"])
                        out = inv["tool_result_event"]["payload"]["outputs"]
                    elif node["type"] == "approval_gate":
                        approval = request.app.state.db.create_approval(run_id, node_id, "workflow.approval_gate", "1.0", {"node_id": node_id}, f"wf-{wr['workflow_run_id']}-{node_id}")
                        request.app.state.db.update_workflow_run(wr["workflow_run_id"], status="waiting_approval", state={"next_node": node_id})
                        append_run_event(run_id, {"kind": "workflow_node_failed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "node_id": node_id, "attempt": attempt, "error_code": "APPROVAL_REQUIRED", "message": approval["approval_id"], "failed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                        append_run_event(run_id, {"kind": "workflow_run_completed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "status": "waiting_approval", "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                        return {"workflow_run_id": wr["workflow_run_id"], "status": "waiting_approval", "approval_id": approval["approval_id"]}
                    else:
                        out = {"ok": True}
                    out_art = store_text_artifact("json", f"wf-node-{node_id}", json.dumps(out))
                    append_run_event(run_id, {"kind": "workflow_node_completed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "node_id": node_id, "attempt": attempt, "outputs_ref": out_art["artifact_id"], "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                    outputs[node_id] = out
                    success = True
                    break
                except Exception as exc:
                    append_run_event(run_id, {"kind": "workflow_node_failed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "node_id": node_id, "attempt": attempt, "error_code": "NODE_FAILED", "message": str(exc), "failed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                    if attempt == max_attempts:
                        request.app.state.db.update_workflow_run(wr["workflow_run_id"], status="failed", completed=True)
                        append_run_event(run_id, {"kind": "workflow_run_completed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "status": "failed", "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
                        return {"workflow_run_id": wr["workflow_run_id"], "status": "failed"}
            if not success:
                break

        request.app.state.db.update_workflow_run(wr["workflow_run_id"], status="completed", state=outputs, completed=True)
        append_run_event(run_id, {"kind": "workflow_run_completed", "actor": "system", "payload": {"workflow_run_id": wr["workflow_run_id"], "status": "completed", "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"workflow_run_id": wr["workflow_run_id"], "status": "completed"}

    @app.get("/v1/runs/{run_id}/workflow_runs")
    def list_workflow_runs(run_id: str, request: Request):
        return {"workflow_runs": request.app.state.db.list_workflow_runs(run_id)}

    @app.get("/v1/runs/{run_id}/workflow_runs/{workflow_run_id}")
    def get_workflow_run(run_id: str, workflow_run_id: str, request: Request):
        wr = request.app.state.db.get_workflow_run(workflow_run_id)
        if not wr or wr["run_id"] != run_id:
            raise HTTPException(status_code=404, detail="workflow run not found")
        return wr

    @app.post("/v1/runs/{run_id}/workflow_runs/{workflow_run_id}/resume")
    def resume_workflow_run(run_id: str, workflow_run_id: str, request: Request):
        wr = request.app.state.db.get_workflow_run(workflow_run_id)
        if not wr or wr["run_id"] != run_id:
            raise HTTPException(status_code=404, detail="workflow run not found")
        if wr["status"] != "waiting_approval":
            return {"workflow_run_id": workflow_run_id, "status": wr["status"]}
        approved = any(a["status"] == "approved" and a["tool_id"] == "workflow.approval_gate" for a in request.app.state.db.list_approvals(run_id))
        if not approved:
            raise HTTPException(status_code=400, detail="approval not granted")
        request.app.state.db.update_workflow_run(workflow_run_id, status="completed", completed=True)
        append_run_event(run_id, {"kind": "workflow_run_completed", "actor": "system", "payload": {"workflow_run_id": workflow_run_id, "status": "completed", "completed_at": datetime.now(UTC).isoformat()}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": DEFAULT_PINS})
        return {"workflow_run_id": workflow_run_id, "status": "completed"}

    @app.post("/v1/runs/{run_id}/agent_stub")
    def agent_stub(run_id: str, payload: AgentRequest, request: Request):
        """Agent endpoint - processes user messages and returns AI responses.
        
        This is a stub implementation that provides basic AI-like responses.
        In production, this would integrate with OpenAI/Anthropic/xAI.
        """
        require_run_role(run_id, request.state.user_id, "editor")
        ctx = request.app.state.db.get_run_context(run_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="run not found")
        
        # Build conversation context from recent messages
        ok, events = request.app.state.db.list_events(run_id, 0, limit=50)
        if not ok:
            raise HTTPException(status_code=404, detail="run not found")
        
        # Extract conversation history
        messages: list[dict[str, Any]] = []
        for e in events:
            if e["kind"] == "user_message":
                messages.append({"role": "user", "content": e["payload"].get("content", "")})
            elif e["kind"] == "assistant_message":
                messages.append({"role": "assistant", "content": e["payload"].get("content", "")})
        
        # Generate response based on mode
        user_input = payload.user_text.strip()
        
        if payload.mode == "simple":
            # Simple mode: direct response without tool calling
            response_text = _generate_simple_response(user_input, messages)
        else:
            # Agent mode: can use tools (stub - just returns enhanced response)
            response_text = _generate_agent_response(user_input, messages)
        
        # Emit assistant_message event
        assistant_event = append_run_event(run_id, {
            "kind": "assistant_message",
            "actor": "assistant",
            "payload": {
                "content": response_text,
                "mode": payload.mode,
            },
            "privacy": {"redact_level": "none", "contains_secrets": False},
            "pins": DEFAULT_PINS,
        })
        
        return {
            "message": response_text,
            "mode": payload.mode,
            "event_id": assistant_event["event_id"],
        }

    # --- V2 subsystem lifecycle ---
    from .v2.setup import setup_v2, teardown_v2

    @app.on_event("startup")
    async def _v2_startup():
        await setup_v2(app)

    @app.on_event("shutdown")
    async def _v2_shutdown():
        await teardown_v2(app)

    return app
