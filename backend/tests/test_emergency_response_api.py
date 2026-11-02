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
from app.schemas.response import NearbyResource


client = TestClient(app)


@pytest.fixture
def video_storage(tmp_path, monkeypatch):
    storage = tmp_path / "videos"
    storage.mkdir()
    monkeypatch.setattr(settings, "video_storage_dir", str(storage))
    return storage


def create_user(role: str, is_active: bool = True):
    user = User(
        email=f"response-{uuid4().hex}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Response",
        role=role,
        is_active=is_active,
        is_email_verified=True,
    )
    with SessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def headers(user_id):
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def create_video(user_id, storage_dir):
    storage_key = f"{uuid4().hex}.mp4"
    (storage_dir / storage_key).write_bytes(b"video")
    video = Video(
        uploaded_by=user_id,
        original_filename="north-road.mp4",
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


def test_camera_location_is_admin_managed_and_operator_readable(video_storage):
    admin_id = create_user("administrator")
    operator_id = create_user("monitoring_operator")
    pending_id = create_user("pending", is_active=False)
    video_id = create_video(admin_id, video_storage)
    camera_payload = {
        "name": f"North intersection {uuid4().hex}",
        "latitude": 51.5072,
        "longitude": -0.1276,
        "address": "Westminster, London",
    }

    assert client.get("/api/v1/cameras").status_code == 401
    assert client.get(
        "/api/v1/cameras",
        headers=headers(pending_id),
    ).status_code == 403
    assert client.post(
        "/api/v1/cameras",
        json=camera_payload,
        headers=headers(operator_id),
    ).status_code == 403

    created = client.post(
        "/api/v1/cameras",
        json=camera_payload,
        headers=headers(admin_id),
    )
    assert created.status_code == 201
    camera = created.json()
    assert camera["name"] == camera_payload["name"]
    assert camera["latitude"] == camera_payload["latitude"]

    assigned = client.put(
        f"/api/v1/videos/{video_id}/camera",
        json={"camera_id": camera["id"]},
        headers=headers(admin_id),
    )
    assert assigned.status_code == 200
    assert assigned.json()["source"] == "registered_camera"
    assert assigned.json()["camera"]["id"] == camera["id"]

    location = client.get(
        f"/api/v1/videos/{video_id}/location",
        headers=headers(operator_id),
    )
    assert location.status_code == 200
    assert location.json()["camera"]["longitude"] == camera_payload["longitude"]

    invalid = client.post(
        "/api/v1/cameras",
        json={**camera_payload, "name": "Invalid camera", "latitude": 91},
        headers=headers(admin_id),
    )
    assert invalid.status_code == 422


def test_nearby_resources_use_assigned_camera_and_return_real_sorted_records(
    video_storage,
    monkeypatch,
):
    admin_id = create_user("administrator")
    video_id = create_video(admin_id, video_storage)
    camera = client.post(
        "/api/v1/cameras",
        json={
            "name": f"Resource lookup camera {uuid4().hex}",
            "latitude": 40.0,
            "longitude": -73.0,
        },
        headers=headers(admin_id),
    ).json()
    client.put(
        f"/api/v1/videos/{video_id}/camera",
        json={"camera_id": camera["id"]},
        headers=headers(admin_id),
    )
    nearby = [
        NearbyResource(
            osm_type="way",
            osm_id=1001,
            resource_type="ambulance_station",
            name="Mapped ambulance station",
            latitude=40.0005,
            longitude=-73.0,
            distance_meters=55.6,
            address=None,
        ),
        NearbyResource(
            osm_type="node",
            osm_id=1002,
            resource_type="hospital",
            name="Mapped hospital",
            latitude=40.001,
            longitude=-73.0,
            distance_meters=111.2,
            address="Main Street",
        ),
    ]
    monkeypatch.setattr(
        "app.api.v1.endpoints.videos.find_nearby_resources",
        lambda latitude, longitude, radius: nearby,
    )
    response = client.get(
        f"/api/v1/videos/{video_id}/resources?radius_meters=2000",
        headers=headers(admin_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "OpenStreetMap"
    assert payload["radius_meters"] == 2000
    assert payload["resources"][0]["name"] == "Mapped ambulance station"
    assert payload["resources"][1]["name"] == "Mapped hospital"


def test_missing_camera_and_osm_failure_are_explicit(video_storage, monkeypatch):
    operator_id = create_user("monitoring_operator")
    video_id = create_video(operator_id, video_storage)
    no_location = client.get(
        f"/api/v1/videos/{video_id}/resources",
        headers=headers(operator_id),
    )
    assert no_location.status_code == 409

    camera = client.post(
        "/api/v1/cameras",
        json={
            "name": f"Unavailable OSM camera {uuid4().hex}",
            "latitude": 40,
            "longitude": -73,
        },
        headers=headers(create_user("administrator")),
    ).json()
    client.put(
        f"/api/v1/videos/{video_id}/camera",
        json={"camera_id": camera["id"]},
        headers=headers(create_user("administrator")),
    )

    def fail_lookup(*_args):
        from app.services.nearby_resources import ResourceLookupError

        raise ResourceLookupError("offline")

    monkeypatch.setattr(
        "app.api.v1.endpoints.videos.find_nearby_resources",
        fail_lookup,
    )
    failed = client.get(
        f"/api/v1/videos/{video_id}/resources",
        headers=headers(operator_id),
    )
    assert failed.status_code == 503
    assert "temporarily unavailable" in failed.json()["detail"]


def test_alert_endpoint_only_creates_idempotent_not_sent_audit_record(video_storage):
    operator_id = create_user("monitoring_operator")
    video_id = create_video(operator_id, video_storage)
    candidate = {
        "candidate_id": "tracks:1:2:episode:1",
        "start_timestamp_seconds": 1.0,
        "end_timestamp_seconds": 2.0,
        "involved_track_ids": [1, 2],
        "object_labels": ["car"],
        "confidence_score": 0.6,
        "confidence_type": "heuristic_temporal_evidence_score",
        "verification_status": "suspected",
        "evidence_summary": "Review required.",
        "evidence_references": [],
        "interaction_observations": 2,
        "motion_events": 1,
    }
    job = AnalysisJob(
        video_id=video_id,
        requested_by=operator_id,
        status="completed",
        progress=100,
        result={"summary": {}, "candidates": [candidate], "frames": []},
    )
    with SessionLocal() as db:
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    url = f"/api/v1/videos/analysis/{job_id}/alerts"
    payload = {
        "candidate_id": candidate["candidate_id"],
        "acknowledge_not_sent": True,
    }
    created = client.post(url, json=payload, headers=headers(operator_id))
    replay = client.post(url, json=payload, headers=headers(operator_id))

    assert created.status_code == 201
    assert created.json()["delivery_status"] == "not_sent"
    assert "disabled" in created.json()["delivery_result"]
    assert replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    assert client.get(url, headers=headers(operator_id)).json() == [created.json()]

    unauthorized = client.post(url, json=payload)
    assert unauthorized.status_code == 401
    unknown_candidate = client.post(
        url,
        json={"candidate_id": "not-a-candidate", "acknowledge_not_sent": True},
        headers=headers(operator_id),
    )
    assert unknown_candidate.status_code == 404
