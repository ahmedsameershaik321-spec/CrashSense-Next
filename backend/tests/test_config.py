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
