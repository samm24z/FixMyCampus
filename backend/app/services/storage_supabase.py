"""Supabase Storage implementation of ``Storage`` (private bucket, service-role key, REST API).

The browser PUTs the raw photo bytes to a signed upload link; the backend only ever reads, rewrites
and deletes objects with the service key, which must never reach the browser. Object keys and link
tokens are not logged, only HTTP status codes.
"""

from typing import Any, Optional
from urllib.parse import quote

import httpx

from app.core.logging import logger
from app.services.storage import StorageError, StoredObject, UploadTarget

CHUNK_BYTES = 64 * 1024
# The storage server reports a missing bucket or object as 404, or as 400 with "statusCode": "404" in the body.
MISSING_STATUSES = {400, 404}


class SupabaseStorage:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        bucket: str,
        timeout: float = 15.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._origin = f"{base_url.rstrip('/')}/storage/v1"
        self._bucket = bucket
        self._timeout = timeout
        self._transport = transport
        # Legacy service_role keys are JWTs and need a bearer header; new sb_secret_ keys must not send one.
        self._headers = {"apikey": service_key}
        if service_key.startswith("eyJ"):
            self._headers["Authorization"] = f"Bearer {service_key}"

    # -- plumbing ---------------------------------------------------------------------------------

    def _object_path(self, key: str) -> str:
        return f"/object/{quote(self._bucket, safe='')}/{quote(key, safe='/')}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def _request(self, method: str, path: str, *, headers: Optional[dict[str, str]] = None, **kwargs: Any) -> httpx.Response:
        try:
            async with self._client() as client:
                return await client.request(method, f"{self._origin}{path}", headers={**self._headers, **(headers or {})}, **kwargs)
        except httpx.HTTPError as exc:
            logger.error(f"Supabase storage unreachable: {type(exc).__name__}")
            raise StorageError() from exc

    @staticmethod
    def _fail(response: httpx.Response) -> StorageError:
        logger.error(f"Supabase storage error {response.status_code}")
        return StorageError()

    # -- Storage protocol -------------------------------------------------------------------------

    async def create_upload_url(self, key: str, content_type: str) -> UploadTarget:
        # The signed link is single-use for this key; upsert is fixed into the token by this header.
        response = await self._request(
            "POST", f"/object/upload/sign/{quote(self._bucket, safe='')}/{quote(key, safe='/')}",
            headers={"x-upsert": "false"},
        )
        if response.status_code >= 300:
            raise self._fail(response)
        try:
            url = response.json()["url"]
        except (ValueError, KeyError, TypeError):
            logger.error("Supabase storage returned no upload link")
            raise StorageError() from None
        if not isinstance(url, str) or not url:
            raise StorageError()
        if not url.startswith("http"):
            url = f"{self._origin}{url}"
        return UploadTarget(url=url, method="PUT", headers={"Content-Type": content_type})

    async def create_view_urls(self, keys: list[str], expires_in: int = 300) -> dict[str, str]:
        if not keys:
            return {}
        response = await self._request(
            "POST", f"/object/sign/{quote(self._bucket, safe='')}", json={"expiresIn": expires_in, "paths": list(keys)},
        )
        if response.status_code >= 300:
            raise self._fail(response)
        try:
            entries = response.json()
            urls: dict[str, str] = {}
            for entry in entries:
                if entry.get("error") or not entry.get("signedURL") or not entry.get("path"):
                    continue
                signed = entry["signedURL"]
                urls[entry["path"]] = signed if signed.startswith("http") else f"{self._origin}{signed}"
        except (ValueError, AttributeError, TypeError):
            logger.error("Supabase storage returned an unreadable link list")
            raise StorageError() from None
        return urls

    async def head(self, key: str) -> Optional[StoredObject]:
        response = await self._request("HEAD", self._object_path(key))
        if response.status_code in MISSING_STATUSES:
            return None
        if response.status_code >= 300:
            raise self._fail(response)
        try:
            size = int(response.headers["content-length"])
        except (KeyError, ValueError):
            logger.error("Supabase storage returned no object size")
            raise StorageError() from None
        return StoredObject(size=size, content_type=response.headers.get("content-type"))

    async def read(self, key: str, max_bytes: int) -> bytes:
        try:
            async with self._client() as client:
                async with client.stream("GET", f"{self._origin}{self._object_path(key)}", headers=self._headers) as response:
                    if response.status_code >= 300:
                        if response.status_code in MISSING_STATUSES:
                            raise StorageError("File not found in storage")
                        raise self._fail(response)
                    declared = response.headers.get("content-length")
                    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                        raise StorageError("File is larger than allowed")
                    data = bytearray()
                    async for chunk in response.aiter_bytes(CHUNK_BYTES):
                        data.extend(chunk)
                        if len(data) > max_bytes:
                            raise StorageError("File is larger than allowed")
                    return bytes(data)
        except httpx.HTTPError as exc:
            logger.error(f"Supabase storage unreachable: {type(exc).__name__}")
            raise StorageError() from exc

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        response = await self._request(
            "POST", self._object_path(key), content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code >= 300:
            raise self._fail(response)

    async def delete(self, keys: list[str]) -> None:
        if not keys:
            return
        response = await self._request("DELETE", f"/object/{quote(self._bucket, safe='')}", json={"prefixes": list(keys)})
        if response.status_code >= 300:
            raise self._fail(response)

    # -- setup ------------------------------------------------------------------------------------

    async def ensure_bucket(self, file_size_limit: int, allowed_mime_types: list[str]) -> None:
        """Create the private bucket, or bring an existing one in line with the limits."""
        bucket_path = f"/bucket/{quote(self._bucket, safe='')}"
        existing = await self._request("GET", bucket_path)
        if existing.status_code in MISSING_STATUSES:
            response = await self._request("POST", "/bucket", json={
                "id": self._bucket, "name": self._bucket, "public": False,
                "file_size_limit": file_size_limit, "allowed_mime_types": allowed_mime_types,
            })
        elif existing.status_code < 300:
            response = await self._request("PUT", bucket_path, json={
                "public": False, "file_size_limit": file_size_limit, "allowed_mime_types": allowed_mime_types,
            })
        else:
            raise self._fail(existing)
        if response.status_code >= 300:
            raise self._fail(response)
