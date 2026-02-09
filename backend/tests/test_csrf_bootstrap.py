"""Regression tests for CSRF bootstrap endpoint.

These tests ensure the public /api/auth/csrf/bootstrap endpoint works correctly
without requiring authentication, while the authenticated /api/auth/csrf endpoint
still requires a valid session.

This prevents regressions where dependencies might accidentally make the bootstrap
endpoint require authentication.
"""

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.main import create_app


pytestmark = [pytest.mark.security, pytest.mark.csrf]


def _setup_db(tmp_path, monkeypatch):
    """Set up a temporary SQLite database for testing."""
    db_path = tmp_path / "csrf_bootstrap_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _get_session(engine):
    """Get a database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


class TestCSRFBootstrapPublic:
    """Tests for the public CSRF bootstrap endpoint."""

    def test_csrf_bootstrap_returns_200_without_session(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should return 200 without a session cookie."""
        _setup_db(tmp_path, monkeypatch)
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            # No session cookie - should still work
            res = client.get("/api/auth/csrf/bootstrap")
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.json()}"

    def test_csrf_bootstrap_returns_csrf_token(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should return a csrf_token in the response."""
        _setup_db(tmp_path, monkeypatch)
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            res = client.get("/api/auth/csrf/bootstrap")
            assert res.status_code == 200
            data = res.json()
            assert "csrf_token" in data
            assert len(data["csrf_token"]) > 20  # Should be a reasonably long token

    def test_csrf_bootstrap_sets_csrf_cookie(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should set the CSRF cookie."""
        _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            res = client.get("/api/auth/csrf/bootstrap")
            assert res.status_code == 200

            # Check that CSRF cookie was set
            assert settings.csrf_cookie_name in client.cookies

    def test_csrf_bootstrap_reuses_existing_cookie(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should reuse existing CSRF cookie if present."""
        _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            # Set an initial CSRF cookie
            client.cookies.set(settings.csrf_cookie_name, "existing-token-value")

            res = client.get("/api/auth/csrf/bootstrap")
            assert res.status_code == 200

            # Should return the same token
            data = res.json()
            assert data["csrf_token"] == "existing-token-value"

    def test_csrf_bootstrap_includes_cors_headers(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should include CORS headers for cross-origin requests."""
        _setup_db(tmp_path, monkeypatch)
        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            res = client.get(
                "/api/auth/csrf/bootstrap",
                headers={"Origin": "https://omniplexity.github.io"}
            )
            assert res.status_code == 200

            # CORS headers should be present
            assert res.headers.get("Access-Control-Allow-Origin") == "https://omniplexity.github.io"
            assert res.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_csrf_bootstrap_no_cache_headers(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf/bootstrap should include no-store cache control."""
        _setup_db(tmp_path, monkeypatch)
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            res = client.get("/api/auth/csrf/bootstrap")
            assert res.status_code == 200

            # Should have no-store to prevent caching
            assert res.headers.get("Cache-Control") == "no-store"


class TestCSRFAuthenticated:
    """Tests to ensure authenticated /csrf endpoint still requires authentication."""

    def test_csrf_requires_authentication(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf should return 401 without a session cookie."""
        _setup_db(tmp_path, monkeypatch)
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            # No session cookie - should fail with 401
            res = client.get("/api/auth/csrf")
            assert res.status_code == 401
            body = res.json()
            assert "Not authenticated" in body.get("detail", "")

    def test_csrf_returns_401_for_invalid_session(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf should return 401 for an invalid session cookie."""
        _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            # Set an invalid session cookie
            client.cookies.set(settings.session_cookie_name, "invalid-session-token")

            res = client.get("/api/auth/csrf")
            assert res.status_code == 401
            body = res.json()
            assert body["error"]["code"] == "E4010"

    def test_csrf_allows_valid_session(self, monkeypatch, tmp_path):
        """GET /api/auth/csrf should return 200 with a valid session cookie."""
        from backend.db.models import User
        from backend.auth.session import create_session

        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        # Create a user and session
        db = _get_session(engine)
        try:
            user = User(
                email="test@example.com",
                username="testuser",
                hashed_password="hashed",
                is_active=True
            )
            db.add(user)
            db.commit()
            session_token, csrf_token = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            # Set valid session cookie
            client.cookies.set(settings.session_cookie_name, session_token)

            res = client.get("/api/auth/csrf")
            assert res.status_code == 200
            data = res.json()
            assert "csrf_token" in data

        dispose_engine()


class TestCSRFEndpointDistinction:
    """Tests to verify the distinction between bootstrap and authenticated endpoints."""

    def test_bootstrap_vs_authenticated_behavior(self, monkeypatch, tmp_path):
        """Verify bootstrap works without session, authenticated requires session."""
        from backend.db.models import User
        from backend.auth.session import create_session

        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        # Create a user and session
        db = _get_session(engine)
        try:
            user = User(
                email="test@example.com",
                username="testuser",
                hashed_password="hashed",
                is_active=True
            )
            db.add(user)
            db.commit()
            session_token, csrf_token = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            # Bootstrap should work without any cookies
            res_bootstrap = client.get("/api/auth/csrf/bootstrap")
            assert res_bootstrap.status_code == 200

            # Authenticated /csrf should fail without session
            res_auth = client.get("/api/auth/csrf")
            assert res_auth.status_code == 401

            # Authenticated /csrf should work with session
            client.cookies.set(settings.session_cookie_name, session_token)
            res_auth_with_session = client.get("/api/auth/csrf")
            assert res_auth_with_session.status_code == 200

        dispose_engine()
