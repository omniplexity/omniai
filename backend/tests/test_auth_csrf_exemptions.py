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
    db_path = tmp_path / "auth_csrf_exemptions.db"
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


def test_login_with_session_cookie_and_missing_csrf_is_rejected(monkeypatch, tmp_path):
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
            email="auth-csrf-exempt@example.test",
            username="auth-csrf-exempt",
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

        res = client.post(
            "/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "auth-csrf-exempt", "password": "StrongPass!123"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "E2002"


def test_login_requires_csrf_even_without_session_cookie(monkeypatch, tmp_path):
    _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        CORS_ORIGINS="http://localhost:3000",
    )

    with _make_client() as client:
        # No session cookie, no csrf bootstrap cookie/header.
        res = client.post(
            "/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "missing-user", "password": "missing-pass"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "E2002"


def test_login_with_csrf_can_reach_auth_validation(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        CORS_ORIGINS="http://localhost:3000",
    )
    settings = get_settings()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = User(
            email="auth-csrf-pass@example.test",
            username="auth-csrf-pass",
            hashed_password=hash_password("StrongPass!123"),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    with _make_client() as client:
        # Bootstrap csrf cookie first.
        csrf = client.get("/v1/auth/csrf/bootstrap").json()["csrf_token"]
        client.cookies.set(settings.csrf_cookie_name, csrf)
        res = client.post(
            "/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                settings.csrf_header_name: csrf,
            },
            json={"username": "auth-csrf-pass", "password": "StrongPass!123"},
        )
        assert res.status_code == 200


def test_chat_still_requires_csrf_with_session_cookie(monkeypatch, tmp_path):
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
            email="auth-csrf-chat@example.test",
            username="auth-csrf-chat",
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

        res = client.post(
            "/v1/chat",
            headers={"Origin": "http://localhost:3000"},
            json={"conversation_id": "missing", "input": "hello", "stream": True},
        )
        assert res.status_code == 403
        body = res.json()
        assert body["error"]["code"] == "E2002"


def test_auth_endpoints_still_enforce_origin_validation(monkeypatch, tmp_path):
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
            email="auth-origin-check@example.test",
            username="auth-origin-check",
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

        res = client.post(
            "/v1/auth/login",
            headers={"Origin": "https://evil.example.com"},
            json={"username": "auth-origin-check", "password": "StrongPass!123"},
        )
        assert res.status_code == 403
        body = res.json()
        assert body["error"]["code"] == "E2003"


def test_auth_origin_allows_localhost_in_seeded_test_mode(monkeypatch, tmp_path):
    _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        E2E_SEED_USER="1",
        CORS_ORIGINS="https://omniplexity.github.io",
    )

    with _make_client() as client:
        res = client.post(
            "/v1/auth/login",
            headers={"Origin": "http://127.0.0.1:5173"},
            json={"username": "seeded-user", "password": "seeded-pass"},
        )
        assert res.status_code == 403
        body = res.json()
        # Localhost origin should pass origin validation; CSRF should fail next.
        assert body["error"]["code"] == "E2002"
