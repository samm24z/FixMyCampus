"""Campus layout endpoint: the places people can pick when reporting a problem."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.campus import PLACES, Place
from app.models.user import User
from app.schemas.campus import PlaceRead


router = APIRouter(prefix="/campus")


@router.get("/places", response_model=list[PlaceRead])
async def list_places(_: Annotated[User, Depends(get_current_user)]) -> tuple[Place, ...]:
    """Blocks and facilities of the campus (any signed-in user)."""
    return PLACES
