from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.models.analysis_job import AnalysisJob
from app.models.user import User
from app.models.video import Video


client = TestClient(app)


def test_analysis_routes_are_in_openapi():
    schema = client.get("/openapi.json").json()

    assert "/api/v1/videos/{video_id}/analysis" in schema["paths"]
    assert "/api/v1/videos/analysis/{analysis_id}" in schema["paths"]
    assert "/api/v1/videos/analysis/{analysis_id}/candidates" in schema["paths"]
    assert "/api/v1/videos/analysis/{analysis_id}/frames" in schema["paths"]


@pytest.fixture
def video_storage(tmp_path, monkeypatch):
    storage = tmp_path / "videos"
    storage.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage))
    return storage


def create_test_user(role="monitoring_operator", is_active=True):
    user = User(
        email=f"analysis-api-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Analysis",
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


def create_test_video(user_id, storage_dir):
    storage_key = f"{uuid4().hex}.mp4"
    (storage_dir / storage_key).write_bytes(b"video")
    video = Video(
        uploaded_by=user_id,
        original_filename="road.mp4",
        stored_filename=storage_key,
        storage_key=storage_key,
        content_type="video/mp4",
        file_size_bytes=5,
        sha256="a" * 64,
        status="uploaded",
    )
    with SessionLocal() as db:
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id


def create_analysis_job(
    video_id,
    requested_by,
    status="queued",
    result=None,
    error_message=None,
):
    job = AnalysisJob(
        video_id=video_id,
        requested_by=requested_by,
        status=status,
        progress=100 if status == "completed" else 0,
        result=result,
        error_message=error_message,
    )
    with SessionLocal() as db:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


def test_analysis_endpoints_require_active_operator(video_storage):
    pending_user = create_test_user("pending", is_active=False)
    inactive_user = create_test_user("monitoring_operator", is_active=False)
    video_id = create_test_video(pending_user, video_storage)
    stream_url = f"/api/v1/videos/{video_id}/analysis"

    assert client.post(stream_url).status_code == 401
    assert client.post(stream_url, headers=auth_headers(pending_user)).status_code == 403
    assert client.post(stream_url, headers=auth_headers(inactive_user)).status_code == 403


def test_analysis_job_can_be_queued_and_status_checked(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)

    response = client.post(
        f"/api/v1/videos/{video_id}/analysis",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["progress"] == 0
    job_id = response.json()["id"]

    status_response = client.get(
        f"/api/v1/videos/analysis/{job_id}",
        headers=auth_headers(user_id),
    )

    assert status_response.status_code == 200
    assert status_response.json()["id"] == job_id
    assert status_response.json()["status"] == "queued"


def test_duplicate_active_analysis_is_rejected(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    url = f"/api/v1/videos/{video_id}/analysis"

    first = client.post(url, headers=auth_headers(user_id))
    second = client.post(url, headers=auth_headers(user_id))

    assert first.status_code == 202
    assert second.status_code == 409


def test_queued_analysis_can_be_cancelled(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    job_id = create_analysis_job(video_id, user_id)

    response = client.delete(
        f"/api/v1/videos/analysis/{job_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["completed_at"] is not None


def test_completed_analysis_results_candidates_and_frames_are_paginated(
    video_storage,
):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    candidate = {
        "candidate_id": "tracks:1:2",
        "start_timestamp_seconds": 1.0,
        "end_timestamp_seconds": 4.0,
        "involved_track_ids": [1, 2],
        "object_labels": ["car", "person"],
        "confidence_score": 0.6,
        "confidence_type": "heuristic_temporal_evidence_score",
        "verification_status": "suspected",
        "evidence_summary": "Review required.",
        "evidence_references": ["frame:5@1.000s"],
        "interaction_observations": 2,
        "motion_events": 1,
    }
    frames = [
        {"frame_index": index, "timestamp_seconds": float(index), "objects": []}
        for index in range(3)
    ]
    job_id = create_analysis_job(
        video_id,
        user_id,
        status="completed",
        result={
            "summary": {
                "frames_processed": 3,
                "detections_processed": 0,
                "candidate_count": 1,
                "model": "yolov8n.pt",
                "device": "cpu",
                "frame_interval_seconds": 1.0,
                "notice": "Heuristic visual evidence only.",
            },
            "candidates": [candidate],
            "frames": frames,
        },
    )
    headers = auth_headers(user_id)

    results = client.get(
        f"/api/v1/videos/analysis/{job_id}/results?offset=1&limit=1",
        headers=headers,
    )
    candidates = client.get(
        f"/api/v1/videos/analysis/{job_id}/candidates",
        headers=headers,
    )
    evidence = client.get(
        f"/api/v1/videos/analysis/{job_id}/frames?offset=1&limit=1",
        headers=headers,
    )

    assert results.status_code == 200
    assert results.json()["total_frames"] == 3
    assert results.json()["frames"][0]["frame_index"] == 1
    assert candidates.status_code == 200
    assert candidates.json()[0]["verification_status"] == "suspected"
    assert evidence.status_code == 200
    assert evidence.json()[0]["timestamp_seconds"] == 1.0


def test_analysis_results_are_not_available_before_completion(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    job_id = create_analysis_job(video_id, user_id)

    response = client.get(
        f"/api/v1/videos/analysis/{job_id}/results",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 409


def test_failed_analysis_status_includes_error_message(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    error_message = "Could not load configured YOLO weights: missing.pt."
    job_id = create_analysis_job(
        video_id,
        user_id,
        status="failed",
        error_message=error_message,
    )

    response = client.get(
        f"/api/v1/videos/analysis/{job_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == error_message


def test_start_analysis_for_missing_video_returns_404(video_storage):
    user_id = create_test_user()

    response = client.post(
        f"/api/v1/videos/{uuid4()}/analysis",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 404


def test_video_cannot_be_deleted_while_analysis_is_queued(video_storage):
    user_id = create_test_user()
    video_id = create_test_video(user_id, video_storage)
    create_analysis_job(video_id, user_id)

    response = client.delete(
        f"/api/v1/videos/{video_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 409
