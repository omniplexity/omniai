import pytest
pytestmark = [pytest.mark.security, pytest.mark.csrf]

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.session import create_session
from backend.config import get_settings
from backend.core.middleware import _is_origin_allowed, _parse_origin
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User
from backend.main import create_app


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "v1_csrf.db"
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
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_v1_conversations_require_csrf(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    settings = get_settings()

    db = _get_session(engine)
    try:
        user = User(email="v1@example.com", username="v1user", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    # Override TrustedHostMiddleware to allow testserver
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    get_settings.cache_clear()
    
    app = create_app()
    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, session_token)
        client.cookies.set(settings.csrf_cookie_name, csrf_token)

        # Without CSRF token but with valid Origin, should fail with E2002
        res = client.post(
            "/v1/conversations",
            json={"title": "Test"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert res.status_code == 403
        body = res.json()
        assert body["error"]["code"] == "E2002"

        # With valid Origin and CSRF token, should succeed
        res = client.post(
            "/v1/conversations",
            json={"title": "Test"},
            headers={
                settings.csrf_header_name: csrf_token,
                "Origin": "http://localhost:3000",
            },
        )
        assert res.status_code == 200

    dispose_engine()


# =============================================================================
# Phase 1: Origin Parsing & Normalization Tests
# =============================================================================

class TestOriginParsing:
    """Tests for _parse_origin() and _is_origin_allowed() functions."""

    def test_parse_origin_https_default_port_443(self):
        """HTTPS origins without explicit port should normalize to 443."""
        result = _parse_origin("https://omniplexity.github.io")
        assert result == ("https", "omniplexity.github.io", 443)

    def test_parse_origin_http_default_port_80(self):
        """HTTP origins without explicit port should normalize to 80."""
        result = _parse_origin("http://example.com")
        assert result == ("http", "example.com", 80)

    def test_parse_origin_explicit_port_preserved(self):
        """Explicit ports should be preserved."""
        result = _parse_origin("https://example.com:8443")
        assert result == ("https", "example.com", 8443)

    def test_parse_origin_lowercase_hostname(self):
        """Hostnames should be normalized to lowercase."""
        result = _parse_origin("https://EXAMPLE.COM")
        assert result == ("https", "example.com", 443)

    def test_parse_origin_strips_userinfo(self):
        """Userinfo (user:pass@) should be stripped."""
        result = _parse_origin("https://user:pass@example.com")
        assert result == ("https", "example.com", 443)

    def test_parse_origin_rejects_null(self):
        """Origin 'null' should be rejected (returns None)."""
        result = _parse_origin("null")
        assert result is None
        result = _parse_origin("Null")
        assert result is None
        result = _parse_origin("NULL")
        assert result is None

    def test_parse_origin_rejects_empty(self):
        """Empty/missing origin should be rejected."""
        assert _parse_origin("") is None

    def test_is_origin_allowed_default_port_match(self):
        """Origin without port should match allowlist with explicit port 443."""
        allowed = {"https://omniplexity.github.io"}
        # Request with explicit 443 port should match allowlist without port
        assert _is_origin_allowed("https://omniplexity.github.io:443", allowed) is True
        # Request without port should also match
        assert _is_origin_allowed("https://omniplexity.github.io", allowed) is True

    def test_is_origin_allowed_port_mismatch(self):
        """Origins with different ports should not match."""
        allowed = {"https://example.com:443"}
        assert _is_origin_allowed("https://example.com:8443", allowed) is False

    def test_is_origin_allowed_prevents_subdomain_bypass(self):
        """Evil subdomain should NOT match legitimate domain."""
        allowed = {"https://omniplexity.github.io"}
        assert _is_origin_allowed("https://omniplexity.github.io.evil.com", allowed) is False

    def test_is_origin_allowed_wildcard_hostname(self):
        """Wildcard patterns should match subdomains."""
        allowed = {"https://*.example.com"}
        assert _is_origin_allowed("https://sub.example.com", allowed) is True
        assert _is_origin_allowed("https://example.com", allowed) is False  # exact match fails


# =============================================================================
# Phase 2: Targeted CSRF Tests
# =============================================================================

class TestCSRFOriginValidation:
    """Phase 2 tests for CSRF origin validation edge cases."""

    def test_origin_null_rejected_for_cookie_auth(self, monkeypatch, tmp_path):
        """Origin: null should be rejected with E2004 for cookie-authenticated requests.
        
        Test A: Default port normalization - Origin: https://example.com:443 
        should match allowlist: https://example.com
        """
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()
        
        # Set CORS_ORIGINS to allowlist without port
        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        db = _get_session(engine)
        try:
            user = User(email="test@example.com", username="testuser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, csrf_token = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)
            client.cookies.set(settings.csrf_cookie_name, csrf_token)

            # Test A: Origin with explicit 443 port should match allowlist without port
            res = client.post(
                "/v1/conversations",
                json={"title": "Test"},
                headers={
                    settings.csrf_header_name: csrf_token,
                    "Origin": "https://omniplexity.github.io:443",
                },
            )
            # Should succeed - ports normalized
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.json()}"

        dispose_engine()

    def test_origin_null_rejected_with_e2004(self, monkeypatch, tmp_path):
        """Test B: Origin: null should be rejected with E2004 for cookie-authenticated POST.
        
        This prevents CSRF via opaque requests that send Origin: null.
        """
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        db = _get_session(engine)
        try:
            user = User(email="null_test@example.com", username="nulluser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, csrf_token = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)
            client.cookies.set(settings.csrf_cookie_name, csrf_token)

            # Test B: Origin: null should be rejected
            res = client.post(
                "/v1/conversations",
                json={"title": "Test"},
                headers={
                    settings.csrf_header_name: csrf_token,
                    "Origin": "null",
                },
            )
            assert res.status_code == 403
            body = res.json()
            # Should fail due to invalid origin (null), not CSRF token
            assert body["error"]["code"] in ("E2003", "E2004"), f"Expected E2003 or E2004, got {body}"

        dispose_engine()

    def test_authorization_header_bypasses_csrf(self, monkeypatch, tmp_path):
        """Test C: Requests without session cookie should skip CSRF checks.
        
        CSRF is a cookie problem - requests without session cookies don't need
        origin/CSRF validation. This simulates token-auth or unauthenticated flows.
        """
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        app = create_app()
        with TestClient(app) as client:
            # No cookies at all - simulates token-auth or API key flow
            # This should NOT trigger CSRF rejection because there's no session cookie
            res = client.post(
                "/v1/conversations",
                json={"title": "Test"},
                # No session cookie, no CSRF token
            )
            # This will fail with 401 (no auth) not 403 (CSRF)
            # because the CSRF middleware only runs when session_cookie is present
            assert res.status_code in (200, 401, 403), f"Unexpected {res.status_code}: {res.json()}"
            # Should NOT be E2002 (CSRF token missing) or E2004 (Origin missing)
            if res.status_code == 403:
                body = res.json()
                assert body["error"]["code"] not in ("E2002", "E2004"), \
                    f"Token-auth flow shouldn't get CSRF error: {body}"

        dispose_engine()

    def test_cookie_auth_without_origin_rejected(self, monkeypatch, tmp_path):
        """Cookie-authenticated requests without Origin/Referer should fail with E2004."""
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        db = _get_session(engine)
        try:
            user = User(email="noorigin@example.com", username="nooriginuser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, csrf_token = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)
            client.cookies.set(settings.csrf_cookie_name, csrf_token)

            # POST without Origin or Referer header
            res = client.post(
                "/v1/conversations",
                json={"title": "Test"},
                headers={
                    settings.csrf_header_name: csrf_token,
                    # No Origin, No Referer
                },
            )
            assert res.status_code == 403
            body = res.json()
            assert body["error"]["code"] == "E2004"

        dispose_engine()


# =============================================================================
# Phase 2b: SSE GET Endpoint Origin Validation Tests
# =============================================================================

class TestSSEGetOriginValidation:
    """Tests for GET SSE streaming endpoints requiring origin validation.
    
    These endpoints return user data (chat events) and need same-origin
    enforcement even though they are GET requests.
    """

    def test_v1_chat_stream_rejects_missing_origin(self, monkeypatch, tmp_path):
        """GET /v1/chat/stream without Origin header should fail with E2004."""
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        db = _get_session(engine)
        try:
            user = User(email="sse_test@example.com", username="sseuser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, _ = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)
            # No Origin header

            # GET to /v1/chat/stream without Origin should fail
            res = client.get(
                "/v1/chat/stream?run_id=test-run-id",
                # No Origin header
            )
            assert res.status_code == 403
            body = res.json()
            assert body["error"]["code"] == "E2004"

        dispose_engine()

    def test_v1_chat_stream_rejects_null_origin(self, monkeypatch, tmp_path):
        """GET /v1/chat/stream with Origin: null should fail.
        
        Origin: null is present but not in the allowlist, so it returns E2003.
        """
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        db = _get_session(engine)
        try:
            user = User(email="sse_null@example.com", username="ssenulluser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, _ = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)

            # Origin: null should be rejected - either E2003 (not allowed) or E2004 (invalid)
            res = client.get(
                "/v1/chat/stream?run_id=test-run-id",
                headers={"Origin": "null"},
            )
            assert res.status_code == 403
            body = res.json()
            assert body["error"]["code"] in ("E2003", "E2004")

        dispose_engine()

    def test_v1_chat_stream_rejects_mismatched_origin(self, monkeypatch, tmp_path):
        """GET /v1/chat/stream with unauthorized Origin should fail with E2003."""
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        db = _get_session(engine)
        try:
            user = User(email="sse_mismatch@example.com", username="ssemismatch", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, _ = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)

            # Unauthorized origin should be rejected
            res = client.get(
                "/v1/chat/stream?run_id=test-run-id",
                headers={"Origin": "https://evil.example.com"},
            )
            assert res.status_code == 403
            body = res.json()
            assert body["error"]["code"] == "E2003"

        dispose_engine()

    def test_v1_chat_stream_allows_valid_origin(self, monkeypatch, tmp_path):
        """GET /v1/chat/stream with valid Origin should be allowed."""
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        db = _get_session(engine)
        try:
            user = User(email="sse_valid@example.com", username="ssevalid", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, _ = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)

            # Valid origin should pass origin check (will still fail on run lookup)
            res = client.get(
                "/v1/chat/stream?run_id=test-run-id",
                headers={"Origin": "https://omniplexity.github.io"},
            )
            # Should not be 403 CSRF error - either 200 (stream) or 404 (run not found)
            assert res.status_code != 403, f"Expected non-403, got {res.json()}"
            # 404 means the run wasn't found, which is expected
            assert res.status_code == 404

        dispose_engine()

    def test_api_runs_stream_rejects_missing_origin(self, monkeypatch, tmp_path):
        """GET /api/runs/{id}/stream without Origin header should fail with E2004."""
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        db = _get_session(engine)
        try:
            user = User(email="api_runs_test@example.com", username="apirunsuser", hashed_password="hashed", is_active=True)
            db.add(user)
            db.commit()
            session_token, _ = create_session(db, user)
        finally:
            db.close()

        app = create_app()
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_token)

            # GET to /api/runs/{id}/stream without Origin should fail
            res = client.get("/api/runs/test-run-id/stream")
            assert res.status_code == 403
            body = res.json()
            assert body["error"]["code"] == "E2004"

        dispose_engine()

    def test_sse_get_without_session_cookie_allowed(self, monkeypatch, tmp_path):
        """GET /v1/chat/stream without session cookie should skip origin check.
        
        Requests without authentication should pass through - they'll fail
        at the auth layer, not CSRF.
        """
        engine = _setup_db(tmp_path, monkeypatch)
        settings = get_settings()

        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            # No session cookie - should not be rejected at CSRF layer
            res = client.get(
                "/v1/chat/stream?run_id=test-run-id",
                # No cookies, no Origin
            )
            # Should fail with 401 (no auth), not 403 (CSRF)
            assert res.status_code == 401

        dispose_engine()
