from pathlib import Path
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import ChatRunEvent, Conversation, User
from backend.main import create_app


def _setup(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "chat_test_mode.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("E2E_SEED_USER", "1")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _seed_user(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = User(
            email="seed@example.com",
            username="seed",
            hashed_password="hashed",
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        convo = Conversation(user_id=user.id, title="Test")
        db.add(convo)
        db.commit()
        db.refresh(convo)
        session_token, csrf_token = create_session(db, user)
        return convo.id, session_token, csrf_token
    finally:
        db.close()


def test_chat_stream_deterministic_in_test_mode(monkeypatch, tmp_path):
    engine = _setup(tmp_path, monkeypatch)
    settings = get_settings()
    conversation_id, session_token, csrf_token = _seed_user(engine)
    app = create_app()

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, session_token)
        client.cookies.set(settings.csrf_cookie_name, csrf_token)
        client.headers[settings.csrf_header_name] = csrf_token
        client.headers["Origin"] = "http://127.0.0.1:5173"

        create = client.post(
            "/v1/chat",
            json={"conversation_id": conversation_id, "input": "hello", "stream": True},
        )
        assert create.status_code == 200
        run_id = create.json()["run_id"]

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        deadline = time.time() + 3.0
        found_terminal = False
        while time.time() < deadline:
            db = SessionLocal()
            try:
                events = (
                    db.query(ChatRunEvent)
                    .filter(ChatRunEvent.run_id == run_id)
                    .order_by(ChatRunEvent.seq.asc())
                    .all()
                )
                if any(evt.type == "run.status" and evt.payload_json.get("status") == "completed" for evt in events):
                    found_terminal = True
                    assert any(evt.type == "message.delta" for evt in events)
                    break
            finally:
                db.close()
            time.sleep(0.1)
        assert found_terminal

    dispose_engine()
