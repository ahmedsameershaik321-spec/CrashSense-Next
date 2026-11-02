from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


AnalysisStatus = Literal[
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
]


class AnalysisJobResponse(BaseModel):
    id: UUID
    video_id: UUID
    status: AnalysisStatus
    progress: int
    cancel_requested: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnalysisResultsResponse(BaseModel):
    job_id: UUID
    video_id: UUID
    summary: dict[str, Any]
    candidates: list[dict[str, Any]]
    frames: list[dict[str, Any]]
    frame_offset: int = 0
    total_frames: int


class AccidentCandidateResponse(BaseModel):
    candidate_id: str
    start_timestamp_seconds: float
    end_timestamp_seconds: float
    involved_track_ids: list[int]
    object_labels: list[str]
    confidence_score: float
    confidence_type: str
    verification_status: Literal["suspected", "verified_detection"]
    evidence_summary: str
    evidence_references: list[str]
    interaction_observations: int
    motion_events: int
