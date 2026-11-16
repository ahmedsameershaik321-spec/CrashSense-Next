
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB

ALLOWED_EXTENSIONS = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
}

# Basic container signatures. Some formats have variable headers,
# so this is an initial format check, not a complete media parser.
SIGNATURES = {
    ".mp4": (b"ftyp", 4),
    ".mov": (b"ftyp", 4),
    ".avi": (b"RIFF", 0),
    ".mkv": (b"\x1a\x45\xdf\xa3", 0),
}


class VideoStorageError(Exception):
    """Raised when video storage or validation fails."""


@dataclass(frozen=True)
class StoredVideo:
    stored_filename: str
    storage_key: str
    file_size_bytes: int
    sha256: str
    content_type: str


def get_video_storage_path() -> Path:
    """Return the resolved private video storage directory."""
    configured_path = Path(settings.video_storage_dir)

    if not configured_path.is_absolute():
        configured_path = Path(__file__).resolve().parents[2] / configured_path

    storage_path = configured_path.resolve()
    storage_path.mkdir(parents=True, exist_ok=True)

    return storage_path


def validate_video_filename(filename: str | None) -> tuple[str, str]:
    """Validate the extension and return a safe extension and MIME type."""
    if not filename:
        raise VideoStorageError("A filename is required.")

    # Ignore client-supplied directory components.
    safe_name = filename.replace("\\", "/").split("/")[-1]

    if not safe_name or safe_name in {".", ".."}:
        raise VideoStorageError("Invalid filename.")

    extension = Path(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise VideoStorageError(
            "Unsupported video format. Allowed formats: MP4, MOV, AVI, MKV."
        )

    return extension, ALLOWED_EXTENSIONS[extension]


def validate_video_signature(extension: str, header: bytes) -> None:
    """Perform a basic file signature check."""
    signature, offset = SIGNATURES[extension]

    if header[offset:offset + len(signature)] != signature:
        raise VideoStorageError(
            "The file content does not match the selected video format."
        )


async def save_video(upload: UploadFile) -> StoredVideo:
    """
    Save an uploaded video using a generated filename.

    The upload is streamed in chunks to enforce the size limit
    without loading the complete file into memory.
    """
    extension, content_type = validate_video_filename(upload.filename)

    max_size = settings.max_video_upload_size_mb * 1024 * 1024

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    storage_key = stored_filename

    storage_dir = get_video_storage_path()
    destination = (storage_dir / stored_filename).resolve()

    # Ensure the final path remains inside the private storage directory.
    if destination.parent != storage_dir:
        raise VideoStorageError("Invalid storage destination.")

    total_size = 0
    sha256 = hashlib.sha256()
    first_chunk = True

    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > max_size:
                    raise VideoStorageError(
                        f"Video exceeds the maximum upload size of "
                        f"{settings.max_video_upload_size_mb} MB."
                    )

                if first_chunk:
                    validate_video_signature(extension, chunk)
                    first_chunk = False

                sha256.update(chunk)
                output.write(chunk)

            if total_size == 0:
                raise VideoStorageError("The uploaded video is empty.")

            output.flush()
            os.fsync(output.fileno())

        return StoredVideo(
            stored_filename=stored_filename,
            storage_key=storage_key,
            file_size_bytes=total_size,
            sha256=sha256.hexdigest(),
            content_type=content_type,
        )

    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Could not remove partial video upload file %s.",
                stored_filename,
            )
        raise

    finally:
        await upload.close()



def _validate_storage_key(storage_key: str) -> None:
    """Validate a generated video storage key."""
    if not re.fullmatch(
        r"[a-f0-9]{32}\.(mp4|mov|avi|mkv)",
        storage_key,
    ):
        raise VideoStorageError("Invalid storage key.")


def get_stored_video_path(storage_key: str) -> Path:
    """Resolve a generated storage key to a file inside private storage."""
    _validate_storage_key(storage_key)

    storage_dir = get_video_storage_path()

    try:
        destination = (storage_dir / storage_key).resolve(strict=True)
    except FileNotFoundError:
        raise
    except (OSError, RuntimeError) as exc:
        raise VideoStorageError("Invalid storage destination.") from exc

    if destination.parent != storage_dir or not destination.is_file():
        raise VideoStorageError("Invalid storage destination.")

    return destination


def _validate_quarantine_key(quarantine_key: str) -> None:
    """Validate a generated quarantine key."""
    if not re.fullmatch(
        r"\.deleting-[a-f0-9]{32}\.tmp",
        quarantine_key,
    ):
        raise VideoStorageError("Invalid quarantine key.")


def delete_stored_video(storage_key: str) -> None:
    """Delete a stored video without allowing path traversal."""
    _validate_storage_key(storage_key)

    storage_dir = get_video_storage_path()
    destination = (storage_dir / storage_key).resolve()

    if destination.parent != storage_dir:
        raise VideoStorageError("Invalid storage destination.")

    destination.unlink(missing_ok=True)


def quarantine_stored_video(storage_key: str) -> str:
    """
    Atomically move a video into quarantine.

    Returns the generated quarantine key, which is needed
    to restore or permanently delete the file.
    """
    _validate_storage_key(storage_key)

    storage_dir = get_video_storage_path()

    source = (storage_dir / storage_key).resolve()

    if source.parent != storage_dir:
        raise VideoStorageError("Invalid storage destination.")

    if not source.is_file():
        raise VideoStorageError("Video file does not exist.")

    quarantine_key = f".deleting-{uuid.uuid4().hex}.tmp"
    quarantine_path = (storage_dir / quarantine_key).resolve()

    if quarantine_path.parent != storage_dir:
        raise VideoStorageError("Invalid quarantine destination.")

    try:
        source.rename(quarantine_path)
    except OSError as exc:
        raise VideoStorageError(
            "Could not quarantine the video file."
        ) from exc

    return quarantine_key


def restore_quarantined_video(
    storage_key: str,
    quarantine_key: str,
) -> None:
    """Restore a quarantined video to its original storage key."""
    _validate_storage_key(storage_key)
    _validate_quarantine_key(quarantine_key)

    storage_dir = get_video_storage_path()

    source = (storage_dir / quarantine_key).resolve()
    destination = (storage_dir / storage_key).resolve()

    if source.parent != storage_dir or destination.parent != storage_dir:
        raise VideoStorageError("Invalid storage destination.")

    if not source.is_file():
        raise VideoStorageError("Quarantined video does not exist.")

    if destination.exists():
        raise VideoStorageError(
            "Cannot restore video: original destination already exists."
        )

    try:
        source.rename(destination)
    except OSError as exc:
        raise VideoStorageError(
            "Could not restore the quarantined video."
        ) from exc


def permanently_delete_quarantined_video(
    quarantine_key: str,
) -> None:
    """Permanently remove a quarantined video."""
    _validate_quarantine_key(quarantine_key)

    storage_dir = get_video_storage_path()
    destination = (storage_dir / quarantine_key).resolve()

    if destination.parent != storage_dir:
        raise VideoStorageError("Invalid quarantine destination.")

    destination.unlink(missing_ok=True)
