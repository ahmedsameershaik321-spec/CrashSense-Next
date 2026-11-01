
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.video import Video


client = TestClient(app)


def create_test_user(role="pending", is_active=False):
    user = User(
        email=f"video-delete-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Video",
        last_name="DeleteTester",
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


def create_test_video(user_id, storage_dir):
    stored_filename = f"{uuid4().hex}.mp4"

    video_content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    video_file = storage_dir / stored_filename
    video_file.write_bytes(video_content)

    video = Video(
        uploaded_by=user_id,
        original_filename="road.mp4",
        stored_filename=stored_filename,
        storage_key=stored_filename,
        content_type="video/mp4",
        file_size_bytes=len(video_content),
        sha256="a" * 64,
        status="uploaded",
    )

    with SessionLocal() as db:
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id, video_file


import pytest


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    directory = tmp_path / "videos"

    monkeypatch.setattr(
        settings,
        "video_storage_dir",
        str(directory),
    )

    directory.mkdir(parents=True)

    return directory


def video_exists(video_id):
    with SessionLocal() as db:
        return db.get(Video, video_id) is not None


def test_video_deletion_requires_authentication():
    response = client.delete(
        f"/api/v1/videos/{uuid4()}"
    )

    assert response.status_code == 401


def test_pending_user_cannot_delete_video(storage_dir):
    user_id = create_test_user()

    video_id, video_file = create_test_video(
        user_id,
        storage_dir,
    )

    response = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403
    assert video_exists(video_id)
    assert video_file.exists()


def test_inactive_operator_cannot_delete_video(storage_dir):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=False,
    )

    video_id, video_file = create_test_video(
        user_id,
        storage_dir,
    )

    response = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403
    assert video_exists(video_id)
    assert video_file.exists()


def test_active_operator_can_delete_video(storage_dir):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    video_id, video_file = create_test_video(
        user_id,
        storage_dir,
    )

    response = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 204
    assert not video_exists(video_id)
    assert not video_file.exists()


def test_administrator_can_delete_video(storage_dir):
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    video_id, video_file = create_test_video(
        admin_id,
        storage_dir,
    )

    response = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 204
    assert not video_exists(video_id)
    assert not video_file.exists()


def test_deleting_nonexistent_video_returns_404():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = client.delete(
        f"/api/v1/videos/{uuid4()}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 404


def test_delete_rejects_invalid_video_id():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = client.delete(
        "/api/v1/videos/not-a-valid-uuid",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 422

from unittest.mock import patch


def test_database_failure_restores_quarantined_video(storage_dir):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    video_id, video_file = create_test_video(
        user_id,
        storage_dir,
    )

    original_content = video_file.read_bytes()

    with patch(
    "app.api.v1.endpoints.videos.Session.commit",
    side_effect=RuntimeError("Simulated database failure"),
):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.delete(
            f"/api/v1/videos/{video_id}",
            headers=auth_headers(user_id),
        )

    assert response.status_code == 500

    # Database record must remain.
    assert video_exists(video_id)

    # Original video must be restored.
    assert video_file.exists()
    assert video_file.read_bytes() == original_content

    # No quarantine files should remain.
    assert list(storage_dir.glob(".deleting-*.tmp")) == []
def test_cleanup_failure_does_not_restore_deleted_video(storage_dir):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )
    video_id, video_file = create_test_video(user_id, storage_dir)

    with patch(
        "app.api.v1.endpoints.videos.permanently_delete_quarantined_video",
        side_effect=RuntimeError("Simulated cleanup failure"),
    ):
        response = client.delete(
            f"/api/v1/videos/{video_id}",
            headers=auth_headers(user_id),
        )

    assert response.status_code == 204
    assert not video_exists(video_id)
    assert not video_file.exists()

    quarantined_files = list(storage_dir.glob(".deleting-*.tmp"))
    assert len(quarantined_files) == 1