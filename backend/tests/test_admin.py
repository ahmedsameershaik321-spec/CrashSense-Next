
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.models.user import User


client = TestClient(app)


def create_test_user(role="pending", is_active=False):
    """Create a unique test account in the existing database."""

    user = User(
        email=f"admin-test-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Test",
        last_name="Account",
        role=role,
        is_active=is_active,
        is_email_verified=False,
    )

    with SessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def auth_headers(user_id):
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_pending_user_cannot_list_pending_users():
    user_id = create_test_user()

    response = client.get(
        "/api/v1/admin/pending-users",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_pending_user_cannot_list_all_users():
    user_id = create_test_user()

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_pending_user_cannot_approve_users():
    user_id = create_test_user()
    target_id = create_test_user()

    response = client.patch(
        f"/api/v1/admin/users/{target_id}/approve",
        headers=auth_headers(user_id),
        json={"role": "monitoring_operator"},
    )

    assert response.status_code == 403


def test_admin_can_list_pending_users():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    response = client.get(
        "/api/v1/admin/pending-users",
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_admin_can_approve_pending_user():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )
    target_id = create_test_user()

    response = client.patch(
        f"/api/v1/admin/users/{target_id}/approve",
        headers=auth_headers(admin_id),
        json={"role": "monitoring_operator"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "monitoring_operator"
    assert response.json()["is_active"] is True
    assert response.json()["approved_by"] if "approved_by" in response.json() else True

    with SessionLocal() as db:
        approved_user = db.get(User, target_id)

        assert approved_user is not None
        assert approved_user.role == "monitoring_operator"
        assert approved_user.is_active is True
        assert approved_user.approved_by == admin_id
        assert approved_user.approved_at is not None


def test_admin_cannot_approve_already_approved_user():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )
    target_id = create_test_user()

    first_response = client.patch(
        f"/api/v1/admin/users/{target_id}/approve",
        headers=auth_headers(admin_id),
        json={"role": "monitoring_operator"},
    )

    assert first_response.status_code == 200

    second_response = client.patch(
        f"/api/v1/admin/users/{target_id}/approve",
        headers=auth_headers(admin_id),
        json={"role": "administrator"},
    )

    assert second_response.status_code == 409


def test_invalid_approval_role_is_rejected():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )
    target_id = create_test_user()

    response = client.patch(
        f"/api/v1/admin/users/{target_id}/approve",
        headers=auth_headers(admin_id),
        json={"role": "pending"},
    )

    assert response.status_code == 422


def test_admin_cannot_approve_own_account():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    response = client.patch(
        f"/api/v1/admin/users/{admin_id}/approve",
        headers=auth_headers(admin_id),
        json={"role": "monitoring_operator"},
    )

    assert response.status_code == 400


def test_missing_token_cannot_access_admin_endpoint():
    response = client.get("/api/v1/admin/pending-users")

    assert response.status_code == 401


def test_inactive_admin_cannot_access_admin_endpoint():
    admin_id = create_test_user(
        role="administrator",
        is_active=False,
    )

    response = client.get(
        "/api/v1/admin/pending-users",
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 403


def test_approval_unknown_user_returns_404():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    response = client.patch(
        f"/api/v1/admin/users/{uuid4()}/approve",
        headers=auth_headers(admin_id),
        json={"role": "monitoring_operator"},
    )

    assert response.status_code == 404
