"""Tests for RequestSizeLimitMiddleware."""
import pytest
from backend.core.middleware import RequestSizeLimitMiddleware
from fastapi import FastAPI
from starlette.testclient import TestClient

pytestmark = pytest.mark.security


def test_rejects_large_body_by_content_length():
    """Test that requests with Content-Length exceeding limit are rejected."""
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=100)

    @app.post("/x")
    async def x(payload: dict):
        return {"ok": True}

    client = TestClient(app)
    big = {"data": "a" * 500}
    response = client.post("/x", json=big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "E4130"


def test_allows_small_body():
    """Test that requests within limit are allowed."""
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=10_000)

    @app.post("/x")
    async def x(payload: dict):
        return {"ok": True}

    client = TestClient(app)
    response = client.post("/x", json={"data": "ok"})
    assert response.status_code == 200


def test_rejects_invalid_content_length():
    """Test that invalid Content-Length header returns 400."""
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=1000)

    @app.post("/x")
    async def x(payload: dict):
        return {"ok": True}

    client = TestClient(app)
    # Manually set invalid content-length
    response = client.post(
        "/x",
        json={"data": "test"},
        headers={"content-length": "not-a-number"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "E1400"
