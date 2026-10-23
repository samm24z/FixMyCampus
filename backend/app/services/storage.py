"""Object storage for ticket photos and videos, independent of the host.

Files never pass through the backend on the way in: the browser uploads straight to storage
with a short-lived signed link from ``create_upload_url``. The backend checks the result,
writes sanitised copies and thumbnails with ``put``, and hands out short-lived view links.

Implementations: ``SupabaseStorage`` (default, ``storage_supabase.py``) and ``InMemoryStorage``
(tests). Azure Blob or S3/R2 can be added later behind the same interface.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.core.config import settings
from app.core.exceptions import AppException


@dataclass(frozen=True)
class UploadTarget:
    """Where and how the browser sends the file: ``method url`` with ``headers`` and the raw bytes as body."""

    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredObject:
    size: int
    content_type: Optional[str] = None


class StorageError(AppException):
    def __init__(self, message: str = "File storage is unavailable right now. Please try again shortly."):
        super().__init__(message, status_code=503, error_code="STORAGE_UNAVAILABLE")


class Storage(Protocol):
    async def create_upload_url(self, key: str, content_type: str) -> UploadTarget: ...

    async def create_view_urls(self, keys: list[str], expires_in: int = 300) -> dict[str, str]:
        """Signed, time-limited links to view each key. Keys that don't exist are left out."""
        ...

    async def head(self, key: str) -> Optional[StoredObject]:
        """Size and type of a stored object, or None if it doesn't exist."""
        ...

    async def read(self, key: str, max_bytes: int) -> bytes:
        """The object's bytes; raises StorageError if missing or larger than ``max_bytes``."""
        ...

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Write (or overwrite) an object from the backend, e.g. a sanitised copy or a thumbnail."""
        ...

    async def delete(self, keys: list[str]) -> None:
        """Remove objects; missing keys are ignored."""
        ...


class InMemoryStorage:
    """Test double. Tests simulate the browser upload by writing to ``objects`` directly."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def create_upload_url(self, key: str, content_type: str) -> UploadTarget:
        return UploadTarget(url=f"memory://upload/{key}", headers={"Content-Type": content_type})

    async def create_view_urls(self, keys: list[str], expires_in: int = 300) -> dict[str, str]:
        return {key: f"memory://view/{key}?expires_in={expires_in}" for key in keys if key in self.objects}

    async def head(self, key: str) -> Optional[StoredObject]:
        if key not in self.objects:
            return None
        data, content_type = self.objects[key]
        return StoredObject(size=len(data), content_type=content_type)

    async def read(self, key: str, max_bytes: int) -> bytes:
        if key not in self.objects:
            raise StorageError("File not found in storage")
        data = self.objects[key][0]
        if len(data) > max_bytes:
            raise StorageError("File is larger than allowed")
        return data

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def delete(self, keys: list[str]) -> None:
        for key in keys:
            self.objects.pop(key, None)


_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.STORAGE_BACKEND == "memory":
            _storage = InMemoryStorage()
        elif settings.STORAGE_BACKEND == "supabase":
            from app.services.storage_supabase import SupabaseStorage

            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                raise AppException("File storage is not configured", 503, "STORAGE_NOT_CONFIGURED")
            _storage = SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, settings.STORAGE_BUCKET)
        else:
            raise AppException(f"Unknown STORAGE_BACKEND {settings.STORAGE_BACKEND!r}", 503, "STORAGE_NOT_CONFIGURED")
    return _storage


def set_storage(storage: Optional[Storage]) -> None:
    """Swap the storage (tests); None resets to the configured backend on next use."""
    global _storage
    _storage = storage
