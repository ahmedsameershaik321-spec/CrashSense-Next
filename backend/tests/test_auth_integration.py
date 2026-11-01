
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_register_user():
    email = f"test_{uuid4().hex}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "IntegrationTest123!",
            "first_name": "Integration",
            "last_name": "Test",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["role"] == "pending"
    assert "user_id" in data


def test_login_with_invalid_password():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "crashsense.test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_success():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "crashsense.test@example.com",
            "password": "CrashSenseTest123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert "access_token" in data


def test_access_profile_with_jwt():
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "crashsense.test@example.com",
            "password": "CrashSenseTest123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    profile = response.json()

    assert profile["email"] == "crashsense.test@example.com"
    assert profile["role"] == "pending"
    assert profile["is_active"] is False

def test_profile_without_token():
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_profile_with_invalid_token():
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer invalid.jwt.token"
        },
    )

    assert response.status_code == 401

def test_pending_user_cannot_access_operator_endpoint():
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "crashsense.test@example.com",
            "password": "CrashSenseTest123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/operator/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Your account is inactive. Contact an administrator."
    )
