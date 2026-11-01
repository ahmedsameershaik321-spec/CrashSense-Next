
import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_operator
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse
from app.services.video_storage import (
    VideoStorageError,
    delete_stored_video,
    permanently_delete_quarantined_video,
    quarantine_stored_video,
    restore_quarantined_video,
    save_video,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)


@router.post(
    "/upload",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Upload and securely store a video for accident analysis."""

    try:
        stored = await save_video(file)

    except VideoStorageError as exc:
        message = str(exc)

        if "exceeds the maximum upload size" in message:
            error_status = status.HTTP_413_CONTENT_TOO_LARGE
        elif "Unsupported video format" in message:
            error_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        else:
            error_status = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=error_status,
            detail=message,
        ) from exc

    video = Video(
        uploaded_by=current_user.id,
        original_filename=(file.filename or "uploaded-video")[:255],
        stored_filename=stored.stored_filename,
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        file_size_bytes=stored.file_size_bytes,
        sha256=stored.sha256,
        status="uploaded",
    )

    try:
        db.add(video)
        db.commit()

    except Exception:
        db.rollback()

        # Remove the stored file if its database record was not committed.
        try:
            delete_stored_video(stored.storage_key)
        except Exception:
            # Preserve the original database exception.
            pass

        raise

    db.refresh(video)
    return video

@router.get(
    "",
    response_model=list[VideoResponse],
)
def list_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List uploaded videos with pagination."""

    statement = (
        select(Video)
        .order_by(Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return db.scalars(statement).all()
@router.get(
    "/{video_id}",
    response_model=VideoResponse,
)
def get_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Retrieve metadata for a specific uploaded video."""

    video = db.get(Video, video_id)

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    return video

@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Safely delete a video using quarantine and database rollback.

    The database record is committed before permanent file removal.
    If the database transaction fails, the original file is restored.
    """

    # Lock the database row to prevent concurrent deletion.
    statement = (
        select(Video)
        .where(Video.id == video_id)
        .with_for_update()
    )

    video = db.scalars(statement).first()

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    storage_key = video.storage_key

    # Stage 1: Move the file into quarantine.
    try:
        quarantine_key = quarantine_stored_video(storage_key)

    except VideoStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not prepare the video for deletion.",
        ) from exc

    # Stage 2: Delete the database record.
    try:
        db.delete(video)
        db.commit()

    except Exception:
        db.rollback()

        # Restore the original file if the database transaction fails.
        try:
            restore_quarantined_video(
                storage_key,
                quarantine_key,
            )

        except Exception:
            logger.critical(
                "CRITICAL: Failed to restore video after database "
                "deletion failure. Storage key: %s, quarantine key: %s",
                storage_key,
                quarantine_key,
                exc_info=True,
            )

        raise

    # Stage 3: Permanently remove the quarantined file.
    try:
        permanently_delete_quarantined_video(quarantine_key)

    except Exception:
        # The database deletion has already succeeded.
        # Log the orphan for later cleanup instead of pretending
        # that physical deletion was successful.
        logger.exception(
            "Video database record deleted, but quarantined file "
            "cleanup failed. Quarantine key: %s",
            quarantine_key,
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
