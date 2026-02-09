"""FastAPI dependencies for authentication."""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from backend.config import get_settings
from backend.core.exceptions import AuthenticationError
from backend.core.logging import get_logger
from backend.db import get_db
from backend.db.models import User
from backend.auth.session import validate_session
from backend.services.audit_service import audit_log_event

logger = get_logger(__name__)


async def get_current_user(
    request: Request,
    db: DBSession = Depends(get_db),
) -> User:
    """Get the current authenticated user.

    Raises:
        HTTPException: If not authenticated.
    """
    settings = get_settings()

    # Get session token from cookie
    session_token = request.cookies.get(settings.session_cookie_name)

    if not session_token:
        audit_log_event(
            db,
            event_type="auth_missing_token",
            user_id=None,
            request=request,
            data={"path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session
    session = validate_session(db, session_token)

    if not session:
        audit_log_event(
            db,
            event_type="auth_invalid_session",
            user_id=None,
            request=request,
            data={"path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user
    user = db.query(User).filter(User.id == session.user_id).first()

    if not user or not user.is_active:
        audit_log_event(
            db,
            event_type="auth_inactive_user",
            user_id=session.user_id,
            request=request,
            data={"path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_optional_user(
    request: Request,
    db: DBSession = Depends(get_db),
) -> Optional[User]:
    """Get the current user if authenticated, otherwise None."""
    settings = get_settings()

    session_token = request.cookies.get(settings.session_cookie_name)

    if not session_token:
        return None

    session = validate_session(db, session_token)

    if not session:
        return None

    user = db.query(User).filter(User.id == session.user_id).first()

    if not user or not user.is_active:
        return None

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        audit_log_event(
            getattr(current_user, "_db", None),
            event_type="admin_access_denied",
            user_id=current_user.id,
            request=None,
            data={"attempted": "admin_access"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
