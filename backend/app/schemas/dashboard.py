from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.analysis import AnalysisStatus


class DashboardActivityResponse(BaseModel):
    analysis_id: UUID
    video_id: UUID
    video_name: str
    status: AnalysisStatus
    progress: int
    candidate_count: int
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    total_videos: int
    completed_analyses: int
    processing_analyses: int
    detected_candidates: int
    analysis_worker_running: bool
    recent_activity: list[DashboardActivityResponse]
