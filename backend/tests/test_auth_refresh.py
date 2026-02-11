from pathlib import Path

from backend.auth.session import create_session, validate_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import Session, User
from backend.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "auth_refresh.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _get_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_refresh_rotates_session_and_csrf(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    settings = get_settings()
    user_id = None

    db = _get_session(engine)
    try:
        user = User(email="r@example.com", username="r1", hashed_password="x", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        old_session_token, old_csrf = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        # CSRF middleware requires both cookie + header match.
        client.cookies.set(settings.session_cookie_name, old_session_token)
        client.cookies.set(settings.csrf_cookie_name, old_csrf)
        res = client.post(
            "/api/auth/refresh",
            headers={
                settings.csrf_header_name: old_csrf,
                "Origin": "http://localhost:3000",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["csrf_token"] != old_csrf

    db = _get_session(engine)
    try:
        assert validate_session(db, old_session_token) is None
        active_sessions = (
            db.query(Session)
            .filter(Session.user_id == user_id)
            .all()
        )
        assert len(active_sessions) == 1
        assert active_sessions[0].csrf_token == body["csrf_token"]
    finally:
        db.close()
        dispose_engine()
