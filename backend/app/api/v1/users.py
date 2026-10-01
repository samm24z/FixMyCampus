"""User administration and staff directory endpoints."""

import math
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException, UnprocessableException
from app.models.department import Department
from app.models.enums import AuditActionEnum, RoleEnum
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import AdminUserCreate, AdminUserUpdate, UserRead
from app.services.audit_service import record_audit
from app.services.supabase_admin import SupabaseAdmin, get_supabase_admin


router = APIRouter(prefix="/users")

DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_role(RoleEnum.ADMIN))]
TriageUser = Annotated[User, Depends(require_role(RoleEnum.COORDINATOR, RoleEnum.ADMIN))]
AuthAdmin = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]


async def _check_department(db: AsyncSession, role: str, department_id: Optional[uuid.UUID]) -> None:
    if department_id is not None:
        found = await db.scalar(select(Department.id).where(Department.id == department_id, Department.is_active.is_(True)))
        if found is None:
            raise UnprocessableException("Department not found or inactive")
    if role == RoleEnum.STAFF.value and department_id is None:
        raise UnprocessableException("Staff accounts must belong to a department")


@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(
    db: DbSession,
    _: AdminUser,
    q: Optional[str] = Query(default=None, max_length=100),
    role: Optional[RoleEnum] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[UserRead]:
    query = select(User)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
    if role:
        query = query.where(User.role == role.value)
    if department_id:
        query = query.where(User.department_id == department_id)
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(query.order_by(User.full_name, User.id).offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse[UserRead](
        items=[UserRead.model_validate(user) for user in rows.all()],
        total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/staff", response_model=list[UserRead])
async def list_staff(
    db: DbSession,
    _: TriageUser,
    department_id: Optional[uuid.UUID] = Query(default=None),
) -> list[User]:
    """Active staff accounts for the assignment picker."""
    query = select(User).where(User.role == RoleEnum.STAFF.value, User.is_active.is_(True))
    if department_id:
        query = query.where(User.department_id == department_id)
    return list((await db.scalars(query.order_by(User.full_name))).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: AdminUserCreate, db: DbSession, admin: AdminUser, auth_admin: AuthAdmin) -> User:
    """Create a confirmed Supabase account plus its application profile (any role)."""
    email = str(payload.email).lower()
    if await db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise ConflictException("Email is already registered")
    await _check_department(db, payload.role.value, payload.department_id)
    auth_id = await auth_admin.create_user(
        email=email, password=payload.password, full_name=payload.full_name, role=payload.role.value
    )
    try:
        user = User(
            id=auth_id,
            email=email,
            full_name=payload.full_name,
            role=payload.role.value,
            department_id=payload.department_id,
            phone_number=payload.phone_number,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        record_audit(
            db, user=admin, action=AuditActionEnum.CREATE, entity_type="user", entity_id=user.id,
            new_values={"email": email, "role": user.role, "department_id": str(user.department_id) if user.department_id else None},
        )
        await db.commit()
    except Exception:
        await db.rollback()
        await auth_admin.delete_user(auth_id)  # do not leave an orphan login that has no profile
        raise
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: AdminUserUpdate, db: DbSession, admin: AdminUser, auth_admin: AuthAdmin
) -> User:
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise NotFoundException("User", user_id)
    given = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        ("role" in given and given["role"] and given["role"].value != user.role) or given.get("is_active") is False
    ):
        raise ForbiddenException("Admins cannot demote or deactivate their own account")

    new_role = given["role"].value if given.get("role") else user.role
    new_department = given["department_id"] if "department_id" in given else user.department_id
    await _check_department(db, new_role, new_department)

    old = {"role": user.role, "department_id": str(user.department_id) if user.department_id else None, "is_active": user.is_active}
    user.role = new_role
    user.department_id = new_department
    active_changed = given.get("is_active") is not None and given["is_active"] != user.is_active
    if given.get("is_active") is not None:
        user.is_active = given["is_active"]
    new = {"role": user.role, "department_id": str(user.department_id) if user.department_id else None, "is_active": user.is_active}
    if new != old:
        record_audit(
            db, user=admin, action=AuditActionEnum.UPDATE, entity_type="user", entity_id=user.id,
            old_values=old, new_values=new,
        )
    await db.flush()
    if active_changed:
        # Also block new sign-ins/refreshes at Supabase. If this fails nothing is committed.
        await auth_admin.set_banned(user.id, banned=not user.is_active)
    await db.commit()
    await db.refresh(user)
    return user
