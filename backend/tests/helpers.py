"""Test helpers: minting Supabase-style tokens and a fake Supabase admin client."""

import time
import uuid
from typing import Any, Optional

from jose import jwt

from app.core.config import settings
from app.core.exceptions import ConflictException
from tests.conftest_constants import TEST_JWT_SECRET


def claims_for(user_id, email: Optional[str] = "user@example.com", **overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "aud": settings.SUPABASE_JWT_AUDIENCE,
        "iss": settings.supabase_issuer,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "role": "authenticated",
    }
    if email is not None:
        claims["email"] = email
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def mint_token(user_id, email: Optional[str] = "user@example.com", *, secret: str = TEST_JWT_SECRET, **overrides: Any) -> str:
    """HS256 token shaped like the ones Supabase Auth issues."""
    return jwt.encode(claims_for(user_id, email, **overrides), secret, algorithm="HS256")


class FakeSupabaseAdmin:
    """Records calls instead of talking to Supabase."""

    def __init__(self) -> None:
        self.accounts: dict[str, uuid.UUID] = {}
        self.bans: list[tuple[uuid.UUID, bool]] = []
        self.deleted: list[uuid.UUID] = []
        self.fail_ban = False

    async def create_user(self, *, email: str, password: str, full_name: str, role: str) -> uuid.UUID:
        if email in self.accounts:
            raise ConflictException("Email is already registered")
        self.accounts[email] = uuid.uuid4()
        return self.accounts[email]

    async def find_user_id(self, email: str) -> Optional[uuid.UUID]:
        return self.accounts.get(email.lower())

    async def set_banned(self, user_id: uuid.UUID, banned: bool) -> None:
        if self.fail_ban:
            from app.core.exceptions import AppException
            raise AppException("Authentication service error", 502, "AUTH_PROVIDER_ERROR")
        self.bans.append((user_id, banned))

    async def delete_user(self, user_id: uuid.UUID) -> None:
        self.deleted.append(user_id)
