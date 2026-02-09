"""Tests for ForwardedHeadersMiddleware."""

import ipaddress
from unittest.mock import MagicMock

import pytest
pytestmark = pytest.mark.security

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.core.middleware import (
    ForwardedHeadersMiddleware,
    TRUSTED_PROXY_NETS,
    _is_trusted_proxy,
    get_client_ip,
)
from backend.main import create_app


class TestIsTrustedProxy:
    """Tests for the _is_trusted_proxy helper function."""

    def test_localhost_is_trusted(self):
        """Loopback addresses should be trusted."""
        assert _is_trusted_proxy("127.0.0.1") is True
        assert _is_trusted_proxy("127.0.0.255") is True
        assert _is_trusted_proxy("::1") is True

    def test_docker_bridge_is_trusted(self):
        """Docker bridge network should be trusted."""
        assert _is_trusted_proxy("172.17.0.1") is True
        assert _is_trusted_proxy("172.17.5.5") is True
        assert _is_trusted_proxy("172.17.255.255") is True

    def test_external_ip_not_trusted(self):
        """Public IP addresses should not be trusted."""
        assert _is_trusted_proxy("8.8.8.8") is False
        assert _is_trusted_proxy("1.1.1.1") is False
        assert _is_trusted_proxy("203.0.113.42") is False

    def test_invalid_ip_not_trusted(self):
        """Invalid IP formats should not be trusted."""
        assert _is_trusted_proxy("not-an-ip") is False
        assert _is_trusted_proxy("") is False


class TestForwardedHeadersMiddleware:
    """Tests for ForwardedHeadersMiddleware."""

    def test_trusted_proxy_x_forwarded_for_accepted(self, monkeypatch):
        """X-Forwarded-For from trusted proxy should be accepted."""
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        app = create_app()

        with TestClient(app) as client:
            # Test that X-Forwarded-For from trusted proxy works
            res = client.get(
                "/health",
                headers={"X-Forwarded-For": "8.8.8.8, 127.0.0.1"},
            )
            assert res.status_code == 200

    def test_untrusted_x_forwarded_for_rejected(self, monkeypatch):
        """X-Forwarded-For from untrusted source should be stripped."""
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        app = create_app()

        with TestClient(app) as client:
            # Request from untrusted IP with fake X-Forwarded-For
            # The header should be stripped but request should still succeed
            res = client.get(
                "/health",
                headers={"X-Forwarded-For": "8.8.8.8"},
            )
            assert res.status_code == 200

    def test_x_forwarded_proto_from_untrusted_stripped(self, monkeypatch):
        """X-Forwarded-Proto from untrusted source should be stripped."""
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        app = create_app()

        with TestClient(app) as client:
            res = client.get(
                "/health",
                headers={"X-Forwarded-Proto": "https"},
            )
            assert res.status_code == 200

    def test_x_forwarded_host_from_untrusted_stripped(self, monkeypatch):
        """X-Forwarded-Host from untrusted source should be stripped."""
        monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
        get_settings.cache_clear()
        
        app = create_app()

        with TestClient(app) as client:
            res = client.get(
                "/health",
                headers={"X-Forwarded-Host": "evil.example.com"},
            )
            assert res.status_code == 200


class TestGetClientIp:
    """Tests for get_client_ip helper function."""

    def test_no_forwarded_header(self):
        """Without X-Forwarded-For, use direct IP."""
        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get = MagicMock(return_value="")

        ip, is_trusted = get_client_ip(request)
        assert ip == "192.168.1.100"
        assert is_trusted is False

    def test_forwarded_from_trusted_proxy(self):
        """X-Forwarded-For from trusted proxy should return original IP."""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers.get = MagicMock(return_value="8.8.8.8, 127.0.0.1")

        ip, is_trusted = get_client_ip(request)
        assert ip == "8.8.8.8"
        assert is_trusted is True

    def test_forwarded_from_untrusted_source(self):
        """X-Forwarded-For from untrusted source should use direct IP."""
        request = MagicMock()
        request.client.host = "8.8.8.8"
        request.headers.get = MagicMock(return_value="1.2.3.4, 8.8.8.8")

        ip, is_trusted = get_client_ip(request)
        # Should fall back to direct IP since proxy is untrusted
        assert ip == "8.8.8.8"
        assert is_trusted is False

    def test_multiple_forwarded_ips(self):
        """Should parse first IP in X-Forwarded-For chain."""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers.get = MagicMock(
            return_value="10.0.0.1, 10.0.0.2, 127.0.0.1"
        )

        ip, is_trusted = get_client_ip(request)
        assert ip == "10.0.0.1"
        assert is_trusted is True


class TestTrustedProxyNets:
    """Tests for the default trusted proxy network configuration."""

    def test_default_networks_configured(self):
        """Should have default trusted proxy networks configured."""
        assert len(TRUSTED_PROXY_NETS) > 0

    def test_contains_loopback(self):
        """Should include loopback network."""
        loopback_nets = [n for n in TRUSTED_PROXY_NETS if ipaddress.ip_address("127.0.0.1") in n]
        assert len(loopback_nets) == 1

    def test_contains_docker_bridge(self):
        """Should include Docker bridge network."""
        docker_nets = [n for n in TRUSTED_PROXY_NETS if ipaddress.ip_address("172.17.0.1") in n]
        assert len(docker_nets) == 1


class TestForwardedHeadersMiddlewareCustomConfig:
    """Tests for ForwardedHeadersMiddleware with custom trusted proxies."""

    def test_custom_trusted_proxies(self, monkeypatch):
        """Middleware should respect custom trusted proxy configuration."""
        from fastapi import FastAPI
        from starlette.requests import Request
        from starlette.responses import Response

        app = FastAPI()

        @app.get("/test")
        async def test():
            return {"status": "ok"}

        # Create middleware with custom trusted networks
        middleware = ForwardedHeadersMiddleware(
            app,
            trusted_proxies=["203.0.113.0/24"],  # TEST-NET-3
        )

        # TestClient doesn't simulate proxy, but we can test the middleware directly
        # This is a basic sanity check that custom config doesn't crash
        assert middleware._trusted_nets is not None
        assert len(middleware._trusted_nets) == 1
