from io import BytesIO
from uuid import uuid4
from app.database import get_db
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.video import Video


client = TestClient(app)

VALID_MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100


def create_test_user(role="pending", is_active=False):
    user = User(
        email=f"video-test-{uuid4().hex}@example.com",
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


@pytest.fixture
def video_storage(tmp_path, monkeypatch):
    storage = tmp_path / "videos"

    monkeypatch.setattr(
        settings,
        "video_storage_dir",
        str(storage),
    )

    return storage


def upload_file(
    filename="road.mp4",
    content=VALID_MP4,
    headers=None,
):
    return client.post(
        "/api/v1/videos/upload",
        headers=headers,
        files={
            "file": (
                filename,
                BytesIO(content),
                "application/octet-stream",
            )
        },
    )


def test_upload_requires_authentication():
    response = upload_file()

    assert response.status_code == 401


def test_pending_user_cannot_upload():
    user_id = create_test_user()

    response = upload_file(
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_inactive_operator_cannot_upload():
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=False,
    )

    response = upload_file(
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_active_operator_can_upload(video_storage):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = upload_file(
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["original_filename"] == "road.mp4"
    assert data["content_type"] == "video/mp4"
    assert data["file_size_bytes"] == len(VALID_MP4)
    assert data["status"] == "uploaded"
    assert len(data["sha256"]) == 64

    # Internal storage details must never be exposed.
    assert "storage_key" not in data
    assert "stored_filename" not in data
    assert "storage_path" not in data

    assert len(list(video_storage.iterdir())) == 1

    with SessionLocal() as db:
        video = db.get(Video, data["id"])

        assert video is not None
        assert video.uploaded_by == user_id
        assert video.file_size_bytes == len(VALID_MP4)


def test_administrator_can_upload(video_storage):
    admin_id = create_test_user(
        role="administrator",
        is_active=True,
    )

    response = upload_file(
        headers=auth_headers(admin_id),
    )

    assert response.status_code == 201
    assert len(list(video_storage.iterdir())) == 1


def test_unsupported_extension_is_rejected(video_storage):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = upload_file(
        filename="document.pdf",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 415
    assert list(video_storage.glob("*")) == []


def test_invalid_video_signature_is_rejected(video_storage):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = upload_file(
        filename="fake.mp4",
        content=b"This is not a video file",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert list(video_storage.glob("*")) == []


def test_empty_video_is_rejected(video_storage):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    response = upload_file(
        content=b"",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert list(video_storage.glob("*")) == []


def test_oversized_video_is_rejected(video_storage, monkeypatch):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    monkeypatch.setattr(
        settings,
        "max_video_upload_size_mb",
        1,
    )

    oversized_content = (
        b"\x00\x00\x00\x18ftypisom"
        + b"x" * (1024 * 1024)
    )

    response = upload_file(
        content=oversized_content,
        headers=auth_headers(user_id),
    )

    assert response.status_code == 413
    assert list(video_storage.glob("*")) == []
def test_database_failure_removes_uploaded_file(
    video_storage,
    monkeypatch,
):
    user_id = create_test_user(
        role="monitoring_operator",
        is_active=True,
    )

    def override_get_db():
        with SessionLocal() as db:

            def fail_commit():
                raise RuntimeError("Simulated database failure")

            monkeypatch.setattr(db, "commit", fail_commit)
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with pytest.raises(RuntimeError, match="Simulated database failure"):
            upload_file(
                headers=auth_headers(user_id),
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert list(video_storage.glob("*")) == []