from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CrashSense API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    # Video upload and local storage
    video_storage_dir: str = "storage/videos"
    max_video_upload_size_mb: int = 100

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "crashsense"
    database_user: str = "crashsense_app"
    database_password: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # Initial administrator bootstrap
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_first_name: str = "System"
    initial_admin_last_name: str = "Administrator"

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