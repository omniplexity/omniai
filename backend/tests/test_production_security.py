"""Production security tests for Phase 4 hardening."""

import pytest
pytestmark = [pytest.mark.security, pytest.mark.slow]

from backend.config import get_settings


class TestAllowedHostsValidation:
    """Tests for allowed hosts configuration validation."""

    def test_wildcard_not_allowed_in_production(self, monkeypatch):
        """Wildcard hosts should not be allowed in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,*.ngrok-free.dev")
        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        get_settings.cache_clear()
        
        with pytest.raises(ValueError, match="Wildcard"):
            get_settings()

    def test_exact_hosts_allowed_in_production(self, monkeypatch):
        """Exact hosts should be allowed in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,my-app.ngrok-free.dev")
        monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
        get_settings.cache_clear()
        
        settings = get_settings()
        assert settings.is_production
        assert "my-app.ngrok-free.dev" in settings.allowed_hosts_list
        assert "*.ngrok-free.dev" not in settings.allowed_hosts_list

    def test_localhost_hosts_allowed_in_development(self, monkeypatch):
        """Wildcard should be allowed only in dev for testing."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,*.ngrok-free.dev")
        get_settings.cache_clear()
        
        settings = get_settings()
        assert not settings.is_production
        assert "*.ngrok-free.dev" in settings.allowed_hosts_list


class TestCookieSameSiteCapitalization:
    """Tests for correct SameSite cookie capitalization."""

    def test_samesite_none_capitalized_for_header(self, monkeypatch):
        """SameSite=None should be capitalized for HTTP header."""
        monkeypatch.setenv("COOKIE_SAMESITE", "None")
        monkeypatch.setenv("COOKIE_SECURE", "true")
        get_settings.cache_clear()
        
        settings = get_settings()
        # Internal value is lowercase
        assert settings.cookie_samesite == "none"
        # Header value is capitalized
        assert settings.cookie_samesite_header == "None"

    def test_samesite_lax_capitalized_for_header(self, monkeypatch):
        """SameSite=Lax should be capitalized for HTTP header."""
        monkeypatch.setenv("COOKIE_SAMESITE", "lax")
        monkeypatch.setenv("COOKIE_SECURE", "true")
        get_settings.cache_clear()
        
        settings = get_settings()
        assert settings.cookie_samesite_header == "Lax"

    def test_samesite_strict_capitalized_for_header(self, monkeypatch):
        """SameSite=Strict should be capitalized for HTTP header."""
        monkeypatch.setenv("COOKIE_SAMESITE", "strict")
        monkeypatch.setenv("COOKIE_SECURE", "true")
        get_settings.cache_clear()
        
        settings = get_settings()
        assert settings.cookie_samesite_header == "Strict"


class TestLogRedactionShortSecrets:
    """Tests for log redaction handling of short secrets."""

    def test_short_token_fully_masked(self):
        """Short tokens (<12 chars) should be fully masked."""
        from backend.core.logging import redact_sensitive_data
        
        # 8-char token - should be fully masked
        result = redact_sensitive_data({"token": "abc123xy"})
        assert result["token"] == "<REDACTED>"

    def test_11_char_token_fully_masked(self):
        """11-char token should be fully masked."""
        from backend.core.logging import redact_sensitive_data
        
        result = redact_sensitive_data({"token": "abcdefghijk"})
        assert result["token"] == "<REDACTED>"

    def test_12_char_token_partially_masked(self):
        """12-char token should show first/last 4 chars."""
        from backend.core.logging import redact_sensitive_data
        
        result = redact_sensitive_data({"token": "abcdefghijkl"})
        # First 3 + *** + last 4 = 3 + 3 + 4 = 10 chars, but 12 total, so shows more at end
        assert result["token"].startswith("abc")
        assert result["token"].endswith("jkl")
        assert "defghi" not in result["token"]
        assert "***" in result["token"]

    def test_long_token_partially_masked(self):
        """Long tokens should show first/last 3 chars."""
        from backend.core.logging import redact_sensitive_data
        
        result = redact_sensitive_data({"token": "verylongtoken12345"})
        assert result["token"].startswith("ver")
        assert result["token"].endswith("345")
        assert "***" in result["token"]

    def test_nested_short_secret_redacted(self):
        """Short secrets in nested structures should be masked."""
        from backend.core.logging import redact_sensitive_data
        
        data = {
            "headers": {
                "Authorization": "Bearer short"
            }
        }
        result = redact_sensitive_data(data)
        # "short" is only 5 chars - the whole thing should be masked
        # But "Bearer short" is 12 chars so partial masking applies
        assert "short" not in result["headers"]["Authorization"]

    def test_token_with_hash_prefix(self):
        """Tokens with hash prefix should show prefix and first/last chars."""
        from backend.core.logging import redact_sensitive_data
        
        result = redact_sensitive_data({"token": "sha256:abcd1234efgh5678"})
        assert "sha256:" in result["token"]
        # Middle should be masked
        assert "****" in result["token"] or "***" in result["token"]


class TestPrivilegeEscalationHardening:
    """Tests for privilege escalation session handling."""

    def test_session_rotation_deletes_old_session(self, monkeypatch, tmp_path):
        """Old session should be deleted when rotating."""
        from pathlib import Path
        
        db_path = tmp_path / "priv_esc.db"
        db_url = f"sqlite:///{db_path.as_posix()}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
        monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
        get_settings.cache_clear()
        
        from backend.db import Base, dispose_engine
        from backend.db.database import get_engine
        from backend.db.models import User, Session
        from backend.auth.session import create_session, validate_session, rotate_session
        from sqlalchemy.orm import sessionmaker
        
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Create user and session
            user = User(email="test@example.com", username="test", hashed_password="x", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
            
            old_token, _ = create_session(db, user)
            
            # Verify old token is valid
            old_session = validate_session(db, old_token)
            assert old_session is not None
            
            # Rotate session
            new_token, new_csrf, new_session = rotate_session(db, old_token)
            
            # Old token should no longer be valid
            old_session_after = validate_session(db, old_token)
            assert old_session_after is None
            
            # New token should be valid
            new_session_after = validate_session(db, new_token)
            assert new_session_after is not None
            assert new_session_after.id == new_session.id
            
        finally:
            db.close()
            dispose_engine()

    def test_revoke_all_user_sessions_removes_old_sessions(self, monkeypatch, tmp_path):
        """revoke_all_user_sessions should remove all but current session."""
        from pathlib import Path
        
        db_path = tmp_path / "revoke_test.db"
        db_url = f"sqlite:///{db_path.as_posix()}"
        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
        monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
        get_settings.cache_clear()
        
        from backend.db import Base, dispose_engine
        from backend.db.database import get_engine
        from backend.db.models import User, Session
        from backend.auth.session import create_session, get_user_sessions, revoke_all_user_sessions
        from sqlalchemy.orm import sessionmaker
        
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Create user with multiple sessions
            user = User(email="test@example.com", username="test", hashed_password="x", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
            
            token1, _ = create_session(db, user)
            token2, _ = create_session(db, user)
            token3, _ = create_session(db, user)
            
            # Verify all sessions exist
            sessions = get_user_sessions(db, user.id)
            assert len(sessions) == 3
            
            # Revoke all except token1 (current)
            count = revoke_all_user_sessions(db, user.id, except_session_id=sessions[1].id)
            
            # Should have revoked 2 sessions
            assert count == 2
            
            # token2 and token3 should be invalid
            # (We'd need to check via DB since we only have token hashes)
            remaining = get_user_sessions(db, user.id)
            assert len(remaining) == 1
            
        finally:
            db.close()
            dispose_engine()
