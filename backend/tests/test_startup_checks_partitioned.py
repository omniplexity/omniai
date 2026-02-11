from backend.config import get_settings
from backend.core.startup_checks import validate_production_settings


def test_production_cross_site_requires_partitioned_cookie(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COOKIE_PARTITIONED", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://omniplexity.github.io")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("REQUIRED_FRONTEND_ORIGINS", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    errors = validate_production_settings(settings)

    assert any("COOKIE_PARTITIONED" in err for err in errors)


def test_production_same_site_allows_non_partitioned_cookie(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("COOKIE_PARTITIONED", "false")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("REQUIRED_FRONTEND_ORIGINS", "https://api.example.com")
    monkeypatch.setenv("CORS_ORIGINS", "https://api.example.com")
    get_settings.cache_clear()

    settings = get_settings()
    errors = validate_production_settings(settings)

    assert not any("COOKIE_PARTITIONED" in err for err in errors)

