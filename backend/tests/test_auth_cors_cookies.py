from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.password import hash_password
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User


def _setup_db(tmp_path: Path, monkeypatch, **env):
    db_path = tmp_path / "auth_cors_cookies.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def test_cross_origin_login_sets_session_cookie(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        COOKIE_SECURE="false",
        COOKIE_SAMESITE="lax",
        CORS_ORIGINS="http://localhost:5173",
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        db.add(
            User(
                email="e2e-auth@example.test",
                username="e2e-auth",
                hashed_password=hash_password("StrongPass!123"),
                is_admin=True,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    from backend.main import create_app

    app = create_app()
    client = TestClient(app)
    try:
        origin = "http://localhost:5173"

        boot = client.get("/v1/auth/csrf/bootstrap", headers={"Origin": origin})
        assert boot.status_code == 200
        csrf = boot.json()["csrf_token"]

        login = client.post(
            "/v1/auth/login",
            headers={"Origin": origin, "X-CSRF-Token": csrf},
            json={"username": "e2e-auth", "password": "StrongPass!123"},
        )
        assert login.status_code == 200
        set_cookie = login.headers.get("set-cookie", "")
        assert "omni_session=" in set_cookie
        assert "omni_csrf=" in set_cookie
    finally:
        dispose_engine()
        get_settings.cache_clear()

