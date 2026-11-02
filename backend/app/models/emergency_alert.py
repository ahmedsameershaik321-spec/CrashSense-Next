import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmergencyAlertAudit(Base):
    __tablename__ = "emergency_alert_audit"

    __table_args__ = (
        UniqueConstraint(
            "analysis_job_id",
            "candidate_id",
            name="uq_emergency_alert_audit_job_candidate",
        ),
        CheckConstraint(
            "delivery_status = 'not_sent'",
            name="ck_emergency_alert_audit_never_dispatched",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delivery_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_sent",
        server_default=text("'not_sent'"),
    )
    delivery_result: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="External delivery is disabled; this is an audit-only record.",
        server_default=text(
            "'External delivery is disabled; this is an audit-only record.'"
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

