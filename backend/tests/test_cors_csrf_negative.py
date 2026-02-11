from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.password import hash_password
from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User


def _setup_db(tmp_path: Path, monkeypatch, **env):
    db_path = tmp_path / "cors_csrf_negative.db"
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


def _make_client():
    from backend.main import create_app

    app = create_app()
    return TestClient(app)


def test_disallowed_origin_has_no_acao_and_no_acac(monkeypatch, tmp_path):
    _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        CORS_ORIGINS="https://omniplexity.github.io",
    )

    with _make_client() as client:
        res = client.options(
            "/v1/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        assert res.status_code in (400, 403)
        assert "access-control-allow-origin" not in res.headers
        assert "access-control-allow-credentials" not in res.headers


def test_missing_csrf_on_state_change_returns_e2002(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        CORS_ORIGINS="http://localhost:3000",
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = User(
            email="csrf-missing@example.test",
            username="csrf-missing",
            hashed_password=hash_password("StrongPass!123"),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, _csrf_token = create_session(db, user)
    finally:
        db.close()

    with _make_client() as client:
        settings = get_settings()
        client.cookies.set(settings.session_cookie_name, session_token)
        # Deliberately do not set CSRF cookie/header.
        res = client.post(
            "/v1/chat",
            headers={"Origin": "http://localhost:3000"},
            json={"message": {"role": "user", "content": "hello"}},
        )
        assert res.status_code == 403
        body = res.json()
        assert body["error"]["code"] == "E2002"


def test_cookie_attributes_in_production_login(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="production",
        CORS_ORIGINS="https://omniplexity.github.io",
        COOKIE_SECURE="true",
        COOKIE_SAMESITE="none",
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        db.add(
            User(
                email="cookie-prod@example.test",
                username="cookie-prod",
                hashed_password=hash_password("StrongPass!123"),
                is_active=True,
                is_admin=False,
            )
        )
        db.commit()
    finally:
        db.close()

    with _make_client() as client:
        res = client.post(
            "/v1/auth/login",
            json={"username": "cookie-prod", "password": "StrongPass!123"},
        )
        assert res.status_code == 200
        set_cookie = res.headers.get("set-cookie", "")
        assert "omni_session=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=None" in set_cookie
        assert "Secure" in set_cookie

