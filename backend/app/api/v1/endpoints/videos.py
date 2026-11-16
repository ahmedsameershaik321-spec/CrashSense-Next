
from collections.abc import Iterator
from datetime import datetime, timezone
import logging
import os
import re
from typing import BinaryIO
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.database import get_db
from app.dependencies.auth import require_admin, require_operator
from app.models.analysis_job import AnalysisJob
from app.models.camera import Camera
from app.models.emergency_alert import EmergencyAlertAudit
from app.models.user import User
from app.models.video import Video
from app.schemas.analysis import (
    AccidentCandidateResponse,
    AnalysisJobResponse,
    AnalysisResultsResponse,
)
from app.schemas.video import VideoResponse
from app.schemas.response import (
    EmergencyAlertCreate,
    EmergencyAlertResponse,
    NearbyResourcesResponse,
    VideoCameraAssignment,
    VideoLocationResponse,
)
from app.services.nearby_resources import (
    OSM_ATTRIBUTION,
    ResourceLookupError,
    find_nearby_resources,
)
from app.services.video_storage import (
    VideoStorageError,
    delete_stored_video,
    get_stored_video_path,
    permanently_delete_quarantined_video,
    quarantine_stored_video,
    restore_quarantined_video,
    save_video,
)


logger = logging.getLogger(__name__)

STREAM_CHUNK_SIZE = 1024 * 1024
BYTE_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")

router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)


@router.put(
    "/{video_id}/camera",
    response_model=VideoLocationResponse,
)
def assign_video_camera(
    video_id: UUID,
    assignment: VideoCameraAssignment,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    if assignment.camera_id is not None:
        camera = db.get(Camera, assignment.camera_id)
        if camera is None or not camera.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active registered camera not found.",
            )
        video.camera_id = camera.id
    else:
        video.camera_id = None
    db.commit()
    db.refresh(video)
    camera = db.get(Camera, video.camera_id) if video.camera_id else None
    return VideoLocationResponse(
        video_id=video.id,
        source="registered_camera" if camera else "unavailable",
        camera=camera,
    )


@router.get(
    "/{video_id}/location",
    response_model=VideoLocationResponse,
)
def get_video_location(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    camera = db.get(Camera, video.camera_id) if video.camera_id else None
    return VideoLocationResponse(
        video_id=video.id,
        source="registered_camera" if camera else "unavailable",
        camera=camera,
    )


@router.get(
    "/{video_id}/resources",
    response_model=NearbyResourcesResponse,
)
def get_video_nearby_resources(
    video_id: UUID,
    radius_meters: int = Query(default=5000, ge=100, le=50000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )
    camera = db.get(Camera, video.camera_id) if video.camera_id else None
    if camera is None or not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This video has no active registered camera location.",
        )
    try:
        resources = find_nearby_resources(
            camera.latitude,
            camera.longitude,
            radius_meters,
        )
    except ResourceLookupError as exc:
        logger.warning(
            "Nearby resource lookup failed for video %s: %s",
            video_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nearby OpenStreetMap resources are temporarily unavailable.",
        ) from exc
    return NearbyResourcesResponse(
        video_id=video.id,
        source="OpenStreetMap",
        source_url="https://www.openstreetmap.org/",
        attribution=OSM_ATTRIBUTION,
        center_latitude=camera.latitude,
        center_longitude=camera.longitude,
        radius_meters=radius_meters,
        resources=resources,
    )


def _get_analysis_job_or_404(
    db: Session,
    analysis_id: UUID,
) -> AnalysisJob:
    job = db.get(AnalysisJob, analysis_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )
    return job


@router.post(
    "/{video_id}/analysis",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {
            "description": "An active operator or administrator is required."
        },
        status.HTTP_404_NOT_FOUND: {"description": "Video not found."},
        status.HTTP_409_CONFLICT: {
            "description": "An analysis is already queued or processing."
        },
    },
)
def start_video_analysis(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Queue YOLO analysis without blocking the API request."""
    video = db.scalars(
        select(Video).where(Video.id == video_id).with_for_update()
    ).first()
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    active_job = db.scalars(
        select(AnalysisJob)
        .where(
            AnalysisJob.video_id == video_id,
            AnalysisJob.status.in_(("queued", "processing")),
        )
        .order_by(AnalysisJob.created_at.desc())
    ).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An analysis is already queued or processing for this video.",
        )

    job = AnalysisJob(
        video_id=video_id,
        requested_by=current_user.id,
        status="queued",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Queued video analysis job %s for video %s.", job.id, video_id)
    return job


@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisJobResponse,
)
def get_analysis_status(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return persistent job status and progress."""
    return _get_analysis_job_or_404(db, analysis_id)


@router.get(
    "/analysis/{analysis_id}/results",
    response_model=AnalysisResultsResponse,
)
def get_analysis_results(
    analysis_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return candidate results and a page of sampled frame evidence."""
    job = _get_analysis_job_or_404(db, analysis_id)
    if job.status != "completed" or job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis results are not available until processing completes.",
        )

    result = job.result
    frames = result["frames"]
    return AnalysisResultsResponse(
        job_id=job.id,
        video_id=job.video_id,
        summary=result["summary"],
        candidates=result["candidates"],
        frames=frames[offset:offset + limit],
        frame_offset=offset,
        total_frames=len(frames),
    )


@router.get(
    "/analysis/{analysis_id}/candidates",
    response_model=list[AccidentCandidateResponse],
)
def get_analysis_candidates(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return suspected and temporally verified detection events."""
    job = _get_analysis_job_or_404(db, analysis_id)
    if job.status != "completed" or job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis candidates are not available until processing completes.",
        )
    return job.result["candidates"]


@router.get(
    "/analysis/{analysis_id}/frames",
    response_model=list[dict],
)
def get_analysis_frame_evidence(
    analysis_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return sampled per-frame detections for timeline and playback use."""
    job = _get_analysis_job_or_404(db, analysis_id)
    if job.status != "completed" or job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Frame evidence is not available until processing completes.",
        )
    frames = job.result["frames"]
    return frames[offset:offset + limit]


@router.delete(
    "/analysis/{analysis_id}",
    response_model=AnalysisJobResponse,
)
def cancel_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Cancel queued analysis or request cancellation at the next sampled frame."""
    job = db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.id == analysis_id)
        .with_for_update()
    ).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )

    if job.status == "queued":
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
    elif job.status == "processing":
        job.cancel_requested = True
    elif job.status != "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only queued or processing analyses can be cancelled.",
        )

    db.commit()
    db.refresh(job)
    return job


@router.get(
    "/analysis/{analysis_id}/alerts",
    response_model=list[EmergencyAlertResponse],
)
def list_analysis_alert_audit(
    analysis_id: UUID,
    candidate_id: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    _get_analysis_job_or_404(db, analysis_id)
    statement = select(EmergencyAlertAudit).where(
        EmergencyAlertAudit.analysis_job_id == analysis_id
    )
    if candidate_id is not None:
        statement = statement.where(
            EmergencyAlertAudit.candidate_id == candidate_id
        )
    return db.scalars(
        statement.order_by(EmergencyAlertAudit.created_at.desc())
    ).all()


@router.post(
    "/analysis/{analysis_id}/alerts",
    response_model=EmergencyAlertResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_alert_audit(
    analysis_id: UUID,
    request: EmergencyAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    job = db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.id == analysis_id)
        .with_for_update()
    ).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )
    if job.status != "completed" or job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An alert audit record requires completed analysis results.",
        )
    if not any(
        isinstance(candidate, dict)
        and candidate.get("candidate_id") == request.candidate_id
        for candidate in job.result.get("candidates", [])
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found in this analysis.",
        )

    existing = db.scalar(
        select(EmergencyAlertAudit).where(
            EmergencyAlertAudit.analysis_job_id == analysis_id,
            EmergencyAlertAudit.candidate_id == request.candidate_id,
        )
    )
    if existing is not None:
        return existing

    audit = EmergencyAlertAudit(
        analysis_job_id=analysis_id,
        candidate_id=request.candidate_id,
        created_by=current_user.id,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def _range_error(file_size: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
        detail=detail,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes */{file_size}",
        },
    )


def _parse_byte_range(
    range_header: str | None,
    file_size: int,
) -> tuple[int, int, bool]:
    """Parse a single range, ignoring multipart requests."""
    if range_header is None or "," in range_header:
        return 0, file_size - 1, False

    match = BYTE_RANGE_PATTERN.fullmatch(range_header.strip())

    if match is None:
        raise _range_error(file_size, "Invalid byte range.")

    first, last = match.groups()

    if not first and not last:
        raise _range_error(file_size, "Invalid byte range.")

    try:
        if first:
            start = int(first)
            end = int(last) if last else file_size - 1

            if start >= file_size or end < start:
                raise _range_error(
                    file_size,
                    "Requested byte range is not satisfiable.",
                )
        else:
            suffix_length = int(last)

            if suffix_length == 0 or file_size == 0:
                raise _range_error(
                    file_size,
                    "Requested byte range is not satisfiable.",
                )

            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError as exc:
        raise _range_error(file_size, "Invalid byte range.") from exc

    return start, min(end, file_size - 1), True


def _stream_file(
    file: BinaryIO,
    start: int,
    length: int,
    video_id: UUID,
) -> Iterator[bytes]:
    """Yield a bounded number of bytes from an already-open video file."""
    try:
        file.seek(start)
        remaining = length

        while remaining:
            chunk = file.read(min(STREAM_CHUNK_SIZE, remaining))

            if not chunk:
                raise OSError("Video file ended before the requested bytes.")

            remaining -= len(chunk)
            yield chunk
    except Exception:
        logger.exception("Video stream failed for video %s.", video_id)
        raise
    finally:
        file.close()


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

    uploaded_by = current_user.id

    try:
        # Authentication only needs a read; release its connection during file I/O.
        db.rollback()
    except Exception as exc:
        logger.exception(
            "Could not release the database transaction before video upload "
            "for user %s.",
            uploaded_by,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The video could not be uploaded. Please try again.",
        ) from exc

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

    except Exception as exc:
        logger.exception("Unexpected storage error while uploading a video.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The video could not be uploaded. Please try again.",
        ) from exc

    video = Video(
        uploaded_by=uploaded_by,
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

    except Exception as exc:
        logger.exception(
            "Could not commit video upload record for user %s.",
            uploaded_by,
        )

        try:
            db.rollback()
        except Exception:
            logger.exception(
                "Could not roll back failed video upload record for user %s.",
                uploaded_by,
            )

        try:
            delete_stored_video(stored.storage_key)
        except Exception:
            logger.exception(
                "Could not remove video file after failed database commit "
                "for user %s.",
                uploaded_by,
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The video could not be uploaded. Please try again.",
        ) from exc

    try:
        db.refresh(video)
    except Exception as exc:
        logger.exception(
            "Could not refresh committed video upload record %s.",
            video.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The video could not be uploaded. Please try again.",
        ) from exc

    return video


@router.get(
    "/{video_id}/stream",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {"description": "Full video stream."},
        status.HTTP_206_PARTIAL_CONTENT: {
            "description": "Requested video byte range."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication is required."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "An active operator or administrator is required."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The video record or physical file was not found."
        },
        status.HTTP_416_RANGE_NOT_SATISFIABLE: {
            "description": "The requested byte range is invalid or unavailable."
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Video storage is unavailable."
        },
    },
)
def stream_video(
    video_id: UUID,
    range_header: str | None = Header(
        default=None,
        alias="Range",
        description="Single HTTP byte range; multipart ranges are ignored.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Stream a protected video, optionally returning a single byte range."""
    video = db.get(Video, video_id)

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found.",
        )

    stream_file = None

    try:
        video_path = get_stored_video_path(video.storage_key)
        stream_file = video_path.open("rb")
        file_size = os.fstat(stream_file.fileno()).st_size
        start, end, is_partial = _parse_byte_range(range_header, file_size)
    except HTTPException:
        if stream_file is not None:
            stream_file.close()
        raise
    except FileNotFoundError as exc:
        if stream_file is not None:
            stream_file.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found.",
        ) from exc
    except VideoStorageError as exc:
        logger.warning(
            "Video %s has an invalid storage destination.",
            video_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video storage is unavailable.",
        ) from exc
    except OSError as exc:
        if stream_file is not None:
            stream_file.close()
        logger.exception("Could not open video %s for streaming.", video_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video storage is unavailable.",
        ) from exc

    content_length = max(end - start + 1, 0)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }

    if is_partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    return StreamingResponse(
        _stream_file(stream_file, start, content_length, video_id),
        status_code=(
            status.HTTP_206_PARTIAL_CONTENT
            if is_partial
            else status.HTTP_200_OK
        ),
        media_type=video.content_type,
        headers=headers,
        background=BackgroundTask(stream_file.close),
    )


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

    active_job = db.scalars(
        select(AnalysisJob)
        .where(
            AnalysisJob.video_id == video_id,
            AnalysisJob.status.in_(("queued", "processing")),
        )
        .with_for_update()
    ).first()
    if active_job is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a video while analysis is queued or processing.",
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
