"""Supabase token verification, first-login provisioning, and auth boundaries."""

import time
import uuid

import pytest
from httpx import AsyncClient
from jose import jwk, jwt
from sqlalchemy import select
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import token_verifier
from app.models import User
from tests.helpers import claims_for, mint_token


def me(client: AsyncClient, token: str):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


async def test_valid_token_returns_the_profile_with_role_and_department(async_client, login):
    response = await async_client.get("/api/v1/auth/me", headers=await login("staff"))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "staff@fixmycampus.dev" and body["role"] == "STAFF" and body["department_id"]
    assert "password" not in response.text


async def test_missing_or_garbage_tokens_are_rejected(async_client):
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401
    assert (await me(async_client, "not-a-jwt")).status_code == 401


@pytest.mark.parametrize("overrides", [
    {"exp": int(time.time()) - 10},                     # expired
    {"aud": "some-other-audience"},                      # wrong audience
    {"iss": "https://evil.supabase.co/auth/v1"},         # another project
])
async def test_tokens_that_fail_validation_are_rejected(async_client, overrides):
    from scripts.demo_users import demo_user_id
    token = mint_token(demo_user_id("admin"), "admin@fixmycampus.dev", **overrides)
    assert (await me(async_client, token)).status_code == 401


async def test_token_signed_with_the_wrong_secret_is_rejected(async_client):
    from scripts.demo_users import demo_user_id
    token = mint_token(demo_user_id("admin"), "admin@fixmycampus.dev", secret="x" * 48)
    assert (await me(async_client, token)).status_code == 401


async def test_unsigned_alg_none_token_is_rejected(async_client):
    import base64, json
    b64 = lambda raw: base64.urlsafe_b64encode(json.dumps(raw).encode()).rstrip(b"=").decode()  # noqa: E731
    from scripts.demo_users import demo_user_id
    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims_for(demo_user_id('admin'), 'admin@fixmycampus.dev'))}."
    assert (await me(async_client, forged)).status_code == 401


async def test_hs256_is_refused_when_no_shared_secret_is_configured(async_client, monkeypatch):
    from scripts.demo_users import demo_user_id
    token = mint_token(demo_user_id("admin"), "admin@fixmycampus.dev")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    assert (await me(async_client, token)).status_code == 401


async def test_authentication_fails_closed_when_supabase_is_not_configured(async_client, monkeypatch, login):
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    assert (await async_client.get("/api/v1/auth/me", headers=await login("admin"))).status_code == 401


async def test_role_comes_from_the_database_never_from_the_token(async_client):
    from scripts.demo_users import demo_user_id
    token = mint_token(
        demo_user_id("student"), "student@fixmycampus.dev",
        user_metadata={"role": "ADMIN"}, app_metadata={"role": "ADMIN"},
    )
    assert (await me(async_client, token)).json()["role"] == "STUDENT"
    admin_only = await async_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert admin_only.status_code == 403


async def test_deactivated_users_are_rejected_even_with_a_valid_token(async_client, login):
    headers = await login("student2")
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == "student2@fixmycampus.dev"))
        user.is_active = False
        await session.commit()
    try:
        assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    finally:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == "student2@fixmycampus.dev"))
            user.is_active = True
            await session.commit()


async def test_the_old_password_endpoints_are_gone(async_client):
    for path in ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"):
        assert (await async_client.post(path, json={})).status_code in {404, 405}


# ------------------------------------------------------- first-login provisioning

async def test_first_login_creates_a_student_profile(async_client, auth_headers):
    new_id = uuid.uuid4()
    headers = auth_headers(new_id, "Fresh.Student@campus.edu", user_metadata={"full_name": "Fresh Student"})
    response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(new_id) and body["role"] == "STUDENT"
    assert body["email"] == "fresh.student@campus.edu" and body["full_name"] == "Fresh Student"
    assert (await async_client.get("/api/v1/auth/me", headers=headers)).json()["id"] == str(new_id)  # no duplicate


async def test_self_signup_may_pick_faculty_but_never_anything_higher(async_client, auth_headers):
    faculty = await async_client.get("/api/v1/auth/me", headers=auth_headers(
        uuid.uuid4(), "prof@campus.edu", user_metadata={"role": "FACULTY"}))
    assert faculty.json()["role"] == "FACULTY"
    for sneaky in ("ADMIN", "COORDINATOR", "STAFF"):
        response = await async_client.get("/api/v1/auth/me", headers=auth_headers(
            uuid.uuid4(), f"{sneaky.lower()}@campus.edu", user_metadata={"role": sneaky}))
        assert response.json()["role"] == "STUDENT"


async def test_tokens_without_a_usable_identity_get_no_profile(async_client, auth_headers):
    no_email = auth_headers(uuid.uuid4(), None)
    anonymous = auth_headers(uuid.uuid4(), "anon@campus.edu", is_anonymous=True)
    assert (await async_client.get("/api/v1/auth/me", headers=no_email)).status_code == 401
    assert (await async_client.get("/api/v1/auth/me", headers=anonymous)).status_code == 401


async def test_an_email_already_owned_by_another_profile_is_refused(async_client, auth_headers):
    imposter = auth_headers(uuid.uuid4(), "admin@fixmycampus.dev")  # new id, existing admin email
    assert (await async_client.get("/api/v1/auth/me", headers=imposter)).status_code == 401


# ---------------------------------------------- asymmetric (ES256 / JWKS) tokens

@pytest.fixture
def es256_keypair(monkeypatch):
    """A fresh P-256 key whose public half is served through the verifier's JWKS fetch."""
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_jwk = jwk.construct(private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(), "ES256").to_dict()
    public_jwk.update({"kid": "key-1", "use": "sig", "alg": "ES256"})
    served = {"keys": [public_jwk], "calls": 0}

    async def fake_fetch():
        served["calls"] += 1
        return served["keys"]

    monkeypatch.setattr(token_verifier, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(token_verifier, "_keys", {})
    monkeypatch.setattr(token_verifier, "_fetched_at", 0.0)
    return pem, served


def es256_token(pem: str, kid: str, user_id, email: str) -> str:
    return jwt.encode(claims_for(user_id, email), pem, algorithm="ES256", headers={"kid": kid})


async def test_es256_tokens_verify_against_the_published_keys(async_client, es256_keypair):
    from scripts.demo_users import demo_user_id
    pem, served = es256_keypair
    token = es256_token(pem, "key-1", demo_user_id("coordinator"), "coordinator@fixmycampus.dev")
    response = await me(async_client, token)
    assert response.status_code == 200 and response.json()["role"] == "COORDINATOR"
    assert (await me(async_client, token)).status_code == 200
    assert served["calls"] == 1  # keys are cached, not refetched per request


async def test_es256_token_signed_by_an_unknown_key_is_rejected(async_client, es256_keypair, monkeypatch):
    from scripts.demo_users import demo_user_id
    _, served = es256_keypair
    attacker = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    # Same key id as the real key, but signed with a different private key.
    token = es256_token(attacker, "key-1", demo_user_id("admin"), "admin@fixmycampus.dev")
    assert (await me(async_client, token)).status_code == 401
    # An id the project never published is rejected without hammering Supabase.
    unknown = es256_token(attacker, "no-such-key", demo_user_id("admin"), "admin@fixmycampus.dev")
    assert (await me(async_client, unknown)).status_code == 401
    assert served["calls"] <= 2


async def test_unreachable_signing_keys_fail_closed(async_client, monkeypatch):
    from scripts.demo_users import demo_user_id

    async def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(token_verifier, "_fetch_jwks", boom)
    monkeypatch.setattr(token_verifier, "_keys", {})
    monkeypatch.setattr(token_verifier, "_fetched_at", 0.0)
    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    token = es256_token(pem, "key-1", demo_user_id("admin"), "admin@fixmycampus.dev")
    assert (await me(async_client, token)).status_code == 401
