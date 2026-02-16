from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omni_backend.app import create_app


@pytest.fixture()
def client(tmp_path: Path):
    worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    os.environ["OMNI_DB_PATH"] = str(tmp_path / f"test-{worker}.db")
    os.environ["OMNI_CORS_ORIGINS"] = "http://localhost:5173"
    os.environ["OMNI_DEV_MODE"] = "true"
    os.environ["OMNI_WORKSPACE_ROOT"] = str(tmp_path / f"workspaces-{worker}")
    os.environ["OMNI_SSE_HEARTBEAT_SECONDS"] = "1"
    os.environ["OMNI_SSE_MAX_REPLAY"] = "50"
    app = create_app()
    with TestClient(app) as c:
        login_as(c, "dev-user")
        yield c


def login_as(client: TestClient, username: str, password: str | None = None) -> None:
    payload = {"username": username}
    if password is not None:
        payload["password"] = password
    res = client.post("/v1/auth/login", json=payload)
    assert res.status_code == 200
    csrf = client.get("/v1/auth/csrf")
    assert csrf.status_code == 200
    token = csrf.json()["csrf_token"]
    client.headers.update({"X-Omni-CSRF": token})


def bootstrap_run(client: TestClient) -> tuple[str, str, str]:
    project = client.post("/v1/projects", json={"name": "p1"}).json()
    thread = client.post(f"/v1/projects/{project['id']}/threads", json={"title": "t1"}).json()
    run = client.post(f"/v1/threads/{thread['id']}/runs", json={}).json()
    return project["id"], thread["id"], run["id"]
