import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.video import Video
from app.services.detection.frames import VideoProcessingError
from app.services.detection.pipeline import AnalysisCancelled, analyze_video
from app.services.video_storage import VideoStorageError, get_stored_video_path


logger = logging.getLogger(__name__)


def _recover_stale_jobs() -> None:
    stale_before = datetime.now(timezone.utc) - timedelta(
        minutes=settings.detection_stale_job_minutes
    )
    with SessionLocal() as db:
        jobs = db.scalars(
            select(AnalysisJob)
            .where(
                AnalysisJob.status == "processing",
                AnalysisJob.updated_at < stale_before,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            if job.cancel_requested:
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
            else:
                job.status = "queued"
                job.started_at = None
                logger.warning("Re-queued stale video analysis job %s.", job.id)
        db.commit()


def _claim_job() -> UUID | None:
    with SessionLocal() as db:
        job = db.scalars(
            select(AnalysisJob)
            .where(AnalysisJob.status == "queued")
            .order_by(AnalysisJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if job is None:
            return None

        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()
        return job.id


def _is_cancel_requested(job_id: UUID) -> bool:
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        return job is None or job.cancel_requested or job.status != "processing"


def _update_progress(job_id: UUID, progress: int) -> None:
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if job is not None and job.status == "processing":
            job.progress = min(99, max(job.progress, progress))
            job.updated_at = datetime.now(timezone.utc)
            db.commit()


def _finish_job(
    job_id: UUID,
    status_value: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            logger.warning("Analysis job %s disappeared before completion.", job_id)
            return
        if job.status == "cancelled":
            return

        if job.cancel_requested:
            status_value = "cancelled"
            result = None

        job.status = status_value
        job.result = result
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        if status_value == "completed":
            job.progress = 100
        db.commit()


def _process_job(job_id: UUID) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            if job is None or job.status != "processing":
                return
            video = db.get(Video, job.video_id)
            if video is None:
                raise VideoProcessingError("The source video record was removed.")
            storage_key = video.storage_key

        video_path = get_stored_video_path(storage_key)
        result = analyze_video(
            video_path,
            progress_callback=lambda value: _update_progress(job_id, value),
            cancellation_requested=lambda: _is_cancel_requested(job_id),
        )
    except AnalysisCancelled:
        _finish_job(job_id, "cancelled")
    except (VideoProcessingError, VideoStorageError) as exc:
        logger.warning("Video analysis job %s could not process its source.", job_id)
        _finish_job(
            job_id,
            "failed",
            error_message=str(exc)[:500],
        )
    except Exception:
        logger.exception("Video analysis job %s failed unexpectedly.", job_id)
        _finish_job(
            job_id,
            "failed",
            error_message=(
                "Video analysis failed. Check server logs and model configuration."
            ),
        )
    else:
        _finish_job(job_id, "completed", result=result)


class AnalysisJobWorker:
    """Single-threaded per-process worker using PostgreSQL row-lock claiming."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="video-analysis-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            if not self._thread.is_alive():
                self._thread = None

    def _run(self) -> None:
        recovered = False
        next_recovery = datetime.now(timezone.utc)
        while not self._stop_event.is_set():
            try:
                if (
                    not recovered
                    or datetime.now(timezone.utc) >= next_recovery
                ):
                    _recover_stale_jobs()
                    recovered = True
                    next_recovery = datetime.now(timezone.utc) + timedelta(minutes=1)
                job_id = _claim_job()
                if job_id is not None:
                    _process_job(job_id)
                    continue
            except Exception:
                logger.exception("Video analysis worker iteration failed.")
            self._stop_event.wait(settings.detection_worker_poll_seconds)


analysis_job_worker = AnalysisJobWorker()
