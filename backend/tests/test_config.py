import pytest
from pydantic import ValidationError

from app.config import Settings
from app.database import build_database_url


def settings(**overrides) -> Settings:
    values = {
        "database_password": "local-test-password",
        "jwt_secret_key": "x" * 40,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_disable_debug_and_require_strong_jwt_secret():
    with pytest.raises(ValidationError):
        settings(environment="production", debug=True)

    with pytest.raises(ValidationError):
        Settings(
            database_password="local-test-password",
            jwt_secret_key="short",
        )

    with pytest.raises(ValidationError):
        settings(environment="production", database_password="short")

    with pytest.raises(ValidationError):
        Settings(
            database_password="replace_with_a_local_database_password",
            jwt_secret_key="x" * 40,
        )


def test_database_url_supports_managed_postgres_and_validates_credentials():
    connection_url = "postgresql://crashsense:p%40ssword-long-enough@db.example/crashsense"
    configured = settings(
        environment="production",
        debug=False,
        database_password="",
        database_url=connection_url,
    )
    engine_url = build_database_url(configured)
    assert engine_url.drivername == "postgresql+psycopg"
    assert engine_url.host == "db.example"
    assert engine_url.password == "p@ssword-long-enough"

    with pytest.raises(ValidationError):
        settings(database_password="", database_url="mysql://db.example/crashsense")

    with pytest.raises(ValidationError):
        settings(
            environment="production",
            database_password="",
            database_url="postgresql://crashsense:short@db.example/crashsense",
        )


def test_database_url_falls_back_to_separate_local_settings():
    engine_url = build_database_url(settings())
    assert engine_url.drivername == "postgresql+psycopg"
    assert engine_url.host == "localhost"
    assert engine_url.database == "crashsense"


def test_cors_origins_must_be_explicit_http_origins():
    with pytest.raises(ValidationError):
        settings(cors_allowed_origins=["*"])

    with pytest.raises(ValidationError):
        settings(cors_allowed_origins=["https://frontend.example/path"])

    configured = settings(
        cors_allowed_origins=["https://frontend.example/"],
    )
    assert configured.cors_allowed_origins == ["https://frontend.example"]


def test_detection_image_size_and_review_duration_are_validated():
    with pytest.raises(ValidationError):
        settings(detection_image_size=16)

    with pytest.raises(ValidationError):
        settings(detection_min_verified_duration_seconds=0)

    configured = settings(
        detection_image_size=512,
        detection_min_verified_duration_seconds=2.5,
    )
    assert configured.detection_image_size == 512
    assert configured.detection_min_verified_duration_seconds == 2.5


def test_current_default_detector_uses_yolo26_nano():
    assert settings().detection_model_weights == "yolo26n.pt"


def test_accident_classifier_settings_are_optional_and_bounded():
    empty_values = settings(
        accident_classifier_weights="",
        accident_classifier_normal_threshold="",
        accident_classifier_accident_threshold="",
    )
    assert empty_values.accident_classifier_weights is None
    assert empty_values.accident_classifier_normal_threshold is None
    assert empty_values.accident_classifier_accident_threshold is None

    configured = settings(
        accident_classifier_weights="  local-model.pth  ",
        accident_classifier_frame_interval_seconds=0.2,
        accident_classifier_normal_threshold=0.2,
        accident_classifier_accident_threshold=0.8,
    )
    assert configured.accident_classifier_weights == "local-model.pth"
    assert configured.accident_classifier_frame_interval_seconds == 0.2

    with pytest.raises(ValidationError):
        settings(accident_classifier_frame_interval_seconds=0)

    with pytest.raises(ValidationError):
        settings(
            accident_classifier_normal_threshold=0.8,
            accident_classifier_accident_threshold=0.2,
        )
