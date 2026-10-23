"""User and Role Pydantic schemas."""

import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.enums import RoleEnum


class RoleBase(BaseModel):
    name: str = Field(..., max_length=50)
    code: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[dict] = Field(default_factory=dict)


class RoleCreate(RoleBase):
    pass


class RoleRead(RoleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    role: RoleEnum = Field(default=RoleEnum.STUDENT)
    department_id: Optional[uuid.UUID] = None
    phone_number: Optional[str] = Field(None, max_length=30)
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone_number: Optional[str] = Field(None, max_length=30)
    department_id: Optional[uuid.UUID] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: uuid.UUID
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreate(BaseModel):
    """Admin-created account (any role); the user should change the password after first login."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=8)
    role: RoleEnum
    department_id: Optional[uuid.UUID] = None
    phone_number: Optional[str] = Field(None, max_length=30)


class AdminUserUpdate(BaseModel):
    """Admin edits to role, department, and active flag."""
    role: Optional[RoleEnum] = None
    department_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


_PHONE_CHARS = re.compile(r"^\+?[0-9 ()-]+$")


class SelfProfileUpdate(BaseModel):
    """What a signed-in user may change on their own profile. Anything else is refused."""
    full_name: Optional[str] = Field(None, max_length=150)
    phone_number: Optional[str] = Field(None, max_length=30)

    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: Optional[str]) -> str:
        name = " ".join((value or "").split())
        if len(name) < 2:
            raise ValueError("Name must be at least 2 characters")
        return name

    @field_validator("phone_number")
    @classmethod
    def _clean_phone(cls, value: Optional[str]) -> Optional[str]:
        phone = " ".join((value or "").split())
        if not phone:
            return None  # clearing the number is allowed
        digits = sum(ch.isdigit() for ch in phone)
        if not _PHONE_CHARS.match(phone) or not 7 <= digits <= 15:
            raise ValueError("Enter a valid phone number, e.g. +91 98765 43210")
        return phone
