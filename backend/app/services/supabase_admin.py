"""Server-side client for the Supabase Auth admin API (create, find, ban, delete accounts).

Uses the service-role/secret key, which must never reach the browser. Routes depend on
``get_supabase_admin`` so tests can substitute a fake.
"""

import uuid
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import AppException, ConflictException, UnprocessableException
from app.core.logging import logger

BAN_FOREVER = "876000h"  # ~100 years; GoTrue has no "ban indefinitely" value


class SupabaseAdmin:
    def __init__(self, base_url: str, service_key: str) -> None:
        self._base = f"{base_url.rstrip('/')}/auth/v1/admin"
        # Legacy service_role keys are JWTs and need a bearer header; new sb_secret_ keys must not send one.
        self._headers = {"apikey": service_key, "Content-Type": "application/json"}
        if service_key.startswith("eyJ"):
            self._headers["Authorization"] = f"Bearer {service_key}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                return await client.request(method, f"{self._base}{path}", headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            logger.error(f"Supabase admin API unreachable: {exc}")
            raise AppException("Authentication service is unreachable", 502, "AUTH_PROVIDER_UNAVAILABLE") from exc

    @staticmethod
    def _fail(response: httpx.Response) -> AppException:
        try:
            body = response.json()
        except ValueError:
            body = {}
        code = body.get("error_code") or body.get("code")
        message = body.get("msg") or body.get("message") or "Authentication service error"
        if code in {"email_exists", "user_already_exists"}:
            return ConflictException("Email is already registered")
        if code in {"weak_password", "validation_failed"} or response.status_code == 422:
            return UnprocessableException(message)
        logger.error(f"Supabase admin API error {response.status_code}: {message}")
        return AppException("Authentication service error", 502, "AUTH_PROVIDER_ERROR")

    async def create_user(self, *, email: str, password: str, full_name: str, role: str) -> uuid.UUID:
        """Create a confirmed account (no confirmation email) and return its id."""
        response = await self._request("POST", "/users", json={
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"full_name": full_name, "role": role},
        })
        if response.status_code >= 400:
            raise self._fail(response)
        return uuid.UUID(response.json()["id"])

    async def find_user_id(self, email: str) -> Optional[uuid.UUID]:
        page = 1
        while True:
            response = await self._request("GET", "/users", params={"page": page, "per_page": 200})
            if response.status_code >= 400:
                raise self._fail(response)
            users = response.json().get("users", [])
            for user in users:
                if (user.get("email") or "").lower() == email.lower():
                    return uuid.UUID(user["id"])
            if len(users) < 200:
                return None
            page += 1

    async def set_banned(self, user_id: uuid.UUID, banned: bool) -> None:
        """Block (or unblock) future sign-ins and token refreshes for the account."""
        response = await self._request("PUT", f"/users/{user_id}", json={"ban_duration": BAN_FOREVER if banned else "none"})
        if response.status_code == 404:
            return  # profile without an auth account: nothing to ban
        if response.status_code >= 400:
            raise self._fail(response)

    async def delete_user(self, user_id: uuid.UUID) -> None:
        response = await self._request("DELETE", f"/users/{user_id}")
        if response.status_code >= 400 and response.status_code != 404:
            raise self._fail(response)


def get_supabase_admin() -> SupabaseAdmin:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise AppException(
            "Account administration is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)",
            503, "AUTH_PROVIDER_NOT_CONFIGURED",
        )
    return SupabaseAdmin(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
