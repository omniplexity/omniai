from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient
from nacl.signing import SigningKey
from omni_backend.app import create_app
from omni_backend.db import Database

from conftest import bootstrap_run, login_as


def _signed_package(tool_id: str, version: str, *, tier: str = "community", status: str = "pending_review", external_write: bool = False, scopes_required: list[str] | None = None):
    sk = SigningKey.generate()
    vk_b64 = base64.b64encode(bytes(sk.verify_key)).decode("ascii")
    key_id = "k1"
    manifest = {
        "tool_id": tool_id,
        "version": version,
        "title": tool_id,
        "description": "pkg",
        "inputs_schema": {"type": "object", "additionalProperties": False, "properties": {"query": {"type": "string"}}},
        "outputs_schema": {"type": "object", "additionalProperties": False, "required": ["results"], "properties": {"results": {"type": "array"}}},
        "binding": {"type": "inproc_safe", "entrypoint": "omni_backend.tools_runtime:web_search"},
        "risk": {"scopes_required": (["read_web"] if external_write else []) if scopes_required is None else scopes_required, "external_write": external_write, "network_egress": False, "secrets_required": []},
        "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
    }
    unsigned = {
        "package_id": tool_id,
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "manifest": manifest,
        "files": [],
        "metadata": {"tier": tier, "tags": ["test"], "description": "desc"},
        "status": status,
        "checks": {"schema_ok": True, "signature_ok": True, "static_ok": False, "contract_tests_ok": False, "last_checked_at": None},
        "moderation": {"reports_count": 0, "last_report_at": None},
    }
    msg = json.dumps({k: v for k, v in unsigned.items() if k != "signature"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = base64.b64encode(sk.sign(msg).signature).decode("ascii")
    pkg = {**unsigned, "signature": {"algo": "ed25519", "public_key_id": key_id, "signature_base64": sig}}
    return key_id, vk_b64, pkg


def _import(client: TestClient, pkg: dict, key_id: str, vk_b64: str):
    assert client.post("/v1/registry/keys", json={"public_key_id": key_id, "public_key_base64": vk_b64}).status_code == 200
    return client.post("/v1/registry/packages/import", json={"package": pkg, "blobs_base64": {}})


def test_report_package_creates_report_and_event(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    key_id, vk_b64, pkg = _signed_package("community.pkg.report", "1.0.0")
    assert _import(client, pkg, key_id, vk_b64).status_code == 200
    rep = client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/report", json={"reporter": "u1", "reason_code": "malicious", "details": "suspicious", "run_id": run_id})
    assert rep.status_code == 200
    reports = client.get("/v1/registry/reports", params={"status": "open"}).json()["reports"]
    assert any(r["package_id"] == pkg["package_id"] for r in reports)
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    assert any(e["kind"] == "tool_package_reported" for e in events)


def test_verify_pipeline_pass_and_fail(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    key_id, vk_b64, pkg_ok = _signed_package("community.pkg.ok", "1.0.0")
    assert _import(client, pkg_ok, key_id, vk_b64).status_code == 200
    ok = client.post(f"/v1/registry/packages/{pkg_ok['package_id']}/{pkg_ok['version']}/verify", json={"run_id": run_id})
    assert ok.status_code == 200
    assert ok.json()["status"] == "verified"

    key_id2, vk_b642, pkg_bad = _signed_package("community.pkg.bad", "1.0.0", external_write=True, scopes_required=[])
    assert _import(client, pkg_bad, key_id2, vk_b642).status_code == 200
    bad = client.post(f"/v1/registry/packages/{pkg_bad['package_id']}/{pkg_bad['version']}/verify", json={"run_id": run_id})
    assert bad.status_code == 200
    assert bad.json()["status"] == "rejected"
    assert bad.json()["checks"]["static_ok"] is False


def test_status_transition_emits_event(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    key_id, vk_b64, pkg = _signed_package("community.pkg.status", "1.0.0")
    assert _import(client, pkg, key_id, vk_b64).status_code == 200
    res = client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/status", json={"to_status": "verified", "notes": "ok", "run_id": run_id})
    assert res.status_code == 200
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    assert any(e["kind"] == "tool_package_status_changed" for e in events)


def test_mirror_to_private_and_install(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    key_id, vk_b64, pkg = _signed_package("community.pkg.mirror", "1.0.0")
    assert _import(client, pkg, key_id, vk_b64).status_code == 200
    assert client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/verify", json={"run_id": run_id}).status_code == 200
    mirror = client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/mirror", json={"to_package_id": "private.org.pkg", "run_id": run_id})
    assert mirror.status_code == 200
    ins = client.post(f"/v1/projects/{project_id}/tools/install", json={"package_id": "private.org.pkg", "version": "1.0.0", "run_id": run_id})
    assert ins.status_code == 200


def test_community_install_blocked_until_verified(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    key_id, vk_b64, pkg = _signed_package("community.pkg.block", "1.0.0")
    assert _import(client, pkg, key_id, vk_b64).status_code == 200
    blocked = client.post(f"/v1/projects/{project_id}/tools/install", json={"package_id": pkg["package_id"], "version": pkg["version"], "run_id": run_id})
    assert blocked.status_code == 409
    assert "community package not installable until verified" in blocked.text


def test_yanked_blocked_but_existing_pin_still_replayable(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    key_id, vk_b64, pkg = _signed_package("community.pkg.replay", "1.0.0")
    assert _import(client, pkg, key_id, vk_b64).status_code == 200
    assert client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/verify", json={"run_id": run_id}).status_code == 200
    assert client.post(f"/v1/projects/{project_id}/tools/install", json={"package_id": pkg["package_id"], "version": pkg["version"], "run_id": run_id}).status_code == 200
    assert client.post(f"/v1/registry/packages/{pkg['package_id']}/{pkg['version']}/status", json={"to_status": "yanked", "run_id": run_id}).status_code == 200
    blocked = client.post(f"/v1/projects/{project_id}/tools/install", json={"package_id": pkg["package_id"], "version": pkg["version"], "run_id": run_id})
    assert blocked.status_code == 409
    invoke = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": pkg["manifest"]["tool_id"], "inputs": {"query": "abc"}})
    assert invoke.status_code == 200


def test_run_metrics_update_deterministically(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    client.post(f"/v1/runs/{run_id}/events", json={"kind": "user_message", "actor": "user", "payload": {"text": "hello"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}})
    client.post(f"/v1/runs/{run_id}/events", json={"kind": "assistant_message", "actor": "assistant", "payload": {"text": "hi"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}})
    metrics = client.get(f"/v1/runs/{run_id}/metrics").json()
    assert metrics["event_count"] >= 2
    assert metrics["bytes_in"] > 0
    assert metrics["bytes_out"] > 0


def test_tool_metrics_and_duration(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "abc"}})
    assert inv.status_code == 200
    client.post(
        f"/v1/runs/{run_id}/events",
        json={
            "kind": "workflow_run_completed",
            "actor": "system",
            "payload": {"workflow_run_id": "wf-run", "status": "completed", "completed_at": datetime.now(UTC).isoformat()},
            "privacy": {"redact_level": "none", "contains_secrets": False},
            "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}},
        },
    )
    metrics = client.get(f"/v1/runs/{run_id}/metrics").json()
    assert metrics["tool_calls"] >= 1
    assert metrics["duration_ms"] is not None
    tmetrics = client.get("/v1/tools/metrics").json()["tools"]
    assert any(t["tool_id"] == "web.search" and t["calls"] >= 1 for t in tmetrics)


def test_filtered_events_endpoint(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    client.post(f"/v1/runs/{run_id}/events", json={"kind": "user_message", "actor": "user", "payload": {"text": "a"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}})
    client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "abc"}})
    filtered = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0, "kinds": "tool_result,tool_error", "tool_id": "web.search"}).json()["events"]
    assert filtered
    assert all(e["kind"] in {"tool_result", "tool_error"} for e in filtered)
    assert all(e["payload"].get("tool_id") == "web.search" for e in filtered if "tool_id" in e["payload"])


def test_user_stub_from_header_and_me(client: TestClient):
    login_as(client, "alice")
    me = client.get("/v1/me").json()
    assert me["user_id"]
    upd = client.patch("/v1/me", json={"display_name": "Alice"}).json()
    assert upd["display_name"] == "Alice"


def test_membership_role_gating_and_owner_changes(client: TestClient):
    login_as(client, "owner")
    project = client.post("/v1/projects", json={"name": "p"}).json()
    pid = project["id"]
    # owner adds viewer
    assert client.post(f"/v1/projects/{pid}/members", json={"user_id": "viewer1", "role": "viewer"}).status_code == 200
    # viewer cannot add member
    login_as(client, "viewer1")
    denied = client.post(f"/v1/projects/{pid}/members", json={"user_id": "x", "role": "viewer"})
    assert denied.status_code == 403
    # owner can change/remove
    login_as(client, "owner")
    assert client.patch(f"/v1/projects/{pid}/members/viewer1", json={"role": "editor"}).status_code == 200
    assert client.delete(f"/v1/projects/{pid}/members/viewer1").status_code == 200


def test_delete_thread_removes_thread_runs_and_events(client: TestClient):
    project = client.post("/v1/projects", json={"name": "delete-thread-project"}).json()
    thread = client.post(f"/v1/projects/{project['id']}/threads", json={"title": "delete-thread"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    payload = {
        "kind": "user_message",
        "actor": "user",
        "payload": {"text": "hello"},
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}},
    }
    assert client.post(f"/v1/runs/{run['id']}/events", json=payload).status_code == 200

    deleted = client.delete(f"/v1/threads/{thread['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    threads = client.get("/v1/threads").json()["threads"]
    assert all(t["id"] != thread["id"] for t in threads)
    assert client.get(f"/v1/threads/{thread['id']}/runs").status_code == 404
    assert client.app.state.db.get_run_context(run["id"]) is None


def test_delete_uncategorized_thread_requires_owner(client: TestClient):
    own_thread = client.post("/v1/threads", json={"title": "owned-chat"}).json()
    login_as(client, "other-user")
    denied = client.delete(f"/v1/threads/{own_thread['id']}")
    assert denied.status_code == 404
    own_list = client.get("/v1/threads").json()["threads"]
    assert all(t["id"] != own_thread["id"] for t in own_list)
    login_as(client, "dev-user")
    own_list_after = client.get("/v1/threads").json()["threads"]
    assert any(t["id"] == own_thread["id"] for t in own_list_after)


def test_delete_project_thread_requires_editor_or_owner(client: TestClient):
    login_as(client, "owner-user")
    project = client.post("/v1/projects", json={"name": "auth-project"}).json()
    thread = client.post(f"/v1/projects/{project['id']}/threads", json={"title": "project-chat"}).json()
    login_as(client, "viewer-user")
    viewer_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "editor-user")
    editor_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "owner-user")
    assert client.post(f"/v1/projects/{project['id']}/members", json={"user_id": viewer_id, "role": "viewer"}).status_code == 200
    assert client.post(f"/v1/projects/{project['id']}/members", json={"user_id": editor_id, "role": "editor"}).status_code == 200

    login_as(client, "viewer-user")
    denied = client.delete(f"/v1/threads/{thread['id']}")
    assert denied.status_code == 404

    login_as(client, "editor-user")
    allowed = client.delete(f"/v1/threads/{thread['id']}")
    assert allowed.status_code == 200
    assert allowed.json()["deleted"] is True


def test_delete_project_cascades_project_threads_and_runs(client: TestClient):
    project = client.post("/v1/projects", json={"name": "delete-project"}).json()
    thread = client.post(f"/v1/projects/{project['id']}/threads", json={"title": "project-thread"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    uncategorized = client.post("/v1/threads", json={"title": "uncategorized-thread"}).json()
    uncategorized_run = client.post(f"/v1/threads/{uncategorized['id']}/runs", json={}).json()
    assert client.post(
        f"/v1/projects/{project['id']}/comments",
        json={"run_id": run["id"], "target_type": "run", "target_id": run["id"], "body": "to-delete"},
    ).status_code == 200

    deleted = client.delete(f"/v1/projects/{project['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    projects = client.get("/v1/projects").json()["projects"]
    assert all(p["id"] != project["id"] for p in projects)
    threads = client.get("/v1/threads").json()["threads"]
    assert all(t["id"] != thread["id"] for t in threads)
    assert any(t["id"] == uncategorized["id"] for t in threads)
    assert client.get(f"/v1/threads/{thread['id']}/runs").status_code == 404
    assert client.get(f"/v1/threads/{uncategorized['id']}/runs").status_code == 200
    assert client.app.state.db.get_run_context(run["id"]) is None
    assert client.app.state.db.get_run_context(uncategorized_run["id"]) is not None


def test_delete_project_cascades_threads_runs_events_comments(client: TestClient):
    login_as(client, "cascade-owner")
    project = client.post("/v1/projects", json={"name": "cascade-project"}).json()
    thread = client.post(f"/v1/projects/{project['id']}/threads", json={"title": "cascade-thread"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    event_payload = {
        "kind": "user_message",
        "actor": "user",
        "payload": {"text": "cascade"},
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}},
    }
    assert client.post(f"/v1/runs/{run['id']}/events", json=event_payload).status_code == 200
    comment = client.post(
        f"/v1/projects/{project['id']}/comments",
        json={"run_id": run["id"], "target_type": "run", "target_id": run["id"], "body": "cascade-note"},
    )
    assert comment.status_code == 200
    deleted = client.delete(f"/v1/projects/{project['id']}")
    assert deleted.status_code == 200
    assert all(p["id"] != project["id"] for p in client.get("/v1/projects").json()["projects"])
    assert client.get(f"/v1/threads/{thread['id']}/runs").status_code == 404
    assert client.get(f"/v1/runs/{run['id']}/events", params={"after_seq": 0}).status_code == 404
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM comments WHERE project_id = ?", (project["id"],)).fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM run_events WHERE run_id = ?", (run["id"],)).fetchone()["c"] == 0


def test_login_does_not_auto_create_default_projects(client: TestClient):
    projects = client.get("/v1/projects")
    assert projects.status_code == 200
    assert projects.json()["projects"] == []


def test_cors_allows_delete_preflight_if_app_is_cross_origin():
    app = create_app()
    with TestClient(app) as c:
        res = c.options(
            "/v1/threads/fake-thread-id",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization,x-omni-csrf",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-methods")
        allowed_headers = (res.headers.get("access-control-allow-headers") or "").lower()
        assert "authorization" in allowed_headers
        assert "x-omni-csrf" in allowed_headers


def test_comment_create_delete_emits_activity_and_validates_target(client: TestClient):
    login_as(client, "owner")
    project = client.post("/v1/projects", json={"name": "p2"}).json()
    pid = project["id"]
    thread = client.post(f"/v1/projects/{pid}/threads", json={"title": "t"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    bad = client.post(f"/v1/projects/{pid}/comments", json={"run_id": run["id"], "target_type": "event", "target_id": "missing", "body": "x"})
    assert bad.status_code == 400
    c = client.post(f"/v1/projects/{pid}/comments", json={"run_id": run["id"], "target_type": "run", "target_id": run["id"], "body": "note"})
    assert c.status_code == 200
    cid = c.json()["comment_id"]
    activity = client.get(f"/v1/projects/{pid}/activity").json()["activity"]
    assert any(a["kind"] == "comment_created" for a in activity)
    assert client.delete(f"/v1/projects/{pid}/comments/{cid}").status_code == 200


def test_viewer_cannot_delete_others_comment_and_activity_paginates(client: TestClient):
    login_as(client, "owner")
    project = client.post("/v1/projects", json={"name": "p3"}).json()
    pid = project["id"]
    client.post(f"/v1/projects/{pid}/members", json={"user_id": "viewer1", "role": "viewer"})
    thread = client.post(f"/v1/projects/{pid}/threads", json={"title": "t"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    c = client.post(f"/v1/projects/{pid}/comments", json={"run_id": run["id"], "target_type": "run", "target_id": run["id"], "body": "note"}).json()
    login_as(client, "viewer1")
    denied = client.delete(f"/v1/projects/{pid}/comments/{c['comment_id']}")
    assert denied.status_code == 403
    login_as(client, "owner")
    feed1 = client.get(f"/v1/projects/{pid}/activity?limit=1").json()["activity"]
    assert len(feed1) == 1


def test_login_sets_session_cookie_and_me_works():
    app = create_app()
    with TestClient(app) as c:
        res = c.post("/v1/auth/login", json={"username": "auth-user"})
        assert res.status_code == 200
        assert "OMNI_SESSION" in c.cookies
        me = c.get("/v1/me")
        assert me.status_code == 200
        assert me.json()["user_id"]


def test_csrf_required_for_mutating_requests():
    app = create_app()
    with TestClient(app) as c:
        c.post("/v1/auth/login", json={"username": "csrf-user"})
        no_csrf = c.post("/v1/projects", json={"name": "p"})
        assert no_csrf.status_code == 403
        token = c.get("/v1/auth/csrf").json()["csrf_token"]
        ok = c.post("/v1/projects", headers={"X-Omni-CSRF": token}, json={"name": "p"})
        assert ok.status_code == 200


def test_logout_clears_session():
    app = create_app()
    with TestClient(app) as c:
        c.post("/v1/auth/login", json={"username": "logout-user"})
        token = c.get("/v1/auth/csrf").json()["csrf_token"]
        out = c.post("/v1/auth/logout", headers={"X-Omni-CSRF": token})
        assert out.status_code == 200
        me = c.get("/v1/me")
        assert me.status_code == 401


def test_legacy_password_upgrades_to_argon2id(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "legacy.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    try:
        app = create_app()
        with TestClient(app) as c:
            c.post("/v1/auth/login", json={"username": "legacy-user", "password": "pw1"})
            db = app.state.db
            ident = db.get_identity_by_username("legacy-user")
            db.update_identity_password_hash(ident["user_id"], hashlib.sha256("pw1".encode("utf-8")).hexdigest())
            res = c.post("/v1/auth/login", json={"username": "legacy-user", "password": "pw1"})
            assert res.status_code == 200
            upgraded = db.get_identity_by_username("legacy-user")
            assert upgraded["password_hash"].startswith("$argon2id$")
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_session_rotates_on_login_and_rotate_endpoint():
    app = create_app()
    with TestClient(app) as c:
        r1 = c.post("/v1/auth/login", json={"username": "rotate-user", "password": "pw"})
        assert r1.status_code == 200
        sid1 = c.cookies.get("OMNI_SESSION")
        token = c.get("/v1/auth/csrf").json()["csrf_token"]
        r2 = c.post("/v1/auth/login", json={"username": "rotate-user", "password": "pw"})
        assert r2.status_code == 200
        sid2 = c.cookies.get("OMNI_SESSION")
        assert sid2 and sid2 != sid1
        token = c.get("/v1/auth/csrf").json()["csrf_token"]
        rot = c.post("/v1/auth/rotate", headers={"X-Omni-CSRF": token})
        assert rot.status_code == 200
        sid3 = c.cookies.get("OMNI_SESSION")
        assert sid3 and sid3 != sid2


def test_csrf_failure_emits_auth_event(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    bad = client.post("/v1/projects", json={"name": "p-no-csrf"}, headers={"X-Omni-CSRF": "bad-token"})
    assert bad.status_code == 403
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    assert any(e["kind"] == "auth_csrf_failed" for e in events)


def test_quota_enforcement_returns_429_and_emits_quota_event(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_MAX_EVENTS_PER_RUN", "OMNI_MAX_BYTES_PER_RUN"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "quota.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_MAX_EVENTS_PER_RUN"] = "100"
    os.environ["OMNI_MAX_BYTES_PER_RUN"] = "180"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "quota-user")
            _, _, run_id = bootstrap_run(c)
            payload = {"kind": "user_message", "actor": "user", "payload": {"text": "x" * 100}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}}
            assert c.post(f"/v1/runs/{run_id}/events", json=payload).status_code == 200
            over = c.post(f"/v1/runs/{run_id}/events", json=payload)
            assert over.status_code == 429
            events = c.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
            assert any(e["kind"] == "quota_exceeded" for e in events)
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_concurrent_appends_cannot_bypass_event_quota(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_MAX_EVENTS_PER_RUN"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "quota-race.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_MAX_EVENTS_PER_RUN"] = "5"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "race-user")
            _, _, run_id = bootstrap_run(c)
            payload = {"kind": "user_message", "actor": "user", "payload": {"text": "x"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}}

            def do_append():
                return c.post(f"/v1/runs/{run_id}/events", json=payload).status_code

            with ThreadPoolExecutor(max_workers=8) as ex:
                statuses = list(ex.map(lambda _: do_append(), range(10)))
            assert statuses.count(200) == 5
            assert statuses.count(429) >= 1
            events = c.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
            assert len(events) == 5
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_tool_error_notifications_disabled_by_env(tmp_path):
    keys = ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_NOTIFY_TOOL_ERRORS"]
    prev = {k: os.environ.get(k) for k in keys}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "notify-disabled.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_NOTIFY_TOOL_ERRORS"] = "false"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "notify-off-user")
            _, _, run_id = bootstrap_run(c)
            inv = c.post(
                f"/v1/runs/{run_id}/tools/invoke",
                json={"tool_id": "files.write_patch", "inputs": {"path": "x.txt", "unified_diff": "--- a/x.txt\n+++ b/x.txt\n@@\n+x\n"}},
            )
            assert inv.status_code in {200, 202}
            rows = c.get("/v1/notifications").json()["notifications"]
            assert not any(r["kind"] == "run_tool_error" for r in rows)
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_tool_error_notifications_respect_only_codes(tmp_path):
    keys = [
        "OMNI_DB_PATH",
        "OMNI_CORS_ORIGINS",
        "OMNI_DEV_MODE",
        "OMNI_WORKSPACE_ROOT",
        "OMNI_NOTIFY_TOOL_ERRORS",
        "OMNI_NOTIFY_TOOL_ERRORS_ONLY_CODES",
    ]
    prev = {k: os.environ.get(k) for k in keys}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "notify-codes.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_NOTIFY_TOOL_ERRORS"] = "true"
    os.environ["OMNI_NOTIFY_TOOL_ERRORS_ONLY_CODES"] = "MCP_ERROR"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "notify-code-user")
            _, _, run_id = bootstrap_run(c)
            inv = c.post(
                f"/v1/runs/{run_id}/tools/invoke",
                json={"tool_id": "files.write_patch", "inputs": {"path": "x.txt", "unified_diff": "--- a/x.txt\n+++ b/x.txt\n@@\n+x\n"}},
            )
            assert inv.status_code in {200, 202}
            rows = c.get("/v1/notifications").json()["notifications"]
            assert not any(r["kind"] == "run_tool_error" for r in rows)
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_tool_error_notifications_per_run_cap(tmp_path):
    keys = [
        "OMNI_DB_PATH",
        "OMNI_CORS_ORIGINS",
        "OMNI_DEV_MODE",
        "OMNI_WORKSPACE_ROOT",
        "OMNI_NOTIFY_TOOL_ERRORS",
        "OMNI_NOTIFY_TOOL_ERRORS_ONLY_CODES",
        "OMNI_NOTIFY_TOOL_ERRORS_ONLY_BINDINGS",
        "OMNI_NOTIFY_TOOL_ERRORS_MAX_PER_RUN",
    ]
    prev = {k: os.environ.get(k) for k in keys}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "notify-cap.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_NOTIFY_TOOL_ERRORS"] = "true"
    os.environ["OMNI_NOTIFY_TOOL_ERRORS_ONLY_CODES"] = ""
    os.environ["OMNI_NOTIFY_TOOL_ERRORS_ONLY_BINDINGS"] = ""
    os.environ["OMNI_NOTIFY_TOOL_ERRORS_MAX_PER_RUN"] = "1"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "notify-cap-user")
            _, _, run_id = bootstrap_run(c)
            for _ in range(3):
                inv = c.post(
                    f"/v1/runs/{run_id}/tools/invoke",
                    json={"tool_id": "files.write_patch", "inputs": {"path": "x.txt", "unified_diff": "--- a/x.txt\n+++ b/x.txt\n@@\n+x\n"}},
                )
                assert inv.status_code in {200, 202}
            rows = c.get("/v1/notifications").json()["notifications"]
            assert len([r for r in rows if r["kind"] == "run_tool_error"]) == 1
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.slow
def test_activity_stream_once_order_and_resume(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "c1"})
    client.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "c2"})
    stream = client.get(f"/v1/projects/{project_id}/activity/stream", params={"after_seq": 0, "once": "true"})
    assert stream.status_code == 200
    chunks = [line for line in stream.text.splitlines() if line.startswith("data: ")]
    rows = [obj for obj in (json.loads(line[6:]) for line in chunks) if isinstance(obj, dict) and "activity_seq" in obj]
    assert rows
    seqs = [int(r["activity_seq"]) for r in rows]
    assert seqs == sorted(seqs)

    last = seqs[-1]
    client.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "c3"})
    resumed = client.get(f"/v1/projects/{project_id}/activity/stream", params={"after_seq": last, "once": "true"})
    assert resumed.status_code == 200
    resumed_rows = [obj for obj in (json.loads(line[6:]) for line in resumed.text.splitlines() if line.startswith("data: ")) if isinstance(obj, dict) and "activity_seq" in obj]
    assert resumed_rows
    assert all(int(r["activity_seq"]) > last for r in resumed_rows)


@pytest.mark.slow
def test_activity_stream_rbac_denied_for_non_member(client: TestClient):
    project_id, _, _ = bootstrap_run(client)
    login_as(client, "non-member-user")
    denied = client.get(f"/v1/projects/{project_id}/activity/stream", params={"after_seq": 0, "once": "true"})
    assert denied.status_code == 403


@pytest.mark.slow
def test_activity_stream_heartbeat(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_SSE_HEARTBEAT_S", "OMNI_SSE_POLL_INTERVAL_S"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "heartbeat.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_SSE_HEARTBEAT_S"] = "0.1"
    os.environ["OMNI_SSE_POLL_INTERVAL_S"] = "0.05"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "heartbeat-user")
            project_id, _, _ = bootstrap_run(c)
            resp = c.get(f"/v1/projects/{project_id}/activity/stream", params={"once": "true"})
            assert resp.status_code == 200
            assert "event: heartbeat" in resp.text
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.slow
def test_sse_replay_cap_once_for_run_and_activity(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_SSE_MAX_REPLAY"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "replay-cap.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_SSE_MAX_REPLAY"] = "1"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "cap-user")
            project_id, _, run_id = bootstrap_run(c)
            payload = {"kind": "user_message", "actor": "user", "payload": {"text": "x"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}}
            c.post(f"/v1/runs/{run_id}/events", json=payload)
            c.post(f"/v1/runs/{run_id}/events", json=payload)
            run_stream = c.get(f"/v1/runs/{run_id}/events/stream", params={"after_seq": 0, "once": "true"})
            run_data_lines = [line for line in run_stream.text.splitlines() if line.startswith("data: ") and "\"run_id\"" in line]
            assert len(run_data_lines) == 1

            c.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "a"})
            c.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "b"})
            act_stream = c.get(f"/v1/projects/{project_id}/activity/stream", params={"after_seq": 0, "once": "true"})
            act_rows = [obj for obj in (json.loads(line[6:]) for line in act_stream.text.splitlines() if line.startswith("data: ")) if isinstance(obj, dict) and "activity_seq" in obj]
            assert len(act_rows) == 1
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.slow
def test_run_stream_resume_with_last_event_id(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    payload = {"kind": "user_message", "actor": "user", "payload": {"text": "x"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}}
    c1 = client.post(f"/v1/runs/{run_id}/events", json=payload).json()
    client.post(f"/v1/runs/{run_id}/events", json=payload)
    resumed = client.get(f"/v1/runs/{run_id}/events/stream", params={"once": "true"}, headers={"Last-Event-ID": str(c1["seq"])})
    rows = [obj for obj in (json.loads(line[6:]) for line in resumed.text.splitlines() if line.startswith("data: ")) if isinstance(obj, dict) and "seq" in obj]
    assert rows
    assert all(int(r["seq"]) > int(c1["seq"]) for r in rows)


def test_activity_unread_mark_seen(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/comments", json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "u1"})
    unread = client.get(f"/v1/projects/{project_id}/activity/unread").json()
    assert unread["unread_count"] >= 1
    seen = client.post(f"/v1/projects/{project_id}/activity/mark_seen", json={"seq": unread["max_activity_seq"]}).json()
    assert seen["unread_count"] == 0


def test_notification_created_on_comment_for_other_member_not_actor(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "viewer-notify")
    viewer_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": viewer_id, "role": "viewer"})
    login_as(client, "viewer-notify")
    unread0 = client.get("/v1/notifications/unread_count").json()["unread_count"]
    login_as(client, "dev-user")
    c = client.post(
        f"/v1/projects/{project_id}/comments",
        json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "notify"},
    )
    assert c.status_code == 200
    own_unread = client.get("/v1/notifications/unread_count").json()["unread_count"]
    login_as(client, "viewer-notify")
    unread1 = client.get("/v1/notifications/unread_count").json()["unread_count"]
    assert unread1 >= unread0 + 1
    assert own_unread >= 0


def test_notifications_unread_count_and_mark_read_deterministic(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "reader")
    reader_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": reader_id, "role": "viewer"})
    login_as(client, "dev-user")
    for i in range(2):
        client.post(
            f"/v1/projects/{project_id}/comments",
            json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": f"n{i}"},
        )
    login_as(client, "reader")
    rows = client.get("/v1/notifications", params={"limit": 50}).json()["notifications"]
    assert len(rows) >= 2
    unread_before = client.get("/v1/notifications/unread_count").json()["unread_count"]
    ids = [rows[0]["notification_id"]]
    mark_one = client.post("/v1/notifications/mark_read", json={"notification_ids": ids})
    assert mark_one.status_code == 200
    unread_mid = mark_one.json()["unread_count"]
    assert unread_mid <= unread_before
    max_seq = max(int(r["notification_seq"]) for r in rows[:2])
    mark_all = client.post("/v1/notifications/mark_read", json={"up_to_seq": max_seq})
    assert mark_all.status_code == 200
    assert mark_all.json()["unread_count"] <= unread_mid


def test_notifications_mark_read_is_idempotent_with_key(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "reader-idem")
    reader_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": reader_id, "role": "viewer"})
    client.post(
        f"/v1/projects/{project_id}/comments",
        json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "idem-notify"},
    )
    login_as(client, "reader-idem")
    rows = client.get("/v1/notifications", params={"limit": 50}).json()["notifications"]
    assert rows
    up_to_seq = max(int(r["notification_seq"]) for r in rows)
    idem = "idem-notifications-mark-read-1"
    first = client.post(
        "/v1/notifications/mark_read",
        json={"up_to_seq": up_to_seq},
        headers={"X-Omni-Idempotency-Key": idem},
    )
    second = client.post(
        "/v1/notifications/mark_read",
        json={"up_to_seq": up_to_seq},
        headers={"X-Omni-Idempotency-Key": idem},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    unread = client.get("/v1/notifications/unread_count").json()["unread_count"]
    assert unread == first.json()["unread_count"]


def test_notifications_mark_read_same_header_different_body_is_not_replay(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "reader-idem-body")
    reader_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": reader_id, "role": "viewer"})
    for i in range(3):
        client.post(
            f"/v1/projects/{project_id}/comments",
            json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": f"idem-body-{i}"},
        )
    login_as(client, "reader-idem-body")
    rows = client.get("/v1/notifications", params={"limit": 50}).json()["notifications"]
    assert len(rows) >= 3
    ordered = sorted(rows, key=lambda r: int(r["notification_seq"]))
    s1 = int(ordered[0]["notification_seq"])
    s2 = int(ordered[2]["notification_seq"])
    assert s2 > s1

    before = client.get("/v1/system/stats").json().get("counters", {})
    store0 = int(before.get("idempotency_stores_total", 0))
    hit0 = int(before.get("idempotency_hits_total", 0))

    idem = "fixed-key"
    r1 = client.post(
        "/v1/notifications/mark_read",
        json={"up_to_seq": s1},
        headers={"X-Omni-Idempotency-Key": idem},
    )
    assert r1.status_code == 200
    b1 = r1.json()
    seq1 = int(b1.get("last_seen_notification_seq", client.get("/v1/notifications/state").json()["last_seen_notification_seq"]))
    assert seq1 >= s1

    r2 = client.post(
        "/v1/notifications/mark_read",
        json={"up_to_seq": s2},
        headers={"X-Omni-Idempotency-Key": idem},
    )
    assert r2.status_code == 200
    b2 = r2.json()
    seq2 = int(b2.get("last_seen_notification_seq", client.get("/v1/notifications/state").json()["last_seen_notification_seq"]))
    assert seq2 >= s2
    assert seq2 > seq1
    assert b2 != b1

    r3 = client.post(
        "/v1/notifications/mark_read",
        json={"up_to_seq": s2},
        headers={"X-Omni-Idempotency-Key": idem},
    )
    assert r3.status_code == 200
    b3 = r3.json()
    assert b3 == b2

    after = client.get("/v1/system/stats").json().get("counters", {})
    assert int(after.get("idempotency_stores_total", 0)) == store0 + 2
    assert int(after.get("idempotency_hits_total", 0)) == hit0 + 1


def test_notifications_mark_read_up_to_seq_marks_expected_subset(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "reader-seq")
    reader_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": reader_id, "role": "viewer"})
    for i in range(3):
        client.post(
            f"/v1/projects/{project_id}/comments",
            json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": f"seq-{i}"},
        )
    login_as(client, "reader-seq")
    rows = client.get("/v1/notifications", params={"limit": 50}).json()["notifications"]
    assert len(rows) >= 3
    ordered = sorted(rows, key=lambda r: int(r["notification_seq"]))
    target_seq = int(ordered[1]["notification_seq"])
    res = client.post("/v1/notifications/mark_read", json={"up_to_seq": target_seq})
    assert res.status_code == 200
    refreshed = client.get("/v1/notifications", params={"limit": 50}).json()["notifications"]
    read_rows = [r for r in refreshed if r["read_at"]]
    unread_rows = [r for r in refreshed if not r["read_at"]]
    assert all(int(r["notification_seq"]) <= target_seq for r in read_rows)
    assert all(int(r["notification_seq"]) > target_seq for r in unread_rows)


@pytest.mark.slow
def test_notifications_sse_once_returns_ordered_replay_and_heartbeat(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "dev-user")
    login_as(client, "sse-user")
    sse_user_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": sse_user_id, "role": "viewer"})
    login_as(client, "dev-user")
    for i in range(2):
        client.post(
            f"/v1/projects/{project_id}/comments",
            json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": f"sse-{i}"},
        )
    login_as(client, "sse-user")
    stream = client.get("/v1/notifications/stream", params={"after_seq": 0, "once": "true"})
    assert "event: heartbeat" in stream.text
    seqs = []
    for line in stream.text.splitlines():
        if not line.startswith("data: "):
            continue
        obj = json.loads(line[6:])
        if isinstance(obj, dict) and "notification_seq" in obj:
            seqs.append(int(obj["notification_seq"]))
    assert seqs == sorted(seqs)
    assert len(seqs) >= 1


@pytest.mark.slow
def test_notifications_sse_resume_with_last_event_id(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "dev-user")
    login_as(client, "resume-user")
    resume_user_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": resume_user_id, "role": "viewer"})
    login_as(client, "dev-user")
    for i in range(2):
        client.post(
            f"/v1/projects/{project_id}/comments",
            json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": f"resume-{i}"},
        )
    login_as(client, "resume-user")
    full = client.get("/v1/notifications/stream", params={"after_seq": 0, "once": "true"})
    all_rows = [json.loads(line[6:]) for line in full.text.splitlines() if line.startswith("data: ")]
    replayable = [r for r in all_rows if isinstance(r, dict) and "notification_seq" in r]
    assert len(replayable) >= 2
    first_seq = int(replayable[0]["notification_seq"])
    resumed = client.get("/v1/notifications/stream", params={"once": "true"}, headers={"Last-Event-ID": str(first_seq)})
    rows = [json.loads(line[6:]) for line in resumed.text.splitlines() if line.startswith("data: ")]
    replay = [r for r in rows if isinstance(r, dict) and "notification_seq" in r]
    assert replay
    assert all(int(r["notification_seq"]) > first_seq for r in replay)


def test_notifications_rbac_self_only(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "dev-user")
    login_as(client, "rbac-a")
    user_a_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "rbac-b")
    user_b_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": user_a_id, "role": "viewer"})
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": user_b_id, "role": "viewer"})
    login_as(client, "dev-user")
    client.post(
        f"/v1/projects/{project_id}/comments",
        json={"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "rbac"},
    )
    login_as(client, "rbac-a")
    a_rows = client.get("/v1/notifications").json()["notifications"]
    a_unread_before = client.get("/v1/notifications/unread_count").json()["unread_count"]
    assert a_rows
    client.post("/v1/notifications/mark_read", json={"notification_ids": [a_rows[0]["notification_id"]]})
    a_unread_after = client.get("/v1/notifications/unread_count").json()["unread_count"]
    assert a_unread_after <= a_unread_before
    login_as(client, "rbac-b")
    b_unread_before = client.get("/v1/notifications/unread_count").json()["unread_count"]
    b_rows = client.get("/v1/notifications").json()["notifications"]
    assert b_rows
    b_unread_after = client.get("/v1/notifications/unread_count").json()["unread_count"]
    assert b_unread_after == b_unread_before


def test_approval_required_notifies_run_creator_and_project_owners(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    login_as(client, "owner-2")
    owner2_id = client.get("/v1/me").json()["user_id"]
    login_as(client, "dev-user")
    client.post(f"/v1/projects/{project_id}/members", json={"user_id": owner2_id, "role": "owner"})
    risky_manifest = {
        "tool_id": "risky.tool",
        "version": "1.0.0",
        "title": "risky",
        "description": "risky tool",
        "inputs_schema": {"type": "object", "additionalProperties": False, "properties": {"q": {"type": "string"}}},
        "outputs_schema": {"type": "object", "additionalProperties": False, "properties": {"ok": {"type": "boolean"}}},
        "binding": {"type": "inproc_safe", "entrypoint": "omni_backend.tools_runtime:web_search"},
        "risk": {"scopes_required": [], "external_write": True, "network_egress": False, "secrets_required": []},
        "compat": {"contract_version": "v1", "min_runtime_version": "0.1"},
    }
    ins = client.post("/v1/tools/install", json={"manifest": risky_manifest})
    assert ins.status_code == 200
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "risky.tool", "inputs": {"q": "x"}})
    assert inv.status_code == 202
    assert inv.json().get("system_event", {}).get("payload", {}).get("code") == "approval_required"

    owner_rows = client.get("/v1/notifications").json()["notifications"]
    assert any(r["kind"] == "run_system_event" for r in owner_rows)
    login_as(client, "owner-2")
    owner2_rows = client.get("/v1/notifications").json()["notifications"]
    assert any(r["kind"] == "run_system_event" for r in owner2_rows)


def test_idempotency_comment_create_returns_same_response(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    idem = "idem-comment-1"
    body = {"run_id": run_id, "target_type": "run", "target_id": run_id, "body": "once"}
    first = client.post(
        f"/v1/projects/{project_id}/comments",
        json=body,
        headers={"X-Omni-Idempotency-Key": idem},
    )
    second = client.post(
        f"/v1/projects/{project_id}/comments",
        json=body,
        headers={"X-Omni-Idempotency-Key": idem},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["comment_id"] == second.json()["comment_id"]
    comments = client.get(f"/v1/projects/{project_id}/comments", params={"run_id": run_id}).json()["comments"]
    assert len([c for c in comments if c["body"] == "once"]) == 1


def test_idempotency_user_message_event_no_duplicate(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    idem = "idem-event-1"
    payload = {"kind": "user_message", "actor": "user", "payload": {"text": "hello"}, "privacy": {"redact_level": "none", "contains_secrets": False}, "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}}}
    first = client.post(f"/v1/runs/{run_id}/events", json=payload, headers={"X-Omni-Idempotency-Key": idem})
    second = client.post(f"/v1/runs/{run_id}/events", json=payload, headers={"X-Omni-Idempotency-Key": idem})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    assert len([e for e in events if e["kind"] == "user_message" and e["payload"].get("text") == "hello"]) == 1


@pytest.mark.slow
def test_artifact_init_parts_finalize_and_download(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    blob = b"hello-artifact-v2"
    h = "sha256:" + hashlib.sha256(blob).hexdigest()
    init = client.post("/v1/artifacts/init", json={"kind": "blob", "media_type": "application/octet-stream", "title": "x", "size_bytes": len(blob), "content_hash": h, "run_id": run_id})
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]
    artifact_id = init.json()["artifact_id"]
    p1 = client.put(f"/v1/artifacts/{artifact_id}/parts/1", params={"upload_id": upload_id}, content=blob[:5])
    p2 = client.put(f"/v1/artifacts/{artifact_id}/parts/2", params={"upload_id": upload_id}, content=blob[5:])
    assert p1.status_code == 200
    assert p2.status_code == 200
    fin = client.post(f"/v1/artifacts/{artifact_id}/finalize", json={"upload_id": upload_id})
    assert fin.status_code == 200
    dl = client.get(f"/v1/artifacts/{artifact_id}/download")
    assert dl.status_code == 200
    assert dl.content == blob


@pytest.mark.slow
def test_artifact_finalize_hash_mismatch_fails(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    blob = b"abcdef"
    wrong_hash = "sha256:" + hashlib.sha256(b"zzz").hexdigest()
    init = client.post("/v1/artifacts/init", json={"kind": "blob", "media_type": "application/octet-stream", "size_bytes": len(blob), "content_hash": wrong_hash, "run_id": run_id})
    upload_id = init.json()["upload_id"]
    artifact_id = init.json()["artifact_id"]
    client.put(f"/v1/artifacts/{artifact_id}/parts/1", params={"upload_id": upload_id}, content=blob)
    fin = client.post(f"/v1/artifacts/{artifact_id}/finalize", json={"upload_id": upload_id})
    assert fin.status_code == 400
    assert "hash mismatch" in fin.text


def test_link_artifact_emits_events_and_lists(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "hello"})
    assert art.status_code == 200
    artifact_id = art.json()["artifact_id"]
    link = client.post(f"/v1/runs/{run_id}/artifacts/link", json={"artifact_id": artifact_id, "purpose": "evidence"})
    assert link.status_code == 200
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    assert any(e["kind"] == "artifact_ref" and e["payload"]["artifact_id"] == artifact_id for e in events)
    assert any(e["kind"] == "artifact_linked" and e["payload"]["artifact_id"] == artifact_id for e in events)
    listed = client.get(f"/v1/runs/{run_id}/artifacts").json()["artifacts"]
    assert any(a["artifact_id"] == artifact_id for a in listed)


def test_rbac_blocks_cross_project_artifact_linking(client: TestClient):
    _, _, run1 = bootstrap_run(client)
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "hello"})
    artifact_id = art.json()["artifact_id"]
    login_as(client, "other-user")
    denied = client.post(f"/v1/runs/{run1}/artifacts/link", json={"artifact_id": artifact_id, "purpose": "x"})
    assert denied.status_code == 403


def test_provenance_graph_includes_tool_artifact_research(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "omni"}})
    assert inv.status_code == 200
    tool_result_event_id = inv.json().get("tool_result_event", {}).get("event_id")
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "p"})
    assert art.status_code == 200
    artifact_id = art.json()["artifact_id"]
    link = client.post(f"/v1/runs/{run_id}/artifacts/link", json={"artifact_id": artifact_id, "purpose": "evidence", "source_event_id": tool_result_event_id})
    assert link.status_code == 200
    rs = client.post(f"/v1/runs/{run_id}/research/start", json={"query": "OmniAI", "mode": "tool_driven", "top_k": 1})
    assert rs.status_code == 200

    graph = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert graph.status_code == 200
    g = graph.json()
    node_ids = {n["id"] for n in g["nodes"]}
    edge_kinds = {e["kind"] for e in g["edges"]}
    assert any(nid.startswith("event:") for nid in node_ids)
    assert f"artifact:{artifact_id}" in node_ids
    assert any(nid.startswith("source:") for nid in node_ids)
    assert "tool_outcome" in edge_kinds
    assert "artifact_ref" in edge_kinds
    assert "citation" in edge_kinds


def test_artifact_link_persists_structured_columns(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "omni"}})
    assert inv.status_code == 200
    tool_call = inv.json()["tool_call_event"]
    tool_result = inv.json()["tool_result_event"]
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "abc"})
    artifact_id = art.json()["artifact_id"]
    link = client.post(
        f"/v1/runs/{run_id}/artifacts/link",
        json={
            "artifact_id": artifact_id,
            "purpose": "evidence",
            "source_event_id": tool_result["event_id"],
            "correlation_id": tool_call["payload"]["correlation_id"],
            "tool_id": "web.search",
            "tool_version": "1.0.0",
        },
    )
    assert link.status_code == 200
    rows = client.app.state.db.list_artifact_links(run_id)
    row = next((r for r in rows if r["artifact_id"] == artifact_id), None)
    assert row is not None
    assert row["source_event_id"] == tool_result["event_id"]
    assert row["correlation_id"] == tool_call["payload"]["correlation_id"]
    assert row["tool_id"] == "web.search"
    assert row["tool_version"] == "1.0.0"
    assert row["purpose"] == "evidence"
    events = client.get(f"/v1/runs/{run_id}/events", params={"after_seq": 0}).json()["events"]
    linked = next((e for e in events if e["kind"] == "artifact_linked" and e["payload"]["artifact_id"] == artifact_id), None)
    assert linked is not None
    assert linked["payload"]["run_id"] == row["run_id"]
    assert linked["payload"]["source_event_id"] == row["source_event_id"]
    assert linked["payload"]["correlation_id"] == row["correlation_id"]
    assert linked["payload"]["tool_id"] == row["tool_id"]
    assert linked["payload"]["tool_version"] == row["tool_version"]
    assert linked["payload"]["purpose"] == row["purpose"]


def test_provenance_why_returns_multiple_paths_and_caps(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "omni"}}).json()
    corr = inv["tool_call_event"]["payload"]["correlation_id"]
    tool_result_event_id = inv["tool_result_event"]["event_id"]
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "shared"}).json()
    artifact_id = art["artifact_id"]
    # Path 1: explicit source_event_id.
    a = client.post(
        f"/v1/runs/{run_id}/artifacts/link",
        json={"artifact_id": artifact_id, "purpose": "p1", "source_event_id": tool_result_event_id},
    )
    assert a.status_code == 200
    # Path 2: correlation linkage to tool_call.
    b = client.post(
        f"/v1/runs/{run_id}/artifacts/link",
        json={"artifact_id": artifact_id, "purpose": "p2", "correlation_id": corr},
    )
    assert b.status_code == 200
    why = client.get(f"/v1/runs/{run_id}/provenance/why", params={"artifact_id": artifact_id, "max_paths": 1, "max_depth": 6})
    assert why.status_code == 200
    body = why.json()
    assert body["artifact_id"] == artifact_id
    assert len(body["paths"]) == 1
    assert body["truncated"] is True
    # deterministic ordering
    why2 = client.get(f"/v1/runs/{run_id}/provenance/why", params={"artifact_id": artifact_id, "max_paths": 1, "max_depth": 6})
    assert why2.status_code == 200
    assert why2.json()["paths"] == body["paths"]


def test_db_init_migrates_legacy_artifact_links_schema(tmp_path):
    db_path = tmp_path / "legacy-artifact-links.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE artifact_links(run_id TEXT NOT NULL, event_id TEXT NOT NULL, artifact_id TEXT NOT NULL, PRIMARY KEY(run_id, event_id, artifact_id))")
    conn.commit()
    conn.close()
    os.environ["OMNI_DB_PATH"] = str(db_path)
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    app = create_app()
    with TestClient(app):
        cols = {c["name"] for c in app.state.db.connect().execute("PRAGMA table_info(artifact_links)").fetchall()}
        assert "source_event_id" in cols
        assert "correlation_id" in cols
        assert "tool_id" in cols
        assert "tool_version" in cols
        assert "purpose" in cols
        assert "created_at" in cols


def test_provenance_graph_is_deterministic(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "abc"}})
    g1 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    g2 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert g1.status_code == 200
    assert g2.status_code == 200
    assert g1.json()["nodes"] == g2.json()["nodes"]
    assert g1.json()["edges"] == g2.json()["edges"]


def test_provenance_graph_cache_compute_and_hit(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "cache"}})
    g1 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert g1.status_code == 200
    cache = client.app.state.db.get_provenance_cache(run_id)
    assert cache is not None
    g2 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert g2.status_code == 200
    assert g1.json() == g2.json()


def test_ops_counters_provenance_cache_hit_and_miss(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    before = client.get("/v1/system/stats").json().get("counters", {})
    miss0 = int(before.get("provenance_cache.miss_count", 0))
    hit0 = int(before.get("provenance_cache.hit_count", 0))
    rec0 = int(before.get("provenance_cache.recompute_count", 0))
    r1 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert r1.status_code == 200
    r2 = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert r2.status_code == 200
    after = client.get("/v1/system/stats").json().get("counters", {})
    assert int(after.get("provenance_cache.miss_count", 0)) >= miss0 + 1
    assert int(after.get("provenance_cache.hit_count", 0)) >= hit0 + 1
    assert int(after.get("provenance_cache.recompute_count", 0)) >= rec0 + 1


def test_ops_counters_idempotency_hit_increments(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    before = client.get("/v1/system/stats").json().get("counters", {})
    hit0 = int(before.get("idempotency_hits_total", 0))
    store0 = int(before.get("idempotency_stores_total", 0))
    payload = {
        "kind": "user_message",
        "actor": "user",
        "payload": {"text": "hello ops"},
        "privacy": {"redact_level": "none", "contains_secrets": False},
        "pins": {"model": {"provider": "stub", "model_id": "stub-model", "params": {}, "seed": None}, "tools": [], "runtime": {"executor_version": "v0"}},
    }
    idem = "ops-idem-hit-1"
    assert client.post(f"/v1/runs/{run_id}/events", json=payload, headers={"X-Omni-Idempotency-Key": idem}).status_code == 200
    assert client.post(f"/v1/runs/{run_id}/events", json=payload, headers={"X-Omni-Idempotency-Key": idem}).status_code == 200
    after = client.get("/v1/system/stats").json().get("counters", {})
    assert int(after.get("idempotency_stores_total", 0)) >= store0 + 1
    assert int(after.get("idempotency_hits_total", 0)) >= hit0 + 1


def test_system_health_augmented_with_db_and_metrics(client: TestClient):
    _, _, run_id = bootstrap_run(client)
    client.get(f"/v1/runs/{run_id}/provenance/graph")
    health = client.get("/v1/system/health")
    assert health.status_code == 200
    body = health.json()
    assert body["db_ok"] is True
    assert "counters" in body and isinstance(body["counters"], dict)
    assert "gauges" in body and isinstance(body["gauges"], dict)
    assert "provenance_cache_age_s" in body


def test_system_config_returns_safe_operator_snapshot(client: TestClient):
    body = client.get("/v1/system/config").json()
    expected_keys = {
        "notify_tool_errors",
        "notify_tool_errors_only_codes",
        "notify_tool_errors_only_bindings",
        "notify_tool_errors_max_per_run",
        "sse_max_replay",
        "sse_heartbeat_seconds",
        "artifact_max_bytes",
        "artifact_part_size",
        "session_ttl_seconds",
        "session_sliding_enabled",
        "session_sliding_window_seconds",
        "max_events_per_run",
        "max_bytes_per_run",
        "generated_at",
        "contract_version",
        "runtime_version",
    }
    assert set(body.keys()) == expected_keys
    datetime.fromisoformat(str(body["generated_at"]).replace("Z", "+00:00"))
    assert "dev_login_password" not in body
    assert "public_key_base64" not in body
    assert "csrf_secret" not in body


def test_system_config_matches_contract_schema(client: TestClient):
    body = client.get("/v1/system/config")
    assert body.status_code == 200
    payload = body.json()
    schema_path = Path(__file__).resolve().parents[2] / "omni-contracts" / "schemas" / "system_config.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: e.path)
    assert errs == []


def test_system_config_contract_failure_hard_fails_in_dev(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT", "OMNI_SSE_HEARTBEAT_SECONDS"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "syscfg-invalid.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    os.environ["OMNI_SSE_HEARTBEAT_SECONDS"] = "0"
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "syscfg-dev")
            failed = c.get("/v1/system/config")
            assert failed.status_code == 500
            assert "contract validation failed" in failed.text
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_system_config_denied_when_not_dev_mode(tmp_path):
    prev = {k: os.environ.get(k) for k in ["OMNI_DB_PATH", "OMNI_CORS_ORIGINS", "OMNI_DEV_MODE", "OMNI_WORKSPACE_ROOT"]}
    os.environ["OMNI_DB_PATH"] = str(tmp_path / "syscfg.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "false"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / "workspaces")
    try:
        app = create_app()
        with TestClient(app) as c:
            login_as(c, "syscfg-user")
            denied = c.get("/v1/system/config")
            assert denied.status_code == 403
    finally:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_notification_state_backfill_sets_max_read_seq_and_is_non_destructive(tmp_path):
    db_path = tmp_path / "notify-backfill.db"
    db = Database(str(db_path))
    user_id = "user-backfill-1"
    db.ensure_user(user_id)
    n1 = db.create_notification(user_id=user_id, kind="k", payload={"summary": "a"})
    n2 = db.create_notification(user_id=user_id, kind="k", payload={"summary": "b"})
    n3 = db.create_notification(user_id=user_id, kind="k", payload={"summary": "c"})
    db.mark_notifications_read(user_id, notification_ids=[n1["notification_id"], n2["notification_id"]])
    with db.connect() as conn:
        conn.execute("DELETE FROM notification_state WHERE user_id = ?", (user_id,))
    db.init_db()
    state = db.get_notification_state(user_id)
    assert int(state["last_seen_notification_seq"]) == int(n2["notification_seq"])
    db.set_last_seen_notification_seq(user_id, 9999)
    db.init_db()
    state2 = db.get_notification_state(user_id)
    assert int(state2["last_seen_notification_seq"]) == 9999
    assert int(n3["notification_seq"]) < int(state2["last_seen_notification_seq"])


def test_provenance_graph_cache_invalidates_on_new_provenance_event(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "invalidate"}})
    first = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert first.status_code == 200
    assert client.app.state.db.get_provenance_cache(run_id) is not None

    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "cache-bust"}).json()
    linked = client.post(f"/v1/runs/{run_id}/artifacts/link", json={"artifact_id": art["artifact_id"], "purpose": "evidence"})
    assert linked.status_code == 200
    assert client.app.state.db.get_provenance_cache(run_id) is None

    second = client.get(f"/v1/runs/{run_id}/provenance/graph")
    assert second.status_code == 200
    node_ids = {n["id"] for n in second.json()["nodes"]}
    assert f"artifact:{art['artifact_id']}" in node_ids
    cache2 = client.app.state.db.get_provenance_cache(run_id)
    assert cache2 is not None
    assert int(cache2["last_seq"]) == int(client.app.state.db.get_run_last_seq(run_id))


def test_provenance_graph_truncation_flags(client: TestClient):
    project_id, _, run_id = bootstrap_run(client)
    client.post(f"/v1/projects/{project_id}/policy/grants", json={"scope": "read_web"})
    inv = client.post(f"/v1/runs/{run_id}/tools/invoke", json={"tool_id": "web.search", "inputs": {"query": "trunc"}})
    assert inv.status_code == 200
    tool_result_event_id = inv.json().get("tool_result_event", {}).get("event_id")
    art = client.post("/v1/artifacts", json={"kind": "document", "media_type": "text/plain", "content_text": "p"}).json()
    assert client.post(
        f"/v1/runs/{run_id}/artifacts/link",
        json={"artifact_id": art["artifact_id"], "purpose": "tiny-caps", "source_event_id": tool_result_event_id},
    ).status_code == 200
    graph = client.get(f"/v1/runs/{run_id}/provenance/graph", params={"node_cap": 1, "edge_cap": 1, "max_depth": 1})
    assert graph.status_code == 200
    body = graph.json()
    assert "truncated" in body
    assert "truncation" in body
    assert body["truncated"] is True
    assert any(bool(body["truncation"].get(k)) for k in ("node_cap_hit", "edge_cap_hit", "depth_cap_hit"))
