
from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT and retrieve the current database user."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    payload = decode_access_token(credentials.credentials)

    if payload is None:
        raise credentials_exception

    subject = payload.get("sub")

    try:
        user_id = UUID(subject)
    except (ValueError, TypeError, AttributeError):
        raise credentials_exception

    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception

    return user


def get_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Reject accounts that are not active."""

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Contact an administrator.",
        )

    return current_user


def require_roles(*allowed_roles: str) -> Callable:
    """Create a dependency restricting access to specified roles."""

    if not allowed_roles:
        raise ValueError("At least one allowed role must be specified.")

    valid_roles = {
        "pending",
        "monitoring_operator",
        "administrator",
    }

    if not set(allowed_roles).issubset(valid_roles):
        raise ValueError("One or more invalid roles were specified.")

    def role_checker(
        current_user: User = Depends(get_active_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )

        return current_user

    return role_checker


require_operator = require_roles(
    "monitoring_operator",
    "administrator",
)

require_admin = require_roles("administrator")
