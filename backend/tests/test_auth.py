"""Authentication and RBAC integration tests."""

from uuid import uuid4

import pytest
from httpx import AsyncClient


DEMO_PASSWORD = "FixMyCampus-Dev-2026!"


@pytest.mark.asyncio
async def test_valid_registration_returns_safe_user(async_client: AsyncClient) -> None:
    email = f"student-{uuid4().hex}@fixmycampus.dev"
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!", "full_name": "New Student"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "STUDENT"
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_duplicate_email_is_rejected(async_client: AsyncClient) -> None:
    email = f"duplicate-{uuid4().hex}@fixmycampus.dev"
    payload = {"email": email, "password": "SecurePass123!", "full_name": "Duplicate Test"}

    first_response = await async_client.post("/api/v1/auth/register", json=payload)
    duplicate_response = await async_client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_access_and_refresh_tokens(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fixmycampus.dev", "password": DEMO_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_invalid_password_is_rejected(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fixmycampus.dev", "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_a_token(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_current_user_and_refresh_token(async_client: AsyncClient) -> None:
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "student@fixmycampus.dev", "password": DEMO_PASSWORD},
    )
    tokens = login_response.json()

    me_response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    refresh_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "student@fixmycampus.dev"
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


@pytest.mark.asyncio
async def test_wrong_role_is_forbidden(async_client: AsyncClient) -> None:
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "student@fixmycampus.dev", "password": DEMO_PASSWORD},
    )

    response = await async_client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_correct_role_is_allowed(async_client: AsyncClient) -> None:
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@fixmycampus.dev", "password": DEMO_PASSWORD},
    )

    response = await async_client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"