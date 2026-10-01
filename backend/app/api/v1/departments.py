"""Department lookup endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentRead


router = APIRouter(prefix="/departments")


@router.get("", response_model=list[DepartmentRead])
async def list_departments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[Department]:
    """Active departments, for pickers in forms (any signed-in user)."""
    result = await db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name))
    return list(result.all())
