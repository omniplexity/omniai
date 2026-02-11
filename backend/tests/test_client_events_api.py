from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User
from backend.main import create_app


def _setup_db(
    tmp_path: Path,
    monkeypatch,
    *,
    enabled: bool = True,
    rpm: int = 120,
    max_sample_rate: float = 0.1,
    force_sample_rate: float | None = None,
    sampling_mode: str = "hash",
    max_batch: int = 50,
):
    db_path = tmp_path / "client_events.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("CLIENT_EVENTS_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("CLIENT_EVENTS_RPM", str(rpm))
    monkeypatch.setenv("CLIENT_EVENTS_MAX_SAMPLE_RATE", str(max_sample_rate))
    monkeypatch.setenv("CLIENT_EVENTS_SAMPLING_MODE", sampling_mode)
    monkeypatch.setenv("CLIENT_EVENTS_MAX_BATCH", str(max_batch))
    if force_sample_rate is None:
        monkeypatch.delenv("CLIENT_EVENTS_FORCE_SAMPLE_RATE", raising=False)
    else:
        monkeypatch.setenv("CLIENT_EVENTS_FORCE_SAMPLE_RATE", str(force_sample_rate))
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _get_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def _auth_client(client: TestClient, settings, session_token: str, csrf_token: str):
    client.cookies.set(settings.session_cookie_name, session_token)
    client.cookies.set(settings.csrf_cookie_name, csrf_token)
    client.headers[settings.csrf_header_name] = csrf_token
    client.headers["Origin"] = "http://localhost:3000"


def test_client_events_disabled_returns_404(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch, enabled=False)
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce1@example.com", username="ce1", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post("/v1/client-events", json={"events": [{"type": "run_start", "run_id": "r1"}]})
        assert res.status_code == 404

    dispose_engine()


def test_client_events_enabled_accepts_valid_payload(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch, enabled=True)
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce2@example.com", username="ce2", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post(
            "/v1/client-events",
            json={"events": [{"type": "run_done", "run_id": "r1", "backend_run_id": "b1"}]},
        )
        assert res.status_code == 202
        body = res.json()
        assert "accepted_count" in body
        assert "dropped_count" in body
        assert "effective_sample_rate" in body
        assert body["sampling_mode"] == "hash"

    dispose_engine()


def test_client_events_rejects_invalid_schema(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch, enabled=True)
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce3@example.com", username="ce3", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post(
            "/v1/client-events",
            json={"events": [{"type": "run_error", "run_id": "r1", "content": "forbidden"}]},
        )
        assert res.status_code == 400

    dispose_engine()


def test_client_events_requires_auth_and_csrf(monkeypatch, tmp_path):
    _setup_db(tmp_path, monkeypatch, enabled=True)
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/v1/client-events", json={"events": [{"type": "run_start", "run_id": "r1"}]})
        assert res.status_code in (401, 403)


def test_client_events_rate_limited(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch, enabled=True, rpm=1)
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce4@example.com", username="ce4", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        ok = client.post("/v1/client-events", json={"events": [{"type": "run_start", "run_id": "r1"}]})
        assert ok.status_code == 202
        limited = client.post("/v1/client-events", json={"events": [{"type": "run_start", "run_id": "r2"}]})
        assert limited.status_code == 429

    dispose_engine()


def test_client_events_sampling_caps_client_header(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path, monkeypatch, enabled=True, max_sample_rate=0.1, sampling_mode="hash", max_batch=250
    )
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce5@example.com", username="ce5", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    events = [{"type": "run_start", "run_id": f"r{i}", "ts": f"2026-01-01T00:00:{i:02d}Z"} for i in range(200)]

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post(
            "/v1/client-events",
            headers={"X-Client-Events-Sample-Rate": "1.0"},
            json={"events": events},
        )
        assert res.status_code == 202
        body = res.json()
        assert body["effective_sample_rate"] == 0.1
        assert 5 <= body["accepted_count"] <= 40
        assert body["dropped_count"] >= 160

    dispose_engine()


def test_client_events_force_sample_overrides_client(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        enabled=True,
        max_sample_rate=0.5,
        force_sample_rate=0.02,
        sampling_mode="hash",
        max_batch=250,
    )
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce6@example.com", username="ce6", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    events = [{"type": "run_start", "run_id": f"r{i}", "ts": f"2026-01-02T00:00:{i:02d}Z"} for i in range(200)]

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post(
            "/v1/client-events",
            headers={"X-Client-Events-Sample-Rate": "1.0"},
            json={"events": events},
        )
        assert res.status_code == 202
        body = res.json()
        assert body["effective_sample_rate"] == 0.02
        assert body["accepted_count"] <= 20
        assert body["dropped_count"] >= 180

    dispose_engine()


def test_client_events_invalid_client_header_is_ignored(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch, enabled=True, max_sample_rate=0.1, max_batch=100)
    settings = get_settings()
    db = _get_session(engine)
    try:
        user = User(email="ce7@example.com", username="ce7", hashed_password="hashed", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        session_token, csrf_token = create_session(db, user)
    finally:
        db.close()

    events = [{"type": "run_start", "run_id": f"r{i}", "ts": f"2026-01-03T00:00:{i:02d}Z"} for i in range(50)]

    app = create_app()
    with TestClient(app) as client:
        _auth_client(client, settings, session_token, csrf_token)
        res = client.post(
            "/v1/client-events",
            headers={"X-Client-Events-Sample-Rate": "not-a-number"},
            json={"events": events},
        )
        assert res.status_code == 202
        body = res.json()
        assert body["effective_sample_rate"] == 0.1

    dispose_engine()
