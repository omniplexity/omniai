from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.main import create_app


def _setup_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "health_build.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def test_health_includes_build_metadata_strings(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("BUILD_SHA", "abc1234")
    monkeypatch.setenv("BUILD_TIME", "2026-02-11T07:12:34Z")
    monkeypatch.setenv("OMNIAI_ENV", "production")

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload.get("build_sha"), str)
        assert isinstance(payload.get("build_time"), str)
        assert isinstance(payload.get("environment"), str)

    dispose_engine()


def test_health_build_metadata_defaults_to_unknown(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.delenv("BUILD_SHA", raising=False)
    monkeypatch.delenv("BUILD_TIME", raising=False)
    monkeypatch.delenv("OMNIAI_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload.get("build_sha"), str)
        assert isinstance(payload.get("build_time"), str)
        assert isinstance(payload.get("environment"), str)
        assert payload["build_sha"] == "unknown"
        assert payload["build_time"] == "unknown"

    dispose_engine()
