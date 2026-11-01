from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.video import Video


client = TestClient(app)


def create_test_user(role="pending", is_active=False):
    user = User(
        email=f"video-list-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Video",
        last_name="Tester",
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


def create_test_video(user_id):
    video = Video(
        uploaded_by=user_id,
        original_filename=f"road-{uuid4().hex[:8]}.mp4",
        stored_filename=f"{uuid4().hex}.mp4",
        storage_key=f"{uuid4().hex}.mp4",
        content_type="video/mp4",
        file_size_bytes=1024,
        sha256="a" * 64,
        status="uploaded",
    )

    with SessionLocal() as db:
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id


def test_video_listing_requires_authentication():
    response = client.get("/api/v1/videos")

    assert response.status_code == 401


def test_pending_user_cannot_list_videos():
    user_id = create_test_user()

    response = client.get(
        "/api/v1/videos",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_inactive_operator_cannot_list_videos():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=False,
    )

    response = client.get(
        "/api/v1/videos",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_active_operator_can_list_videos():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    video_id = create_test_video(user_id)

    response = client.get(
        "/api/v1/videos",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert any(item["id"] == str(video_id) for item in data)


def test_administrator_can_list_videos():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    response = client.get(
        "/api/v1/videos",
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_video_listing_pagination():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    for _ in range(3):
        create_test_video(user_id)

    headers = auth_headers(user_id)

    first_page = client.get(
        "/api/v1/videos?limit=2&offset=0",
        headers=headers,
    )

    second_page = client.get(
        "/api/v1/videos?limit=2&offset=2",
        headers=headers,
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 2

    first_ids = {item["id"] for item in first_page.json()}
    second_ids = {item["id"] for item in second_page.json()}

    assert first_ids.isdisjoint(second_ids)


def test_video_listing_rejects_invalid_pagination():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    headers = auth_headers(user_id)

    response = client.get(
        "/api/v1/videos?limit=101",
        headers=headers,
    )

    assert response.status_code == 422


def test_video_listing_does_not_expose_storage_details():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    create_test_video(user_id)

    response = client.get(
        "/api/v1/videos",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200

    for video in response.json():
        assert "storage_key" not in video
        assert "stored_filename" not in video
        assert "storage_path" not in video