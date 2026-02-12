from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.password import hash_password
from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "v1_auth_csrf_matrix.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _make_client():
    from backend.main import create_app

    app = create_app()
    return TestClient(app)


def test_v1_auth_login_requires_csrf(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)

    with _make_client() as client:
        res = client.post(
            "/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "x", "password": "y"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "E2002"


def test_v1_auth_logout_requires_csrf(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    settings = get_settings()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = User(
            email="matrix@example.test",
            username="matrix-user",
            hashed_password=hash_password("StrongPass!123"),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, _ = create_session(db, user)
    finally:
        db.close()

    with _make_client() as client:
        client.cookies.set(settings.session_cookie_name, session_token)
        res = client.post("/v1/auth/logout", headers={"Origin": "http://localhost:3000"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "E2002"


def test_legacy_api_csrf_bootstrap_remains_compat(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch)

    with _make_client() as client:
        res = client.get("/api/auth/csrf/bootstrap")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body.get("csrf_token"), str)
        assert body["csrf_token"] != ""
        assert res.headers.get("cache-control") == "no-store"
