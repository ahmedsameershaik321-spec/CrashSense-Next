from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Camera name cannot be blank.")
        return normalized

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CameraResponse(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    address: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoCameraAssignment(BaseModel):
    camera_id: UUID | None


class VideoLocationResponse(BaseModel):
    video_id: UUID
    source: Literal["registered_camera", "unavailable"]
    camera: CameraResponse | None


class NearbyResource(BaseModel):
    osm_type: Literal["node", "way", "relation"]
    osm_id: int
    resource_type: Literal[
        "hospital",
        "clinic",
        "ambulance_station",
        "fire_station",
    ]
    name: str
    latitude: float
    longitude: float
    distance_meters: float
    address: str | None


class NearbyResourcesResponse(BaseModel):
    video_id: UUID
    source: Literal["OpenStreetMap"]
    source_url: str
    attribution: str
    center_latitude: float
    center_longitude: float
    radius_meters: int
    resources: list[NearbyResource]


class EmergencyAlertCreate(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=255)
    acknowledge_not_sent: Literal[True]


class EmergencyAlertResponse(BaseModel):
    id: UUID
    analysis_job_id: UUID
    candidate_id: str
    delivery_status: Literal["not_sent"]
    delivery_result: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

