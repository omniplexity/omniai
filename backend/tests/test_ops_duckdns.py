from pathlib import Path
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.agents.ops.duckdns_service import DuckDnsError, DuckDnsOpsService
from backend.auth.session import create_session
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import DuckDnsUpdateEvent, User
from backend.main import create_app

pytestmark = [pytest.mark.security, pytest.mark.csrf]


def _setup_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "ops_duckdns.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE_URL_POSTGRES", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("LIMITS_BACKEND", "memory")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    dispose_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def _get_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


@pytest.mark.asyncio
async def test_duckdns_service_token_missing(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DUCKDNS_TOKEN", "")
    monkeypatch.setattr(DuckDnsOpsService, "_get_token", lambda self: "")

    db = _get_session(engine)
    try:
        service = DuckDnsOpsService(db=db)
        with pytest.raises(DuckDnsError) as exc:
            await service.update(force=False, source="manual")
        assert exc.value.code == "DUCKDNS_TOKEN_MISSING"
        assert exc.value.status_code in (500, 503)
        row = db.query(DuckDnsUpdateEvent).order_by(DuckDnsUpdateEvent.created_at.desc()).first()
        assert row is not None
        assert row.error_code == "DUCKDNS_TOKEN_MISSING"
    finally:
        db.close()
        dispose_engine()


@pytest.mark.asyncio
async def test_duckdns_service_ko(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DUCKDNS_TOKEN", "a" * 32)

    async def _fake_ip(self, timeout_seconds):
        return "1.2.3.4"

    async def _fake_get(self, url, params=None, headers=None):
        return httpx.Response(200, text="KO", request=httpx.Request("GET", str(url)))

    monkeypatch.setattr(DuckDnsOpsService, "_discover_public_ip", _fake_ip)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    db = _get_session(engine)
    try:
        service = DuckDnsOpsService(db=db)
        with pytest.raises(DuckDnsError) as exc:
            await service.update(force=False, source="manual")
        assert exc.value.code == "DUCKDNS_KO"
        assert exc.value.status_code == 502
    finally:
        db.close()
        dispose_engine()


@pytest.mark.asyncio
async def test_duckdns_service_network_error(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DUCKDNS_TOKEN", "a" * 32)

    async def _fake_ip(self, timeout_seconds):
        return "1.2.3.4"

    async def _fake_get(self, url, params=None, headers=None):
        raise httpx.ConnectError("network down", request=httpx.Request("GET", url))

    monkeypatch.setattr(DuckDnsOpsService, "_discover_public_ip", _fake_ip)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    db = _get_session(engine)
    try:
        service = DuckDnsOpsService(db=db)
        with pytest.raises(DuckDnsError) as exc:
            await service.update(force=False, source="manual")
        assert exc.value.code == "DUCKDNS_NETWORK"
        assert exc.value.status_code == 504
    finally:
        db.close()
        dispose_engine()


def test_ops_duckdns_update_admin_csrf_gating(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(DuckDnsOpsService, "_get_token", lambda self: "")

    db = _get_session(engine)
    try:
        admin = User(
            email="admin_ops@example.com",
            username="admin_ops",
            hashed_password="hashed",
            is_active=True,
            is_admin=True,
        )
        user = User(
            email="user_ops@example.com",
            username="user_ops",
            hashed_password="hashed",
            is_active=True,
            is_admin=False,
        )
        db.add(admin)
        db.add(user)
        db.commit()
        db.refresh(admin)
        db.refresh(user)
        admin_session, admin_csrf = create_session(db, admin)
        user_session, user_csrf = create_session(db, user)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        # unauthenticated
        r = client.post("/v1/ops/duckdns/update", json={"force": True})
        assert r.status_code == 401

        # non-admin
        client.cookies.set(settings.session_cookie_name, user_session)
        client.cookies.set(settings.csrf_cookie_name, user_csrf)
        r = client.post(
            "/v1/ops/duckdns/update",
            json={"force": True},
            headers={"Origin": "http://localhost:3000", settings.csrf_header_name: user_csrf},
        )
        assert r.status_code == 403

        # admin but missing origin -> CSRF middleware rejection
        client.cookies.set(settings.session_cookie_name, admin_session)
        client.cookies.set(settings.csrf_cookie_name, admin_csrf)
        r = client.post(
            "/v1/ops/duckdns/update",
            json={"force": True},
            headers={settings.csrf_header_name: admin_csrf},
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "E2004"

        # admin + csrf + origin, but token missing -> DuckDNS stable code
        r = client.post(
            "/v1/ops/duckdns/update",
            json={"force": True},
            headers={"Origin": "http://localhost:3000", settings.csrf_header_name: admin_csrf},
        )
        assert r.status_code in (500, 503)
        body = r.json()
        assert body["error"]["code"] == "DUCKDNS_TOKEN_MISSING"

    dispose_engine()


def test_duckdns_status_scheduler_health(monkeypatch, tmp_path):
    engine = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setenv("OPS_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("OPS_SCHEDULER_INTERVAL_MINUTES", "5")
    get_settings.cache_clear()

    db = _get_session(engine)
    try:
        service = DuckDnsOpsService(db=db)

        # No runs recorded yet -> stale when scheduler is enabled.
        status_empty = service.get_status(scheduler_interval_minutes=5)
        assert status_empty["scheduler_enabled"] is True
        assert status_empty["scheduler_stale"] is True
        assert status_empty["scheduler_last_run_unix"] is None
        assert status_empty["scheduler_last_ok_unix"] is None
        assert status_empty["scheduler_stale_threshold_minutes"] == 10

        now = datetime.now(UTC)
        fresh = DuckDnsUpdateEvent(
            subdomain="omniplexity",
            ip="1.2.3.4",
            response="OK",
            success=True,
            error_code=None,
            error_message=None,
            latency_ms=20,
            actor_user_id=None,
            source="scheduler",
            created_at=now - timedelta(minutes=2),
        )
        db.add(fresh)
        db.commit()

        status_fresh = service.get_status(scheduler_interval_minutes=5)
        assert status_fresh["scheduler_stale"] is False
        assert status_fresh["scheduler_last_run_unix"] is not None
        assert status_fresh["scheduler_last_ok_unix"] is not None

    finally:
        db.close()
        dispose_engine()
