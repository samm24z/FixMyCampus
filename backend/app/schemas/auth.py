"""Authentication and Token schemas."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.enums import RoleEnum


class Token(BaseModel):
    """JWT Access and Refresh token payload."""
    access_token: str = Field(..., description="JWT Bearer token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Seconds until token expiration")


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token exchange payload."""
    refresh_token: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    """User login credentials."""
    email: EmailStr = Field(..., description="Institutional email address")
    password: str = Field(..., min_length=6, description="User password")


class RegisterRequest(BaseModel):
    """User registration payload."""
    email: EmailStr = Field(..., description="Institutional email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: str = Field(..., min_length=2, max_length=150, description="Full Name")
    role: RoleEnum = Field(default=RoleEnum.STUDENT, description="Initial role")
    phone_number: Optional[str] = Field(None, max_length=30, description="Contact phone number")
