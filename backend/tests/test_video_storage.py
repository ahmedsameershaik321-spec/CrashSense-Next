
import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile

from app.config import settings
from app.services.video_storage import (
    VideoStorageError,
    delete_stored_video,
    save_video,
    validate_video_filename,
    quarantine_stored_video,
    restore_quarantined_video,
    permanently_delete_quarantined_video,
)

@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "video_storage_dir", str(tmp_path / "videos")
    )
    return tmp_path / "videos"


def make_upload(filename, content):
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
    )


def test_accepts_supported_formats():
    assert validate_video_filename("road.mp4")[0] == ".mp4"
    assert validate_video_filename("road.mov")[0] == ".mov"
    assert validate_video_filename("road.avi")[0] == ".avi"
    assert validate_video_filename("road.mkv")[0] == ".mkv"


def test_rejects_unsupported_format():
    with pytest.raises(VideoStorageError):
        validate_video_filename("document.pdf")


def test_rejects_missing_filename():
    with pytest.raises(VideoStorageError):
        validate_video_filename(None)


def test_rejects_path_filename_without_trusting_directories():
    extension, _ = validate_video_filename("../../road.mp4")
    assert extension == ".mp4"


def test_saves_valid_mp4(storage_dir):
    content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    result = asyncio.run(
        save_video(make_upload("road.mp4", content))
    )

    saved_file = storage_dir / result.stored_filename

    assert saved_file.exists()
    assert saved_file.read_bytes() == content
    assert result.file_size_bytes == len(content)
    assert len(result.sha256) == 64
    assert result.content_type == "video/mp4"


def test_rejects_invalid_video_signature(storage_dir):
    with pytest.raises(VideoStorageError):
        asyncio.run(
            save_video(make_upload("fake.mp4", b"not a video"))
        )

    assert list(storage_dir.glob("*")) == []


def test_rejects_empty_video(storage_dir):
    with pytest.raises(VideoStorageError):
        asyncio.run(save_video(make_upload("empty.mp4", b"")))

    assert list(storage_dir.glob("*")) == []


def test_rejects_video_exceeding_limit(storage_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_video_upload_size_mb", 1)

    content = b"\x00\x00\x00\x18ftypisom" + b"x" * (1024 * 1024)

    with pytest.raises(VideoStorageError, match="maximum upload size"):
        asyncio.run(
            save_video(make_upload("large.mp4", content))
        )

    assert list(storage_dir.glob("*")) == []


def test_deletes_stored_video(storage_dir):
    content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    result = asyncio.run(
        save_video(make_upload("road.mp4", content))
    )

    delete_stored_video(result.storage_key)

    assert not (storage_dir / result.stored_filename).exists()


def test_rejects_path_traversal_storage_key():
    with pytest.raises(VideoStorageError):
        delete_stored_video("../../important.mp4")


def test_quarantine_stored_video(storage_dir):
    content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    result = asyncio.run(
        save_video(make_upload("road.mp4", content))
    )

    original_path = storage_dir / result.storage_key

    quarantine_key = quarantine_stored_video(result.storage_key)
    quarantine_path = storage_dir / quarantine_key

    assert not original_path.exists()
    assert quarantine_path.exists()
    assert quarantine_path.read_bytes() == content


def test_restores_quarantined_video(storage_dir):
    content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    result = asyncio.run(
        save_video(make_upload("road.mp4", content))
    )

    original_path = storage_dir / result.storage_key

    quarantine_key = quarantine_stored_video(result.storage_key)

    restore_quarantined_video(
        result.storage_key,
        quarantine_key,
    )

    assert original_path.exists()
    assert original_path.read_bytes() == content
    assert not (storage_dir / quarantine_key).exists()


def test_permanently_deletes_quarantined_video(storage_dir):
    content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100

    result = asyncio.run(
        save_video(make_upload("road.mp4", content))
    )

    quarantine_key = quarantine_stored_video(result.storage_key)

    quarantine_path = storage_dir / quarantine_key

    assert quarantine_path.exists()

    permanently_delete_quarantined_video(quarantine_key)

    assert not quarantine_path.exists()


def test_rejects_invalid_quarantine_key():
    with pytest.raises(VideoStorageError):
        restore_quarantined_video(
            "../../important.mp4",
            "../../important.tmp",
        )


def test_rejects_invalid_quarantine_key_for_permanent_delete():
    with pytest.raises(VideoStorageError):
        permanently_delete_quarantined_video(
            "../../important.tmp"
        )


def test_quarantine_rejects_missing_video(storage_dir):
    with pytest.raises(
        VideoStorageError,
        match="Video file does not exist",
    ):
        quarantine_stored_video("a" * 32 + ".mp4")
