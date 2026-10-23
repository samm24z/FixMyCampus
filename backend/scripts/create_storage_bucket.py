"""Create (or update) the private Supabase Storage bucket that holds ticket photos.

Usage from the backend directory:
    python scripts/create_storage_bucket.py

Uses SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and STORAGE_BUCKET from the environment. The bucket is private
(photos are only viewed through short-lived signed links) with a size limit of UPLOAD_MAX_IMAGE_BYTES and
JPEG/PNG/WEBP only. Safe to rerun: an existing bucket just gets the limits refreshed.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.storage import StorageError
from app.services.storage_supabase import SupabaseStorage

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]


async def main() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")
    storage = SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, settings.STORAGE_BUCKET)
    try:
        await storage.ensure_bucket(settings.UPLOAD_MAX_IMAGE_BYTES, ALLOWED_TYPES)
    except StorageError:
        sys.exit("Could not create the bucket. Check SUPABASE_URL and the service-role key (see the log line above).")
    print(f"Bucket '{settings.STORAGE_BUCKET}' is ready: private, up to {settings.UPLOAD_MAX_IMAGE_BYTES} bytes, {', '.join(ALLOWED_TYPES)}")


if __name__ == "__main__":
    asyncio.run(main())
