from pathlib import Path

from sqlalchemy.orm import sessionmaker

from backend.auth.e2e_seed import ensure_e2e_seed_user
from backend.auth.password import verify_password
from backend.config import get_settings
from backend.db import Base, dispose_engine
from backend.db.database import get_engine
from backend.db.models import User


def _setup_db(tmp_path: Path, monkeypatch, **env):
    db_path = tmp_path / "e2e_seed.db"
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


def _get_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_e2e_seed_creates_user_in_test_env(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        E2E_SEED_USER="true",
        E2E_USERNAME="e2e_admin",
        E2E_PASSWORD="StrongPass!123",
    )

    settings = get_settings()
    ensure_e2e_seed_user(settings)

    db = _get_session(engine)
    try:
        user = db.query(User).filter(User.username == "e2e_admin").first()
        assert user is not None
        assert user.is_admin is True
        assert user.is_active is True
        assert verify_password("StrongPass!123", user.hashed_password)
    finally:
        db.close()
        dispose_engine()


def test_e2e_seed_updates_existing_user_password(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="test",
        E2E_SEED_USER="true",
        E2E_USERNAME="e2e_admin",
        E2E_PASSWORD="NewStrongPass!456",
    )

    db = _get_session(engine)
    try:
        db.add(
            User(
                email="old@example.test",
                username="e2e_admin",
                hashed_password="bad-hash",
                is_admin=False,
                is_active=False,
            )
        )
        db.commit()
    finally:
        db.close()

    settings = get_settings()
    ensure_e2e_seed_user(settings)

    db = _get_session(engine)
    try:
        user = db.query(User).filter(User.username == "e2e_admin").first()
        assert user is not None
        assert user.is_admin is True
        assert user.is_active is True
        assert verify_password("NewStrongPass!456", user.hashed_password)
    finally:
        db.close()
        dispose_engine()


def test_e2e_seed_skips_outside_test_env(monkeypatch, tmp_path):
    engine = _setup_db(
        tmp_path,
        monkeypatch,
        ENVIRONMENT="development",
        E2E_SEED_USER="true",
        E2E_USERNAME="e2e_admin",
        E2E_PASSWORD="StrongPass!123",
    )

    settings = get_settings()
    ensure_e2e_seed_user(settings)

    db = _get_session(engine)
    try:
        user = db.query(User).filter(User.username == "e2e_admin").first()
        assert user is None
    finally:
        db.close()
        dispose_engine()

