"""Pytest configuration and fixtures for OmniAI backend tests.

This module sets up the test environment before any tests run, ensuring
that settings are properly configured for the test context.
"""

import os
import sys

# Ensure backend is in path for imports
_backend_path = os.path.join(os.path.dirname(__file__))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)


def pytest_configure(config):
    """Configure test environment before any tests run.
    
    This runs at pytest startup and ensures that test environment is properly
    configured. We use ENVIRONMENT=test (not development) to avoid accidentally
    relying on "dev permissiveness" that could mask production/test-only behaviors.
    
    Key test settings:
    - ENVIRONMENT=test (not development) - ensures production checks work correctly
    - ALLOWED_HOSTS includes testserver for TestClient
    - CORS_ORIGINS includes localhost:3000 for test requests
    - BOOTSTRAP_ADMIN_ENABLED=false to avoid admin creation during tests
    
    IMPORTANT: Set environment variables BEFORE importing the app to ensure
    settings are loaded with the test environment.
    """
    # Register custom markers for test categorization
    config.addinivalue_line("markers", "security: Security-related tests (required gate)")
    config.addinivalue_line("markers", "csrf: CSRF protection tests (required gate)")
    config.addinivalue_line("markers", "slow: Slow-running tests (excluded from fast)")
    config.addinivalue_line("markers", "integration: Integration tests requiring external services")
    
    # Set test environment (not development - avoids dev permissiveness)
    os.environ.setdefault("ENVIRONMENT", "test")
    
    # Ensure testserver is in allowed hosts for TestClient
    allowed_hosts = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
    if "testserver" not in allowed_hosts:
        allowed_hosts = f"{allowed_hosts},testserver"
        os.environ["ALLOWED_HOSTS"] = allowed_hosts
    
    # Set CORS origins for test requests (localhost:3000 is common in tests)
    cors_origins = os.environ.get("CORS_ORIGINS", "")
    if "localhost:3000" not in cors_origins:
        cors_origins = f"{cors_origins},http://localhost:3000" if cors_origins else "http://localhost:3000"
        os.environ["CORS_ORIGINS"] = cors_origins
    
    # Disable bootstrap admin during tests
    os.environ.setdefault("BOOTSTRAP_ADMIN_ENABLED", "false")
