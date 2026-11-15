from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    event_state: Literal["suspected", "needs_review"] = "suspected"
    accident_category: Literal[
        "VEHICLE_TO_VEHICLE",
        "VEHICLE_TO_OBJECT",
        "ROLLOVER",
        "MULTI_VEHICLE",
        "PEDESTRIAN_RELATED",
        "OTHER",
        "UNKNOWN",
    ] = "UNKNOWN"
    classification_confidence: float | None = None
    classification_reasoning: str = (
        "Accident category is unavailable from the current detection evidence."
    )
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"] = "UNKNOWN"
    severity_confidence: float | None = None
    severity_reasoning_factors: list[str] = Field(default_factory=list)
    severity_missing_information: list[str] = Field(default_factory=list)
    human_review_required: bool = True
