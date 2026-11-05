from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal, get_db
from app.main import app
from app.models.analysis_job import AnalysisJob
from app.models.user import User
from app.models.video import Video
from app.models.user import User


client = TestClient(app)


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _install_database_override(monkeypatch, db):
    def override_database():
        yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_database)


def test_dashboard_summary_returns_aggregates_and_recent_activity(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        role="monitoring_operator",
        is_active=True,
    )
    activity = SimpleNamespace(
        id=uuid4(),
        video_id=uuid4(),
        original_filename="north-road.mp4",
        status="completed",
        progress=100,
        candidate_count=2,
        created_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
    )
    db = Mock()
    db.get.return_value = user
    totals_result = Mock()
    totals_result.one.return_value = SimpleNamespace(
        total_videos=3,
        completed_analyses=2,
        processing_analyses=1,
        detected_candidates=4,
    )
    activity_result = Mock()
    activity_result.all.return_value = [activity]
    db.execute.side_effect = [totals_result, activity_result]
    _install_database_override(monkeypatch, db)

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_videos": 3,
        "completed_analyses": 2,
        "processing_analyses": 1,
        "detected_candidates": 4,
        "analysis_worker_running": False,
        "recent_activity": [
            {
                "analysis_id": str(activity.id),
                "video_id": str(activity.video_id),
                "video_name": "north-road.mp4",
                "status": "completed",
                "progress": 100,
                "candidate_count": 2,
                "created_at": "2026-11-05T00:00:00Z",
            }
        ],
    }
    assert db.execute.call_count == 2
    activity_query = str(db.execute.call_args_list[1].args[0])
    assert "LIMIT" in activity_query.upper()


def test_dashboard_summary_handles_empty_database(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        role="administrator",
        is_active=True,
    )
    db = Mock()
    db.get.return_value = user
    totals_result = Mock()
    totals_result.one.return_value = SimpleNamespace(
        total_videos=0,
        completed_analyses=0,
        processing_analyses=0,
        detected_candidates=0,
    )
    activity_result = Mock()
    activity_result.all.return_value = []
    db.execute.side_effect = [totals_result, activity_result]
    _install_database_override(monkeypatch, db)

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json()["total_videos"] == 0
    assert response.json()["detected_candidates"] == 0
    assert response.json()["recent_activity"] == []


def test_dashboard_summary_requires_active_operator_or_administrator(monkeypatch):
    pending_user = SimpleNamespace(
        id=uuid4(),
        role="pending",
        is_active=False,
    )
    db = Mock()
    db.get.return_value = pending_user
    _install_database_override(monkeypatch, db)

    unauthenticated = client.get("/api/v1/dashboard/summary")
    pending = client.get(
        "/api/v1/dashboard/summary",
        headers=_headers(pending_user.id),
    )

    assert unauthenticated.status_code == 401
    assert pending.status_code == 403
    db.execute.assert_not_called()


def test_dashboard_summary_queries_persisted_video_and_analysis_data():
    user = User(
        email=f"dashboard-{uuid4().hex}@example.com",
        password_hash="test-hash",
        first_name="Dashboard",
        role="monitoring_operator",
        is_active=True,
    )
    with SessionLocal() as db:
        db.add(user)
        db.flush()
        videos = [
            Video(
                uploaded_by=user.id,
                original_filename=f"dashboard-{index}.mp4",
                stored_filename=f"{uuid4().hex}.mp4",
                storage_key=f"{uuid4().hex}.mp4",
                content_type="video/mp4",
                file_size_bytes=5,
                sha256="a" * 64,
                status="uploaded",
            )
            for index in range(2)
        ]
        db.add_all(videos)
        db.flush()
        completed_job = AnalysisJob(
            video_id=videos[0].id,
            requested_by=user.id,
            status="completed",
            progress=100,
            result={
                "summary": {"candidate_count": 2},
                "candidates": [{}, {}],
                "frames": [],
            },
        )
        queued_job = AnalysisJob(
            video_id=videos[1].id,
            requested_by=user.id,
            status="queued",
        )
        db.add_all([completed_job, queued_job])
        db.commit()
        user_id = user.id
        job_ids = [completed_job.id, queued_job.id]

    try:
        response = client.get(
            "/api/v1/dashboard/summary",
            headers=_headers(user_id),
        )
    finally:
        with SessionLocal() as db:
            db.query(AnalysisJob).filter(AnalysisJob.id.in_(job_ids)).delete(
                synchronize_session=False
            )
            db.query(Video).filter(Video.uploaded_by == user_id).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id == user_id).delete(
                synchronize_session=False
            )
            db.commit()

    assert response.status_code == 200
    data = response.json()
    assert data["total_videos"] >= 2
    assert data["completed_analyses"] >= 1
    assert data["processing_analyses"] >= 1
    assert data["detected_candidates"] >= 2
    assert {item["analysis_id"] for item in data["recent_activity"]}.issuperset(
        {str(job_id) for job_id in job_ids}
    )
