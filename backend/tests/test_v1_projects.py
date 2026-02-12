from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User
from backend.main import create_app


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "v1_projects.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _seed_user(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = User(email="projects@example.com", username="projects-user", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _csrf = create_session(db, user)
        return token
    finally:
        db.close()


def test_v1_projects_enabled_returns_empty_list(monkeypatch, tmp_path):
    monkeypatch.setenv("FEATURE_WORKSPACE", "true")
    engine = _setup_db(tmp_path, monkeypatch)
    token = _seed_user(engine)
    settings = get_settings()

    app = create_app()
    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, token)
        res = client.get("/v1/projects")
        assert res.status_code == 200
        assert res.json() == []

    dispose_engine()


def test_v1_projects_unauthenticated_returns_401_envelope(monkeypatch, tmp_path):
    monkeypatch.setenv("FEATURE_WORKSPACE", "false")
    _setup_db(tmp_path, monkeypatch)
    app = create_app()

    with TestClient(app) as client:
        res = client.get("/v1/projects")
        assert res.status_code == 401
        body = res.json()
        assert body["error"]["code"] == "E4010"
        assert isinstance(body["error"]["message"], str)
        assert "request_id" in body["error"]

    dispose_engine()


def test_v1_projects_disabled_returns_capability_error(monkeypatch, tmp_path):
    monkeypatch.setenv("FEATURE_WORKSPACE", "false")
    engine = _setup_db(tmp_path, monkeypatch)
    token = _seed_user(engine)
    settings = get_settings()

    app = create_app()
    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, token)
        res = client.get("/v1/projects")
        assert res.status_code == 403
        body = res.json()
        assert body["error"]["code"] == "E_CAPABILITY_DISABLED"
        assert body["error"]["message"] == "Workspace capability disabled"
        assert "request_id" in body["error"]

    dispose_engine()
