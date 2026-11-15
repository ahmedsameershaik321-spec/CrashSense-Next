from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CrashSense API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # Video upload and local storage
    video_storage_dir: str = "storage/videos"
    max_video_upload_size_mb: int = Field(default=100, gt=0, le=4096)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    detection_model_weights: str = Field(default="yolov8n.pt", min_length=1)
    detection_device: str = "auto"
    accident_classifier_weights: str | None = None
    accident_classifier_frame_interval_seconds: float = Field(
        default=0.1,
        gt=0,
        le=1,
    )
    accident_classifier_normal_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    accident_classifier_accident_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    detection_confidence_threshold: float = Field(default=0.25, ge=0, le=1)
    detection_iou_threshold: float = Field(default=0.45, ge=0, le=1)
    detection_image_size: int = Field(default=640, ge=32, le=2048)
    detection_frame_interval_seconds: float = Field(default=1.0, gt=0)
    detection_max_frame_dimension: int = Field(default=1280, gt=0)
    detection_min_candidate_observations: int = Field(default=2, ge=1)
    detection_min_verified_observations: int = Field(default=4, ge=1)
    detection_min_verified_duration_seconds: float = Field(default=2.0, gt=0)
    detection_min_motion_events: int = Field(default=2, ge=1)
    detection_interaction_distance_ratio: float = Field(default=0.08, gt=0, le=1)
    detection_min_speed_pixels_per_second: float = Field(default=12.0, gt=0)
    detection_stop_speed_ratio: float = Field(default=0.2, ge=0, le=1)
    detection_worker_poll_seconds: float = Field(default=1.0, gt=0)
    detection_stale_job_minutes: int = Field(default=60, gt=0)
    osm_overpass_url: str = "https://overpass-api.de/api/interpreter"
    osm_overpass_timeout_seconds: float = Field(default=10.0, gt=0, le=30)

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "crashsense"
    database_user: str = "crashsense_app"
    database_password: str = Field(min_length=1)
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # Initial administrator bootstrap
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_first_name: str = "System"
    initial_admin_last_name: str = "Administrator"

    @field_validator("database_password", "jwt_secret_key")
    @classmethod
    def reject_example_secrets(cls, value: str) -> str:
        if value.strip().lower().startswith(
            ("replace_with_", "change_me", "your_secret")
        ):
            raise ValueError("Replace the example credential with a unique secret.")
        return value

    @field_validator("accident_classifier_weights", mode="before")
    @classmethod
    def normalize_optional_classifier_weights(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "accident_classifier_normal_threshold",
        "accident_classifier_accident_threshold",
        mode="before",
    )
    @classmethod
    def normalize_optional_classifier_thresholds(
        cls,
        value: float | str | None,
    ) -> float | str | None:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized = [origin.strip().rstrip("/") for origin in origins]
        for origin in normalized:
            parsed = urlsplit(origin)
            if (
                not origin
                or origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError(
                    "CORS entries must be explicit HTTP(S) origins without paths."
                )
            try:
                parsed.port
            except ValueError as exc:
                raise ValueError("A CORS origin contains an invalid port.") from exc
        return normalized

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() == "production" and self.debug:
            raise ValueError("DEBUG must be false in production.")
        if self.environment.lower() == "production" and len(self.database_password) < 16:
            raise ValueError("Production database passwords must be at least 16 characters.")
        if (
            self.accident_classifier_normal_threshold is not None
            and self.accident_classifier_accident_threshold is not None
            and self.accident_classifier_normal_threshold
            >= self.accident_classifier_accident_threshold
        ):
            raise ValueError(
                "The classifier normal threshold must be lower than its accident threshold."
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()