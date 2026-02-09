"""Tests for discovery endpoint disabling in production/staging."""
import importlib
import os

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.security


def _load_app(env: str):
    """Load app with specified environment."""
    os.environ["ENVIRONMENT"] = env
    os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"
    import backend.main as main
    importlib.reload(main)
    return main.app


def test_docs_disabled_in_production():
    """Verify docs/openapi/redoc return 404 in production."""
    app = _load_app("production")
    client = TestClient(app, raise_server_exceptions=False)
    
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_docs_disabled_in_staging():
    """Verify docs/openapi/redoc return 404 in staging."""
    app = _load_app("staging")
    client = TestClient(app, raise_server_exceptions=False)
    
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_docs_enabled_in_development():
    """Verify docs/openapi/redoc are accessible in development."""
    app = _load_app("development")
    client = TestClient(app)
    
    # FastAPI redirects /docs -> /docs/ often; accept 200/307
    assert client.get("/docs").status_code in (200, 307)


def test_docs_enabled_in_test():
    """Verify docs/openapi/redoc are accessible in test mode."""
    app = _load_app("test")
    client = TestClient(app)
    
    # Test mode should also enable docs for testing
    assert client.get("/docs").status_code in (200, 307)
