"""Tests for log redaction functionality."""

import pytest
pytestmark = pytest.mark.security

from backend.core.logging import redact_sensitive_data


class TestRedactSensitiveData:
    """Tests for redact_sensitive_data function."""

    def test_authorization_header_redacted(self):
        """Authorization header should be redacted."""
        data = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"}
        result = redact_sensitive_data(data)
        assert result["Authorization"] != "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        assert "***" in result["Authorization"]
        # Should preserve first and last 3 chars
        assert result["Authorization"].startswith("Bea")  # "Bearer" -> "Bea"
        assert result["Authorization"].endswith("est")  # ".test" -> "est"

    def test_cookie_header_redacted(self):
        """Cookie header should have values masked."""
        data = {"cookie": "omni_session=abc123secret; omni_csrf=xyz789token"}
        result = redact_sensitive_data(data)
        # Cookie values should be masked (first/last 3 chars preserved)
        assert "abc123secret" not in result["cookie"]
        assert "xyz789token" not in result["cookie"]
        assert "***" in result["cookie"]  # Uses standard masking pattern

    def test_csrf_header_redacted(self):
        """CSRF token header should be redacted."""
        data = {"X-CSRF-Token": "super_secret_csrf_token_value_12345"}
        result = redact_sensitive_data(data)
        assert "super_secret_csrf_token_value_12345" not in result["X-CSRF-Token"]
        assert "***" in result["X-CSRF-Token"]

    def test_nested_dict_redaction(self):
        """Nested dictionaries should be redacted recursively."""
        data = {
            "headers": {
                "Authorization": "Bearer secret_token",
                "Content-Type": "application/json",
            },
            "message": "test",
        }
        result = redact_sensitive_data(data)
        # Authorization should be redacted
        assert result["headers"]["Authorization"] != "Bearer secret_token"
        # Content-Type should be preserved
        assert result["headers"]["Content-Type"] == "application/json"

    def test_list_redaction(self):
        """Lists should have each item redacted."""
        data = {
            "items": [
                {"Authorization": "Bearer token1"},
                {"Authorization": "Bearer token2"},
            ]
        }
        result = redact_sensitive_data(data)
        assert result["items"][0]["Authorization"] != "Bearer token1"
        assert result["items"][1]["Authorization"] != "Bearer token2"

    def test_non_dict_preserved(self):
        """Non-dict values should be preserved."""
        data = {"message": "test message", "count": 42}
        result = redact_sensitive_data(data)
        assert result["message"] == "test message"
        assert result["count"] == 42

    def test_token_like_string_redacted(self):
        """Long token-like strings should be partially redacted."""
        data = {"token": "abcdefghijklmnopqrstuvwxyz123456"}
        result = redact_sensitive_data(data)
        assert result["token"] != data["token"]
        assert result["token"].startswith("abc")
        assert result["token"].endswith("456")  # "123456" -> last 3 chars

    def test_short_string_preserved(self):
        """Short non-token strings should be preserved."""
        data = {"code": "abc123", "message": "hello world"}
        result = redact_sensitive_data(data)
        # Non-token short strings are preserved
        assert result["code"] == "abc123"
        assert result["message"] == "hello world"

    def test_short_token_fully_masked(self):
        """Short tokens (<12 chars) should be fully masked."""
        data = {"token": "abc123xy"}
        result = redact_sensitive_data(data)
        # Short tokens should be fully masked
        assert result["token"] == "<REDACTED>"

    def test_11_char_token_fully_masked(self):
        """11-char token should be fully masked."""
        data = {"token": "abcdefghijk"}
        result = redact_sensitive_data(data)
        assert result["token"] == "<REDACTED>"

    def test_12_char_token_partially_masked(self):
        """12-char token should show first 3 and last 3 chars."""
        data = {"token": "abcdefghijkl"}
        result = redact_sensitive_data(data)
        # First 3 + *** + last 3 = 9 chars masked, but actual output shows last 4 chars
        assert result["token"].startswith("abc")
        assert result["token"].endswith("jkl")
        assert "defghi" not in result["token"]
        assert "***" in result["token"]

    def test_cookie_key_redaction(self):
        """Cookie-related keys should be redacted."""
        data = {"set-cookie": "session=secret_value"}
        result = redact_sensitive_data(data)
        # The value should be masked (cookie pattern applies)
        assert "secret_value" not in result["set-cookie"]
        assert "***" in result["set-cookie"]  # Value is masked
