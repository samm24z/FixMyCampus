"""User administration, departments, and RBAC boundary tests."""

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import AuditLog, User
from tests.test_tickets import department_id


def new_user(**overrides) -> dict:
    return {
        "email": f"new-{uuid4().hex[:8]}@fixmycampus.dev",
        "full_name": "New Person",
        "password": "Sup3rSecret!pw",
        "role": "STAFF",
        **overrides,
    }


async def test_only_admins_can_list_users(async_client: AsyncClient, login):
    assert (await async_client.get("/api/v1/users", headers=await login("admin"))).status_code == 200
    for prefix in ("student", "faculty", "staff", "coordinator"):
        assert (await async_client.get("/api/v1/users", headers=await login(prefix))).status_code == 403
    assert (await async_client.get("/api/v1/users")).status_code == 401


async def test_admin_can_filter_users(async_client: AsyncClient, login):
    admin = await login("admin")
    staff = (await async_client.get("/api/v1/users?role=STAFF", headers=admin)).json()
    assert staff["total"] == 2 and {u["role"] for u in staff["items"]} == {"STAFF"}
    found = (await async_client.get("/api/v1/users?q=Electrical", headers=admin)).json()
    assert [u["email"] for u in found["items"]] == ["staff2@fixmycampus.dev"]


async def test_staff_accounts_require_a_department(async_client: AsyncClient, login, fake_supabase_admin):
    admin = await login("admin")
    assert (await async_client.post("/api/v1/users", json=new_user(), headers=admin)).status_code == 422
    assert fake_supabase_admin.accounts == {}  # rejected before any Supabase account was created
    dept = await department_id("IT")
    response = await async_client.post("/api/v1/users", json=new_user(department_id=dept), headers=admin)
    assert response.status_code == 201 and response.json()["department_id"] == dept
    assert "password" not in response.text


async def test_admin_created_user_gets_a_supabase_account_and_a_matching_profile(
    async_client: AsyncClient, login, fake_supabase_admin, auth_headers
):
    admin = await login("admin")
    payload = new_user(role="COORDINATOR")
    created = await async_client.post("/api/v1/users", json=payload, headers=admin)
    assert created.status_code == 201
    # The profile id is the Supabase account id, so the person's own token resolves to it.
    assert created.json()["id"] == str(fake_supabase_admin.accounts[payload["email"]])
    assert (await async_client.post("/api/v1/users", json=payload, headers=admin)).status_code == 409

    their_headers = auth_headers(UUID(created.json()["id"]), payload["email"])
    me = await async_client.get("/api/v1/auth/me", headers=their_headers)
    assert me.json()["role"] == "COORDINATOR"
    async with AsyncSessionLocal() as session:
        rows = (await session.scalars(select(AuditLog).where(AuditLog.entity_id == UUID(created.json()["id"])))).all()
    assert [row.action for row in rows] == ["CREATE"]


async def test_duplicate_email_is_rejected_before_anything_is_created_at_supabase(
    async_client: AsyncClient, login, fake_supabase_admin
):
    async with AsyncSessionLocal() as session:
        session.add(User(id=uuid4(), email="clash@fixmycampus.dev", full_name="Existing", role="STUDENT"))
        await session.commit()
    response = await async_client.post(
        "/api/v1/users", json=new_user(role="STUDENT", email="Clash@fixmycampus.dev"), headers=await login("admin")
    )
    assert response.status_code == 409
    assert fake_supabase_admin.accounts == {}


async def test_failed_profile_insert_removes_the_orphan_supabase_account(
    async_client: AsyncClient, login, fake_supabase_admin, monkeypatch
):
    import pytest
    from app.api.v1 import users as users_module

    def explode(*args, **kwargs):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(users_module, "record_audit", explode)  # fails after the Supabase account exists
    payload = new_user(role="STUDENT")
    with pytest.raises(RuntimeError):
        await async_client.post("/api/v1/users", json=payload, headers=await login("admin"))
    created_id = fake_supabase_admin.accounts[payload["email"]]
    assert fake_supabase_admin.deleted == [created_id]  # no login left behind without a profile
    async with AsyncSessionLocal() as session:
        assert await session.scalar(select(User).where(User.id == created_id)) is None


async def test_non_admins_cannot_create_or_modify_users(async_client: AsyncClient, login, fake_supabase_admin):
    student_id = (await async_client.get("/api/v1/auth/me", headers=await login("student"))).json()["id"]
    for prefix in ("student", "staff", "coordinator"):
        headers = await login(prefix)
        assert (await async_client.post("/api/v1/users", json=new_user(role="ADMIN"), headers=headers)).status_code == 403
        assert (await async_client.patch(f"/api/v1/users/{student_id}", json={"role": "ADMIN"}, headers=headers)).status_code == 403
    assert fake_supabase_admin.accounts == {}


async def test_role_change_takes_effect_immediately_and_is_audited(
    async_client: AsyncClient, login, fake_supabase_admin, auth_headers
):
    admin = await login("admin")
    payload = new_user(role="STUDENT")
    created = (await async_client.post("/api/v1/users", json=payload, headers=admin)).json()
    headers = auth_headers(UUID(created["id"]), payload["email"])
    assert (await async_client.get("/api/v1/users", headers=headers)).status_code == 403

    promoted = await async_client.patch(f"/api/v1/users/{created['id']}", json={"role": "ADMIN"}, headers=admin)
    assert promoted.status_code == 200 and promoted.json()["role"] == "ADMIN"
    # The role is read from the database per request, so the same token is upgraded at once.
    assert (await async_client.get("/api/v1/users", headers=headers)).status_code == 200
    async with AsyncSessionLocal() as session:
        update = (await session.scalars(select(AuditLog).where(
            AuditLog.entity_id == UUID(created["id"]), AuditLog.action == "UPDATE"))).one()
    assert update.old_values["role"] == "STUDENT" and update.new_values["role"] == "ADMIN"


async def test_deactivation_blocks_the_user_everywhere_and_reactivation_restores_it(
    async_client: AsyncClient, login, fake_supabase_admin, auth_headers
):
    admin = await login("admin")
    payload = new_user(role="STUDENT")
    created = (await async_client.post("/api/v1/users", json=payload, headers=admin)).json()
    user_id = UUID(created["id"])
    headers = auth_headers(user_id, payload["email"])
    assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 200

    off = await async_client.patch(f"/api/v1/users/{created['id']}", json={"is_active": False}, headers=admin)
    assert off.status_code == 200
    assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 401  # existing token, instantly
    assert fake_supabase_admin.bans == [(user_id, True)]  # and blocked from signing in again at Supabase

    on = await async_client.patch(f"/api/v1/users/{created['id']}", json={"is_active": True}, headers=admin)
    assert on.status_code == 200 and fake_supabase_admin.bans[-1] == (user_id, False)
    assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 200


async def test_failed_ban_leaves_the_user_unchanged(async_client: AsyncClient, login, fake_supabase_admin):
    admin = await login("admin")
    created = (await async_client.post("/api/v1/users", json=new_user(role="STUDENT"), headers=admin)).json()
    fake_supabase_admin.fail_ban = True
    response = await async_client.patch(f"/api/v1/users/{created['id']}", json={"is_active": False}, headers=admin)
    assert response.status_code == 502
    listing = (await async_client.get("/api/v1/users?q=New Person", headers=admin)).json()["items"]
    assert listing[0]["is_active"] is True  # not half-applied


async def test_role_only_edits_do_not_touch_supabase(async_client: AsyncClient, login, fake_supabase_admin):
    admin = await login("admin")
    created = (await async_client.post("/api/v1/users", json=new_user(role="STUDENT"), headers=admin)).json()
    await async_client.patch(f"/api/v1/users/{created['id']}", json={"role": "FACULTY"}, headers=admin)
    assert fake_supabase_admin.bans == []


async def test_admin_cannot_demote_or_deactivate_themselves(async_client: AsyncClient, login):
    admin = await login("admin")
    my_id = (await async_client.get("/api/v1/auth/me", headers=admin)).json()["id"]
    assert (await async_client.patch(f"/api/v1/users/{my_id}", json={"role": "STUDENT"}, headers=admin)).status_code == 403
    assert (await async_client.patch(f"/api/v1/users/{my_id}", json={"is_active": False}, headers=admin)).status_code == 403


async def test_moving_a_user_to_staff_needs_a_department(async_client: AsyncClient, login, fake_supabase_admin):
    admin = await login("admin")
    created = (await async_client.post("/api/v1/users", json=new_user(role="STUDENT"), headers=admin)).json()
    assert (await async_client.patch(f"/api/v1/users/{created['id']}", json={"role": "STAFF"}, headers=admin)).status_code == 422
    ok = await async_client.patch(
        f"/api/v1/users/{created['id']}", json={"role": "STAFF", "department_id": await department_id("CIVIL")}, headers=admin
    )
    assert ok.status_code == 200


async def test_staff_directory_is_coordinator_or_admin_only(async_client: AsyncClient, login):
    for prefix in ("coordinator", "admin"):
        response = await async_client.get("/api/v1/users/staff", headers=await login(prefix))
        assert response.status_code == 200 and {u["role"] for u in response.json()} == {"STAFF"}
    for prefix in ("student", "staff"):
        assert (await async_client.get("/api/v1/users/staff", headers=await login(prefix))).status_code == 403


async def test_department_list_needs_login(async_client: AsyncClient, login):
    assert (await async_client.get("/api/v1/departments")).status_code == 401
    response = await async_client.get("/api/v1/departments", headers=await login("student"))
    assert response.status_code == 200 and len(response.json()) == 7


async def test_account_administration_reports_misconfiguration_clearly(async_client: AsyncClient, login, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    response = await async_client.post("/api/v1/users", json=new_user(role="STUDENT"), headers=await login("admin"))
    assert response.status_code == 503
