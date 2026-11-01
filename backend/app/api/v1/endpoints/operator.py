
from fastapi import APIRouter, Depends

from app.dependencies.auth import require_operator
from app.models.user import User
from app.schemas.user import UserResponse


router = APIRouter(
    prefix="/operator",
    tags=["Operator"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_operator_profile(
    current_user: User = Depends(require_operator),
):
    """Return the authenticated operator's profile."""

    return current_user
