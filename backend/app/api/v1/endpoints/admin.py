
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.user import UserApprovalRequest, UserResponse


router = APIRouter(
    prefix="/admin",
    tags=["Administrator"],
)


@router.get(
    "/pending-users",
    response_model=list[UserResponse],
)
def get_pending_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """List accounts waiting for administrator approval."""

    statement = (
        select(User)
        .where(
            User.role == "pending",
            User.is_active.is_(False),
        )
        .order_by(User.created_at.asc())
    )

    return db.scalars(statement).all()


@router.get(
    "/users",
    response_model=list[UserResponse],
)
def get_all_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List registered users with pagination."""

    statement = (
        select(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return db.scalars(statement).all()


@router.patch(
    "/users/{user_id}/approve",
    response_model=UserResponse,
)
def approve_user(
    user_id: UUID,
    approval: UserApprovalRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Approve a pending account and assign its operational role."""

    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot approve your own account.",
        )

    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if user.role != "pending" or user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is not awaiting approval.",
        )

    user.role = approval.role
    user.is_active = True
    user.approved_by = current_admin.id
    user.approved_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user
