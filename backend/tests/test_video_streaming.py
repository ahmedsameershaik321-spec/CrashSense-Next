from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.api.v1.endpoints.videos import _stream_file
from app.models.user import User
from app.models.video import Video


client = TestClient(app)
VIDEO_CONTENT = b"0123456789abcdefghijklmnopqrstuvwxyz"


def test_stream_endpoint_documents_range_responses():
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/videos/{video_id}/stream"]["get"]

    assert "206" in operation["responses"]
    assert "416" in operation["responses"]
    range_parameter = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "Range"
    )
    assert "byte range" in range_parameter["description"]


def test_unexpected_stream_error_is_logged_and_file_is_closed(caplog):
    class BrokenVideoFile:
        closed = False

        def seek(self, start):
            pass

        def read(self, length):
            raise RuntimeError("simulated storage read failure")

        def close(self):
            self.closed = True

    video_file = BrokenVideoFile()
    stream = _stream_file(video_file, 0, 1, uuid4())

    with pytest.raises(RuntimeError, match="simulated storage read failure"):
        next(stream)

    assert "Video stream failed for video" in caplog.text
    assert video_file.closed


@pytest.fixture
def video_storage(tmp_path, monkeypatch):
    storage = tmp_path / "videos"
    monkeypatch.setattr(settings, "video_storage_dir", str(storage))
    storage.mkdir()
    return storage


def create_test_user(role="pending", is_active=False):
    user = User(
        email=f"video-stream-{uuid4().hex}@example.com",
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


def create_test_video(user_id, storage_dir, storage_key=None, create_file=True):
    storage_key = storage_key or f"{uuid4().hex}.mp4"

    if create_file:
        (storage_dir / storage_key).write_bytes(VIDEO_CONTENT)

    video = Video(
        uploaded_by=user_id,
        original_filename="road.mp4",
        stored_filename=storage_key,
        storage_key=storage_key,
        content_type="video/mp4",
        file_size_bytes=len(VIDEO_CONTENT),
        sha256="a" * 64,
        status="uploaded",
    )

    with SessionLocal() as db:
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id


def test_active_operator_can_stream_full_video(video_storage):
    user_id = create_test_user("monitoring_operator", is_active=True)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.content == VIDEO_CONTENT
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(VIDEO_CONTENT))
    assert response.headers["content-type"] == "video/mp4"
    assert "content-range" not in response.headers


def test_active_administrator_can_stream_video(video_storage):
    user_id = create_test_user("administrator", is_active=True)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.content == VIDEO_CONTENT


@pytest.mark.parametrize(
    ("range_header", "expected_content", "expected_range"),
    [
        ("bytes=4-9", VIDEO_CONTENT[4:10], "bytes 4-9/36"),
        ("bytes=30-", VIDEO_CONTENT[30:], "bytes 30-35/36"),
        ("bytes=-6", VIDEO_CONTENT[-6:], "bytes 30-35/36"),
        ("bytes=34-99", VIDEO_CONTENT[34:], "bytes 34-35/36"),
        ("bytes=0-0", VIDEO_CONTENT[:1], "bytes 0-0/36"),
    ],
)
def test_video_stream_supports_byte_range(
    video_storage,
    range_header,
    expected_content,
    expected_range,
):
    user_id = create_test_user("monitoring_operator", is_active=True)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers={
            **auth_headers(user_id),
            "Range": range_header,
        },
    )

    assert response.status_code == 206
    assert response.content == expected_content
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == expected_range
    assert response.headers["content-length"] == str(len(expected_content))


def test_multiple_byte_ranges_fall_back_to_full_response(video_storage):
    user_id = create_test_user("monitoring_operator", is_active=True)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers={
            **auth_headers(user_id),
            "Range": "bytes=0-1,4-5",
        },
    )

    assert response.status_code == 200
    assert response.content == VIDEO_CONTENT
    assert "content-range" not in response.headers


@pytest.mark.parametrize(
    "range_header",
    [
        "bytes=abc-def",
        "bytes=36-",
        "bytes=9-3",
        "bytes=-0",
    ],
)
def test_invalid_or_unsatisfiable_range_returns_416(
    video_storage,
    range_header,
):
    user_id = create_test_user("monitoring_operator", is_active=True)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers={
            **auth_headers(user_id),
            "Range": range_header,
        },
    )

    assert response.status_code == 416
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == "bytes */36"
    assert response.json()["detail"]


def test_missing_video_returns_404(video_storage):
    user_id = create_test_user("monitoring_operator", is_active=True)

    response = client.get(
        f"/api/v1/videos/{uuid4()}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found."


def test_missing_video_file_returns_404(video_storage):
    user_id = create_test_user("monitoring_operator", is_active=True)
    video_id = uuid4()
    video = Video(
        id=video_id,
        uploaded_by=user_id,
        original_filename="road.mp4",
        stored_filename=f"{uuid4().hex}.mp4",
        storage_key=f"{uuid4().hex}.mp4",
        content_type="video/mp4",
        file_size_bytes=len(VIDEO_CONTENT),
        sha256="a" * 64,
        status="uploaded",
    )

    with SessionLocal() as db:
        db.add(video)
        db.commit()

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video file not found."


def test_stream_requires_authentication(video_storage):
    response = client.get(f"/api/v1/videos/{uuid4()}/stream")

    assert response.status_code == 401


def test_pending_user_cannot_stream_video(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_inactive_operator_cannot_stream_video(video_storage):
    user_id = create_test_user("monitoring_operator", is_active=False)
    video_id = create_test_video(user_id, video_storage)

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 403


def test_invalid_stored_path_is_rejected_without_exposing_path(
    tmp_path,
    video_storage,
):
    user_id = create_test_user("monitoring_operator", is_active=True)
    traversal_key = f"../outside-{uuid4().hex}.mp4"
    outside_file = tmp_path / traversal_key.split("/")[-1]
    outside_file.write_bytes(b"private")
    video_id = create_test_video(
        user_id,
        video_storage,
        storage_key=traversal_key,
        create_file=False,
    )

    response = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Video storage is unavailable."
    assert str(outside_file) not in response.text
