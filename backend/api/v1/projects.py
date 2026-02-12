"""v1 project workspace endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.core.exceptions import OmniAIException
from backend.db import get_db
from backend.db.models import Project, User

router = APIRouter()


class ProjectModel(BaseModel):
    id: str
    name: str
    instructions: str | None
    created_at: str
    updated_at: str


@router.get("/projects", response_model=List[ProjectModel])
async def list_projects(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectModel]:
    settings = get_settings()
    if not settings.feature_workspace:
        raise OmniAIException(
            "Workspace capability disabled",
            status_code=status.HTTP_403_FORBIDDEN,
            code="E_CAPABILITY_DISABLED",
        )

    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    return [
        ProjectModel(
            id=p.id,
            name=p.name,
            instructions=p.instructions,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in projects
    ]
