
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str | None
    role: str
    is_active: bool
    is_email_verified: bool
    approved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserApprovalRequest(BaseModel):
    role: Literal["monitoring_operator", "administrator"]


class UserRoleUpdateRequest(BaseModel):
    role: Literal["monitoring_operator", "administrator"]


class UserStatusUpdateRequest(BaseModel):
    is_active: bool
