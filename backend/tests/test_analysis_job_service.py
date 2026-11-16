from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.user import User
from app.models.video import Video
from app.services import analysis_jobs
from app.services.detection.accident_classifier import AccidentClassifierError
from app.services.detection.pipeline import AnalysisCancelled
from app.services.detection.yolo import DetectionModelError


class FakeScalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def all(self):
        return [self.value]


class FakeDatabase:
    def __init__(self, job):
        self.job = job

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def scalars(self, statement):
        return FakeScalars(self.job)

    def get(self, _model, _job_id):
        return self.job

    def commit(self):
        pass


def test_claiming_job_transitions_queued_to_processing(monkeypatch):
    job = AnalysisJob(
        id=uuid4(),
        video_id=uuid4(),
        requested_by=uuid4(),
        status="queued",
        progress=0,
    )
    monkeypatch.setattr(
        analysis_jobs,
        "SessionLocal",
        lambda: FakeDatabase(job),
    )

    claimed_id = analysis_jobs._claim_job()

    assert claimed_id == job.id
    assert job.status == "processing"
    assert isinstance(job.started_at, datetime)
    assert job.started_at.tzinfo == timezone.utc


def test_progress_update_skips_redundant_database_commit(monkeypatch):
    job = AnalysisJob(
        id=uuid4(),
        video_id=uuid4(),
        requested_by=uuid4(),
        status="processing",
        progress=40,
    )
    database = FakeDatabase(job)
    commits = []
    database.commit = lambda: commits.append(job.progress)
    monkeypatch.setattr(analysis_jobs, "SessionLocal", lambda: database)

    analysis_jobs._update_progress(job.id, 40)
    assert commits == []

    analysis_jobs._update_progress(job.id, 45)
    assert job.progress == 45
    assert commits == [45]


def test_stale_processing_job_is_requeued(monkeypatch):
    job = AnalysisJob(
        id=uuid4(),
        video_id=uuid4(),
        requested_by=uuid4(),
        status="processing",
        progress=25,
    )
    job.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    monkeypatch.setattr(
        analysis_jobs,
        "SessionLocal",
        lambda: FakeDatabase(job),
    )

    analysis_jobs._recover_stale_jobs()

    assert job.status == "queued"
    assert job.started_at is None


def test_stale_job_with_cancel_request_becomes_cancelled(monkeypatch):
    job = AnalysisJob(
        id=uuid4(),
        video_id=uuid4(),
        requested_by=uuid4(),
        status="processing",
        progress=25,
        cancel_requested=True,
    )
    job.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    monkeypatch.setattr(
        analysis_jobs,
        "SessionLocal",
        lambda: FakeDatabase(job),
    )

    analysis_jobs._recover_stale_jobs()

    assert job.status == "cancelled"
    assert job.completed_at is not None


def create_processing_job(storage_dir):
    user_id = uuid4()
    video_id = uuid4()
    user = User(
        id=user_id,
        email=f"analysis-worker-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Analysis",
        last_name="Worker",
        role="monitoring_operator",
        is_active=True,
        is_email_verified=False,
    )
    storage_key = f"{uuid4().hex}.mp4"
    (storage_dir / storage_key).write_bytes(b"test-video")
    video = Video(
        id=video_id,
        uploaded_by=user_id,
        original_filename="road.mp4",
        stored_filename=storage_key,
        storage_key=storage_key,
        content_type="video/mp4",
        file_size_bytes=10,
        sha256="a" * 64,
        status="uploaded",
    )
    job = AnalysisJob(
        video_id=video_id,
        requested_by=user_id,
        status="processing",
        progress=0,
    )
    with SessionLocal() as db:
        db.add(user)
        db.flush()
        db.add(video)
        db.flush()
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


def test_processing_job_persists_completed_result(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage_dir))
    job_id = create_processing_job(storage_dir)
    expected_result = {
        "summary": {"frames_processed": 1},
        "frames": [],
        "candidates": [],
    }
    monkeypatch.setattr(
        analysis_jobs,
        "analyze_video",
        lambda *args, **kwargs: expected_result,
    )

    analysis_jobs._process_job(job_id)

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job.status == "completed"
        assert job.progress == 100
        assert job.result == expected_result
        assert job.completed_at is not None


def test_inference_failure_transitions_job_to_failed(
    tmp_path,
    monkeypatch,
    caplog,
):
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage_dir))
    job_id = create_processing_job(storage_dir)

    def fail_inference(*args, **kwargs):
        raise RuntimeError("private inference detail")

    monkeypatch.setattr(analysis_jobs, "analyze_video", fail_inference)
    analysis_jobs._process_job(job_id)

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job.status == "failed"
        assert job.error_message == (
            "Video analysis failed. Check server logs and model configuration."
        )
        assert "private inference detail" not in job.error_message
    assert "private inference detail" in caplog.text


def test_detector_failure_message_is_persisted(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage_dir))
    job_id = create_processing_job(storage_dir)
    error_message = "Could not load configured YOLO weights: missing.pt."

    def fail_inference(*args, **kwargs):
        raise DetectionModelError(error_message)

    monkeypatch.setattr(analysis_jobs, "analyze_video", fail_inference)
    analysis_jobs._process_job(job_id)

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job.status == "failed"
        assert job.error_message == error_message


def test_classifier_failure_message_is_persisted(tmp_path, monkeypatch):
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage_dir))
    job_id = create_processing_job(storage_dir)
    error_message = "Configured classifier checkpoint is incompatible."

    def fail_inference(*args, **kwargs):
        raise AccidentClassifierError(error_message)

    monkeypatch.setattr(analysis_jobs, "analyze_video", fail_inference)
    analysis_jobs._process_job(job_id)

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job.status == "failed"
        assert job.error_message == error_message


def test_processing_job_honors_cancellation_request(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage_dir))
    job_id = create_processing_job(storage_dir)

    def cancel_during_inference(
        video_path,
        progress_callback,
        cancellation_requested,
    ):
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            job.cancel_requested = True
            db.commit()
        if cancellation_requested():
            raise AnalysisCancelled
        raise AssertionError("Cancellation request was not observed.")

    monkeypatch.setattr(
        analysis_jobs,
        "analyze_video",
        cancel_during_inference,
    )
    analysis_jobs._process_job(job_id)

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job.status == "cancelled"
        assert job.completed_at is not None
