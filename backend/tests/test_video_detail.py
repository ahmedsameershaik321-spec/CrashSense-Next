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
        email=f"video-detail-{uuid4().hex}@example.com",
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
        original_filename="road.mp4",
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


def test_video_detail_requires_authentication():
    response = client.get(f"/api/v1/videos/{uuid4()}")

    assert response.status_code == 401


def test_pending_user_cannot_access_video_detail():
    user_id = create_test_user()
    video_id = create_test_video(user_id)

    response = client.get(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_inactive_operator_cannot_access_video_detail():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=False,
    )
    video_id = create_test_video(user_id)

    response = client.get(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_active_operator_can_access_video_detail():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )
    video_id = create_test_video(user_id)

    response = client.get(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(video_id)
    assert data["original_filename"] == "road.mp4"
    assert data["content_type"] == "video/mp4"
    assert data["file_size_bytes"] == 1024
    assert data["status"] == "uploaded"


def test_administrator_can_access_video_detail():
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )
    video_id = create_test_video(admin_id)

    response = client.get(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 200


def test_unknown_video_returns_404():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = client.get(
        f"/api/v1/videos/{uuid4()}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 404


def test_video_detail_does_not_expose_storage_information():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )
    video_id = create_test_video(user_id)

    response = client.get(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200

    data = response.json()

    assert "storage_key" not in data
    assert "stored_filename" not in data
    assert "storage_path" not in data