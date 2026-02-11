"""v1 auth endpoint aliases.

These endpoints map the canonical `/v1/auth/*` surface to the existing auth logic.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DBSession

from backend.api.auth import (
    AuthResponse,
    LoginRequest,
    UserResponse,
    csrf_bootstrap as legacy_csrf_bootstrap,
    get_me as legacy_get_me,
    login as legacy_login,
    logout as legacy_logout,
)
from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.db.models import User

router = APIRouter(prefix="/auth", tags=["v1-auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: DBSession = Depends(get_db),
):
    return await legacy_login(payload=payload, response=response, http_request=request, db=db)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
):
    return await legacy_logout(request=request, response=response, db=db)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return await legacy_get_me(current_user=current_user)


@router.get("/csrf/bootstrap")
async def csrf_bootstrap(request: Request, response: Response):
    return await legacy_csrf_bootstrap(request=request, response=response)
