
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.schemas.user import (
    UserApprovalRequest,
    UserResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)


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


def _get_user_for_update(db: Session, user_id: UUID) -> User:
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def _lock_active_administrators(db: Session) -> None:
    db.scalars(
        select(User.id)
        .where(
            User.role == "administrator",
            User.is_active.is_(True),
        )
        .order_by(User.id)
        .with_for_update()
    ).all()


def _prevent_removing_last_admin(
    db: Session,
    user: User,
    *,
    role: str | None = None,
    is_active: bool | None = None,
) -> None:
    loses_admin_access = (
        user.role == "administrator"
        and user.is_active
        and (
            (role is not None and role != "administrator")
            or (is_active is False)
        )
    )
    if not loses_admin_access:
        return

    active_admins = db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.role == "administrator",
            User.is_active.is_(True),
        )
    )
    if active_admins <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active administrator cannot be deactivated or demoted.",
        )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: UUID,
    request: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Change the role of an already approved, active account."""
    _lock_active_administrators(db)
    user = _get_user_for_update(db, user_id)
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )
    if user.role == "pending" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active, approved accounts can have their role changed.",
        )
    if user.role == request.role:
        return user

    _prevent_removing_last_admin(db, user, role=request.role)
    user.role = request.role
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
)
def update_user_status(
    user_id: UUID,
    request: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Suspend or reactivate an approved account without changing its role."""
    _lock_active_administrators(db)
    user = _get_user_for_update(db, user_id)
    if user.role == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pending accounts must be approved before they can be activated.",
        )
    if user_id == current_admin.id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot suspend your own account.",
        )
    if user.is_active == request.is_active:
        return user
    _prevent_removing_last_admin(db, user, is_active=request.is_active)
    user.is_active = request.is_active
    db.commit()
    db.refresh(user)
    return user
