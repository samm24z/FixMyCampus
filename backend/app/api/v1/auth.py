"""Authentication and Review-1 RBAC endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose.exceptions import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.enums import RoleEnum
from app.models.department import Department
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest, Token
from app.schemas.user import UserRead
from app.schemas.department import DepartmentRead


router = APIRouter(prefix="/auth")
PUBLIC_REGISTRATION_ROLES = {RoleEnum.STUDENT, RoleEnum.FACULTY}


def token_response(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a basic campus account without accepting elevated roles."""
    email = str(payload.email).lower()
    if payload.role not in PUBLIC_REGISTRATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student and faculty accounts can self-register",
        )
    existing_user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role.value,
        phone_number=payload.phone_number,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate a user and issue access and refresh JWTs."""
    email = str(payload.email).lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return token_response(user)


@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Exchange a valid refresh token for a new token pair."""
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = UUID(decoded["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return token_response(user)


@router.get("/me", response_model=UserRead)
async def current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the authenticated user's profile."""
    return current_user


@router.get("/admin-check", response_model=UserRead, include_in_schema=False)
async def admin_check(
    current_user: Annotated[User, Depends(require_role(RoleEnum.ADMIN))],
) -> User:
    """Small protected endpoint used to verify server-side RBAC."""
    return current_user


@router.get("/directory/staff", response_model=list[UserRead], include_in_schema=False)
async def staff_directory(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(RoleEnum.COORDINATOR, RoleEnum.ADMIN))],
) -> list[User]:
    """Return active staff accounts for coordinator/admin assignment controls."""
    result = await db.scalars(
        select(User).where(User.role == RoleEnum.STAFF.value, User.is_active.is_(True)).order_by(User.full_name)
    )
    return list(result.all())


@router.get("/directory/departments", response_model=list[DepartmentRead], include_in_schema=False)
async def department_directory(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(RoleEnum.COORDINATOR, RoleEnum.ADMIN))],
) -> list[Department]:
    """Return active department IDs for assignment controls."""
    result = await db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name))
    return list(result.all())