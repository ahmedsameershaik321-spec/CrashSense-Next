import pytest
from pydantic import ValidationError

from app.config import Settings


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
