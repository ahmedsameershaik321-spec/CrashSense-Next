from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_operator
from app.models.analysis_job import AnalysisJob
from app.models.user import User
from app.models.video import Video
from app.schemas.dashboard import (
    DashboardActivityResponse,
    DashboardSummaryResponse,
)
from app.services.analysis_jobs import analysis_job_worker


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _candidate_count_expression():
    return func.coalesce(
        AnalysisJob.result["summary"]["candidate_count"].as_integer(),
        0,
    )


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return authorized dashboard metrics and the latest analysis activity."""
    completed_analyses = (
        select(func.count())
        .select_from(AnalysisJob)
        .where(AnalysisJob.status == "completed")
        .scalar_subquery()
    )
    processing_analyses = (
        select(func.count())
        .select_from(AnalysisJob)
        .where(AnalysisJob.status.in_(("queued", "processing")))
        .scalar_subquery()
    )
    detected_candidates = (
        select(func.coalesce(func.sum(_candidate_count_expression()), 0))
        .where(AnalysisJob.status == "completed")
        .scalar_subquery()
    )
    totals = db.execute(
        select(
            select(func.count()).select_from(Video).scalar_subquery().label(
                "total_videos"
            ),
            completed_analyses.label("completed_analyses"),
            processing_analyses.label("processing_analyses"),
            detected_candidates.label("detected_candidates"),
        )
    ).one()

    activity_rows = db.execute(
        select(
            AnalysisJob.id,
            AnalysisJob.video_id,
            Video.original_filename,
            AnalysisJob.status,
            AnalysisJob.progress,
            _candidate_count_expression().label("candidate_count"),
            AnalysisJob.created_at,
        )
        .join(Video, Video.id == AnalysisJob.video_id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .limit(8)
    ).all()

    return DashboardSummaryResponse(
        total_videos=totals.total_videos,
        completed_analyses=totals.completed_analyses,
        processing_analyses=totals.processing_analyses,
        detected_candidates=totals.detected_candidates,
        analysis_worker_running=analysis_job_worker.is_running,
        recent_activity=[
            DashboardActivityResponse(
                analysis_id=row.id,
                video_id=row.video_id,
                video_name=row.original_filename,
                status=row.status,
                progress=row.progress,
                candidate_count=row.candidate_count,
                created_at=row.created_at,
            )
            for row in activity_rows
        ],
    )
