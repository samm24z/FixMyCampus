"""SupabaseStorage: exact requests sent to the storage REST API and how responses are parsed (httpx mocked)."""

import json

import httpx
import pytest

from app.services.storage import StorageError, StoredObject, UploadTarget
from app.services.storage_supabase import SupabaseStorage

BASE = "https://proj.supabase.co/storage/v1"
KEY = "tickets/2026/10/3f2a/original.jpg"
LEGACY_KEY = "eyJhbGciOi.service.role"
NEW_KEY = "sb_secret_abc123"


def make_storage(handler, service_key: str = NEW_KEY) -> tuple[SupabaseStorage, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    storage = SupabaseStorage("https://proj.supabase.co/", service_key, "ticket-media", transport=httpx.MockTransport(wrapped))
    return storage, seen


def fixed(status: int, **kwargs) -> "callable":
    return lambda request: httpx.Response(status, **kwargs)


async def test_auth_headers_depend_on_key_style():
    storage, seen = make_storage(fixed(200, json={"url": "/x"}), LEGACY_KEY)
    await storage.create_upload_url(KEY, "image/jpeg")
    assert seen[0].headers["apikey"] == LEGACY_KEY
    assert seen[0].headers["authorization"] == f"Bearer {LEGACY_KEY}"

    storage, seen = make_storage(fixed(200, json={"url": "/x"}), NEW_KEY)
    await storage.create_upload_url(KEY, "image/jpeg")
    assert seen[0].headers["apikey"] == NEW_KEY
    assert "authorization" not in seen[0].headers


async def test_create_upload_url_signs_and_builds_browser_target():
    storage, seen = make_storage(fixed(200, json={"url": f"/object/upload/sign/ticket-media/{KEY}?token=abc.def"}))
    target = await storage.create_upload_url(KEY, "image/png")
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", f"/storage/v1/object/upload/sign/ticket-media/{KEY}")
    assert request.headers["x-upsert"] == "false"
    assert target == UploadTarget(
        url=f"{BASE}/object/upload/sign/ticket-media/{KEY}?token=abc.def",
        method="PUT", headers={"Content-Type": "image/png"},
    )


async def test_create_upload_url_encodes_odd_keys_but_keeps_slashes():
    storage, seen = make_storage(fixed(200, json={"url": "/u?token=t"}))
    await storage.create_upload_url("tickets/a b/c#d.jpg", "image/jpeg")
    assert seen[0].url.raw_path.decode().split("?")[0] == "/storage/v1/object/upload/sign/ticket-media/tickets/a%20b/c%23d.jpg"


@pytest.mark.parametrize("response", [
    httpx.Response(409, json={"error": "Duplicate"}),
    httpx.Response(500, text="boom"),
    httpx.Response(200, json={"nope": 1}),
    httpx.Response(200, text="not json"),
])
async def test_create_upload_url_failures_become_storage_error(response):
    storage, _ = make_storage(lambda request: response)
    with pytest.raises(StorageError):
        await storage.create_upload_url(KEY, "image/jpeg")


async def test_unreachable_server_becomes_storage_error():
    def boom(request):
        raise httpx.ConnectError("down")

    storage, _ = make_storage(boom)
    with pytest.raises(StorageError):
        await storage.create_upload_url(KEY, "image/jpeg")
    with pytest.raises(StorageError):
        await storage.read(KEY, 100)


async def test_create_view_urls_batches_one_call_and_skips_failures():
    keys = [KEY, "tickets/missing.jpg", "tickets/b.jpg"]
    reply = [
        {"path": KEY, "signedURL": f"/object/sign/ticket-media/{KEY}?token=t1", "error": None},
        {"path": "tickets/missing.jpg", "signedURL": None, "error": "Either the object does not exist or you do not have access to it"},
        {"path": "tickets/b.jpg", "signedURL": "/object/sign/ticket-media/tickets/b.jpg?token=t2", "error": None},
    ]
    storage, seen = make_storage(fixed(200, json=reply))
    urls = await storage.create_view_urls(keys, expires_in=120)
    assert len(seen) == 1
    assert (seen[0].method, seen[0].url.path) == ("POST", "/storage/v1/object/sign/ticket-media")
    assert json.loads(seen[0].content) == {"expiresIn": 120, "paths": keys}
    assert urls == {
        KEY: f"{BASE}/object/sign/ticket-media/{KEY}?token=t1",
        "tickets/b.jpg": f"{BASE}/object/sign/ticket-media/tickets/b.jpg?token=t2",
    }


async def test_create_view_urls_default_expiry_and_empty_list():
    storage, seen = make_storage(fixed(200, json=[]))
    assert await storage.create_view_urls([]) == {}
    assert seen == []
    await storage.create_view_urls([KEY])
    assert json.loads(seen[0].content)["expiresIn"] == 300


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(200, json={"not": "a list"}), httpx.Response(200, json=[1])])
async def test_create_view_urls_failures_become_storage_error(response):
    storage, _ = make_storage(lambda request: response)
    with pytest.raises(StorageError):
        await storage.create_view_urls([KEY])


async def test_head_returns_size_and_type():
    storage, seen = make_storage(fixed(200, headers={"content-length": "2048", "content-type": "image/jpeg"}))
    assert await storage.head(KEY) == StoredObject(size=2048, content_type="image/jpeg")
    assert (seen[0].method, seen[0].url.path) == ("HEAD", f"/storage/v1/object/ticket-media/{KEY}")


@pytest.mark.parametrize("status", [400, 404])
async def test_head_missing_is_none(status):
    storage, _ = make_storage(fixed(status))
    assert await storage.head(KEY) is None


async def test_head_server_error_and_missing_length_raise():
    storage, _ = make_storage(fixed(500))
    with pytest.raises(StorageError):
        await storage.head(KEY)
    storage, _ = make_storage(lambda request: httpx.Response(200, headers={"transfer-encoding": "chunked"}))
    with pytest.raises(StorageError):
        await storage.head(KEY)


async def test_read_returns_bytes():
    storage, seen = make_storage(fixed(200, content=b"photo-bytes"))
    assert await storage.read(KEY, 1000) == b"photo-bytes"
    assert (seen[0].method, seen[0].url.path) == ("GET", f"/storage/v1/object/ticket-media/{KEY}")
    assert seen[0].headers["apikey"] == NEW_KEY


async def test_read_exactly_at_the_limit_is_allowed():
    storage, _ = make_storage(fixed(200, content=b"x" * 100))
    assert len(await storage.read(KEY, 100)) == 100


async def test_read_stops_when_body_exceeds_limit_even_without_content_length():
    def handler(request):
        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                for _ in range(10):
                    yield b"x" * 100

        return httpx.Response(200, stream=Body())

    storage, _ = make_storage(handler)
    with pytest.raises(StorageError, match="larger"):
        await storage.read(KEY, 250)


async def test_read_rejects_large_declared_length():
    storage, _ = make_storage(fixed(200, content=b"x" * 500))
    with pytest.raises(StorageError, match="larger"):
        await storage.read(KEY, 100)


@pytest.mark.parametrize("status", [400, 404])
async def test_read_missing_raises_not_found(status):
    storage, _ = make_storage(fixed(status, json={"error": "not_found"}))
    with pytest.raises(StorageError, match="not found"):
        await storage.read(KEY, 100)


async def test_read_server_error_raises():
    storage, _ = make_storage(fixed(502))
    with pytest.raises(StorageError):
        await storage.read(KEY, 100)


async def test_put_sends_raw_body_with_upsert():
    storage, seen = make_storage(fixed(200, json={"Id": "1", "Key": f"ticket-media/{KEY}"}))
    await storage.put(KEY, b"jpeg-bytes", "image/jpeg")
    request = seen[0]
    assert (request.method, request.url.path) == ("POST", f"/storage/v1/object/ticket-media/{KEY}")
    assert request.headers["content-type"] == "image/jpeg"
    assert request.headers["x-upsert"] == "true"
    assert request.content == b"jpeg-bytes"


async def test_put_failure_raises():
    storage, _ = make_storage(fixed(413, json={"error": "Payload too large"}))
    with pytest.raises(StorageError):
        await storage.put(KEY, b"x", "image/jpeg")


async def test_delete_sends_prefixes_and_skips_empty():
    storage, seen = make_storage(fixed(200, json=[]))
    await storage.delete([])
    assert seen == []
    await storage.delete([KEY, "tickets/x/thumb.jpg"])
    request = seen[0]
    assert (request.method, request.url.path) == ("DELETE", "/storage/v1/object/ticket-media")
    assert json.loads(request.content) == {"prefixes": [KEY, "tickets/x/thumb.jpg"]}


async def test_delete_failure_raises():
    storage, _ = make_storage(fixed(500))
    with pytest.raises(StorageError):
        await storage.delete([KEY])


LIMITS = {"file_size_limit": 5242880, "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]}


async def test_ensure_bucket_creates_when_missing():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(404, json={"error": "Bucket not found"})
        return httpx.Response(200, json={"name": "ticket-media"})

    storage, seen = make_storage(handler)
    await storage.ensure_bucket(**LIMITS)
    assert [(r.method, r.url.path) for r in seen] == [("GET", "/storage/v1/bucket/ticket-media"), ("POST", "/storage/v1/bucket")]
    assert json.loads(seen[1].content) == {"id": "ticket-media", "name": "ticket-media", "public": False, **LIMITS}


async def test_ensure_bucket_treats_400_as_missing():
    storage, seen = make_storage(lambda r: httpx.Response(400, json={"statusCode": "404"}) if r.method == "GET" else httpx.Response(200, json={}))
    await storage.ensure_bucket(**LIMITS)
    assert seen[1].method == "POST"


async def test_ensure_bucket_updates_when_present():
    storage, seen = make_storage(lambda r: httpx.Response(200, json={"id": "ticket-media"} if r.method == "GET" else {"message": "Successfully updated"}))
    await storage.ensure_bucket(**LIMITS)
    assert [(r.method, r.url.path) for r in seen] == [("GET", "/storage/v1/bucket/ticket-media"), ("PUT", "/storage/v1/bucket/ticket-media")]
    assert json.loads(seen[1].content) == {"public": False, **LIMITS}


async def test_ensure_bucket_errors_raise():
    storage, _ = make_storage(fixed(401))
    with pytest.raises(StorageError):
        await storage.ensure_bucket(**LIMITS)
    storage, _ = make_storage(lambda r: httpx.Response(404) if r.method == "GET" else httpx.Response(403))
    with pytest.raises(StorageError):
        await storage.ensure_bucket(**LIMITS)
