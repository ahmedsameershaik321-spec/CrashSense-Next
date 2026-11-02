from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_admin, require_operator
from app.models.camera import Camera
from app.models.user import User
from app.schemas.response import CameraCreate, CameraResponse


router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=list[CameraResponse])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    return db.scalars(
        select(Camera).where(Camera.is_active.is_(True)).order_by(Camera.name)
    ).all()


@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_camera(
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    camera = Camera(
        name=camera_data.name,
        latitude=camera_data.latitude,
        longitude=camera_data.longitude,
        address=camera_data.address,
        registered_by=current_admin.id,
    )
    db.add(camera)
    try:
        db.commit()
        db.refresh(camera)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A camera with this name is already registered.",
        ) from exc
    return camera

