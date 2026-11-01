from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VideoResponse(BaseModel):
    id: UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    sha256: str
    status: str
    duration_seconds: float | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)