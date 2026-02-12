from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.main import create_app


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "v1_error_envelope.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def test_v1_auth_me_unauthorized_uses_canonical_envelope(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    app = create_app()

    with TestClient(app) as client:
        res = client.get("/v1/auth/me")
        assert res.status_code == 401
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "E4010"
        assert isinstance(body["error"]["message"], str)
        assert "request_id" in body["error"]

    dispose_engine()


def test_v1_auth_login_validation_uses_canonical_envelope(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        csrf = client.get(
            "/v1/auth/csrf/bootstrap",
            headers={"Origin": "http://localhost:3000"},
        ).json()["csrf_token"]
        res = client.post(
            "/v1/auth/login",
            json={},
            headers={
                "Origin": "http://localhost:3000",
                "X-CSRF-Token": csrf,
            },
            cookies={get_settings().csrf_cookie_name: csrf},
        )
        assert res.status_code == 422
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "E4220"
        assert body["error"]["message"] == "Validation error"
        assert "request_id" in body["error"]

    dispose_engine()
