"""add cameras, nearby resource support, and no-send alert audit

Revision ID: 72a31f4c9d10
Revises: 957d9e36a42f
Create Date: 2026-11-02 14:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "72a31f4c9d10"
down_revision: Union[str, Sequence[str], None] = "957d9e36a42f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("registered_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_cameras_valid_latitude",
        ),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_cameras_valid_longitude",
        ),
        sa.ForeignKeyConstraint(
            ["registered_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_cameras_active", "cameras", ["is_active"])

    op.add_column(
        "videos",
        sa.Column("camera_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_videos_camera_id_cameras",
        "videos",
        "cameras",
        ["camera_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_videos_camera_id", "videos", ["camera_id"])

    op.create_table(
        "emergency_alert_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            server_default=sa.text("'not_sent'"),
            nullable=False,
        ),
        sa.Column(
            "delivery_result",
            sa.String(length=500),
            server_default=sa.text(
                "'External delivery is disabled; this is an audit-only record.'"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "delivery_status = 'not_sent'",
            name="ck_emergency_alert_audit_never_dispatched",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_job_id"],
            ["video_analysis_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_job_id",
            "candidate_id",
            name="uq_emergency_alert_audit_job_candidate",
        ),
    )


def downgrade() -> None:
    op.drop_table("emergency_alert_audit")
    op.drop_index("ix_videos_camera_id", table_name="videos")
    op.drop_constraint(
        "fk_videos_camera_id_cameras",
        "videos",
        type_="foreignkey",
    )
    op.drop_column("videos", "camera_id")
    op.drop_index("ix_cameras_active", table_name="cameras")
    op.drop_table("cameras")

