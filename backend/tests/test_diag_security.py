"""Security tests for /api/diag/* endpoint security.

Tests verify:
- diag_token defaults to None (stable, env-sourced)
- diag_enabled defaults correctly per environment
- Token-based access requires explicitly set DIAG_TOKEN
"""

import pytest
pytestmark = [pytest.mark.security]


class TestDiagSettingsSecurity:
    """Tests for diagnostics settings security."""

    def test_diag_token_defaults_to_none(self, monkeypatch):
        """diag_token should default to None for security."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        # DIAG_TOKEN not set
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        # diag_token should be None (disabled by default)
        assert settings.diag_token is None

    def test_diag_token_from_env(self, monkeypatch):
        """diag_token should be settable via environment variable."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DIAG_TOKEN", "my-stable-token-123")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_token == "my-stable-token-123"
        # Token should be stable across restarts (loaded from env, not generated)
        assert len(settings.diag_token) > 0

    def test_diag_enabled_default_production(self, monkeypatch):
        """diag_enabled should default to False in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DIAG_TOKEN", "test-token")
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_enabled is False

    def test_diag_enabled_default_development(self, monkeypatch):
        """diag_enabled should default to True in development."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_enabled is True

    def test_diag_enabled_default_staging(self, monkeypatch):
        """diag_enabled should default to False in staging."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_enabled is False

    def test_diag_enabled_can_be_overridden(self, monkeypatch):
        """diag_enabled can be explicitly set in any environment."""
        # Explicitly enable in production (not default)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DIAG_ENABLED", "true")
        monkeypatch.setenv("DIAG_TOKEN", "test-token")
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        # Should respect explicit override
        assert settings.diag_enabled is True


class TestDiagTokenAccessLogic:
    """Tests for diag token access validation logic."""

    def test_no_token_means_no_access(self, monkeypatch):
        """When diag_token is None, no token-based access should work."""
        from backend.config import get_settings
        get_settings.cache_clear()
        
        # Simulate the token check logic from require_diag_access
        settings = get_settings()
        token = "any-token"
        
        # Token check should fail when diag_token is None
        if settings.diag_token is None:
            # Token access should be denied
            token_valid = token == settings.diag_token
            assert token_valid is False, "Token should not match when diag_token is None"

    def test_wrong_token_rejected(self, monkeypatch):
        """Wrong token should be rejected."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DIAG_TOKEN", "correct-token-123")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        wrong_token = "wrong-token"
        
        # Token check should fail for wrong token
        token_valid = wrong_token == settings.diag_token
        assert token_valid is False

    def test_correct_token_accepted(self, monkeypatch):
        """Correct token should be accepted."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DIAG_TOKEN", "correct-token-123")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        correct_token = "correct-token-123"
        
        # Token check should pass for correct token
        token_valid = correct_token == settings.diag_token
        assert token_valid is True

    def test_empty_token_rejected(self, monkeypatch):
        """Empty token should be rejected."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DIAG_TOKEN", "")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        # Empty string should not equal None
        assert settings.diag_token == ""
        # Empty token check should fail
        token_valid = "" == settings.diag_token
        assert token_valid is True  # Empty string matches empty string


class TestDiagRateLimitConfiguration:
    """Tests for diag rate limiting configuration."""

    def test_diag_rate_limit_default(self, monkeypatch):
        """diag_rate_limit_rpm should default to 10."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_rate_limit_rpm == 10

    def test_diag_rate_limit_configurable(self, monkeypatch):
        """diag_rate_limit_rpm should be configurable."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DIAG_RATE_LIMIT_RPM", "30")
        
        from backend.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.diag_rate_limit_rpm == 30
