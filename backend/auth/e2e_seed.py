"""Deterministic E2E test-user seed support (test environment only)."""

from __future__ import annotations

import hashlib
from sqlalchemy.orm import sessionmaker

from backend.auth.password import hash_password
from backend.config import Settings
from backend.core.logging import get_logger
from backend.db.database import get_engine
from backend.db.models import User

logger = get_logger(__name__)


def _seed_email_for_username(username: str) -> str:
    digest = hashlib.sha1(username.encode("utf-8")).hexdigest()[:10]
    return f"e2e-{digest}@local.test"


def ensure_e2e_seed_user(settings: Settings) -> None:
    """Create/update a deterministic E2E user for local/CI tests.

    Safety:
    - runs only when ENVIRONMENT=test
    - requires E2E_SEED_USER=true and non-empty E2E_USERNAME/E2E_PASSWORD
    """
    if not settings.is_test:
        return
    if not settings.e2e_seed_user:
        return

    username = (settings.e2e_username or "").strip()
    password = settings.e2e_password or ""
    if not username or not password:
        logger.warning(
            "E2E seed user enabled but credentials are missing; skipping",
            data={"username_set": bool(username), "password_set": bool(password)},
        )
        return

    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(
                email=_seed_email_for_username(username),
                username=username,
                hashed_password=hash_password(password),
                is_admin=True,
                is_active=True,
            )
            db.add(user)
            db.commit()
            logger.info("E2E seed user created", data={"username": username})
            return

        user.hashed_password = hash_password(password)
        user.is_active = True
        user.is_admin = True
        db.add(user)
        db.commit()
        logger.info("E2E seed user updated", data={"username": username})
    finally:
        db.close()

