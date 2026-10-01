"""Verification of Supabase Auth access tokens.

Supabase issues and refreshes the tokens; this module only checks them. Modern projects sign
with asymmetric keys (ES256/RS256) published as a JWKS document, so no shared secret is needed.
HS256 is accepted only when ``SUPABASE_JWT_SECRET`` is configured (legacy projects, tests), and
the algorithm named in the token header can never select a different kind of key.
"""

import time
from typing import Any, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings
from app.core.logging import logger

JWKS_TTL_SECONDS = 600
JWKS_MIN_REFETCH_SECONDS = 60  # unknown key id => refetch once, but never hammer Supabase
ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}


class AuthError(Exception):
    """The presented token is missing, malformed, expired, or not issued by our Supabase project."""


class SupabaseTokenVerifier:
    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at = 0.0

    async def _fetch_jwks(self) -> list[dict[str, Any]]:
        url = f"{settings.supabase_issuer}/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json().get("keys", [])

    async def _refresh_keys(self) -> None:
        try:
            keys = await self._fetch_jwks()
        except Exception as exc:  # network error, Supabase paused, bad JSON ...
            logger.error(f"Could not fetch Supabase signing keys: {exc}")
            raise AuthError("Signing keys unavailable") from exc
        self._keys = {key["kid"]: key for key in keys if "kid" in key}
        self._fetched_at = time.monotonic()

    async def _signing_key(self, kid: Optional[str]) -> dict[str, Any]:
        age = time.monotonic() - self._fetched_at
        if not self._keys or age > JWKS_TTL_SECONDS:
            await self._refresh_keys()
        if kid not in self._keys and time.monotonic() - self._fetched_at > JWKS_MIN_REFETCH_SECONDS:
            await self._refresh_keys()  # the project may have rotated its keys
        if kid not in self._keys:
            raise AuthError("Unknown signing key")
        return self._keys[kid]

    async def verify(self, token: str) -> dict[str, Any]:
        """Return the verified claims of ``token`` or raise ``AuthError``."""
        if not settings.SUPABASE_URL:
            logger.error("SUPABASE_URL is not configured; every authenticated request will be rejected")
            raise AuthError("Authentication is not configured")
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm == "HS256" and settings.SUPABASE_JWT_SECRET:
                key: Any = settings.SUPABASE_JWT_SECRET
            elif algorithm in ASYMMETRIC_ALGORITHMS:
                key = await self._signing_key(header.get("kid"))
            else:
                raise AuthError("Unsupported token algorithm")
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                issuer=settings.supabase_issuer,
            )
        except JWTError as exc:
            raise AuthError(str(exc)) from exc
        if not claims.get("sub"):
            raise AuthError("Token has no subject")
        return claims


token_verifier = SupabaseTokenVerifier()
