
from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
)


def test_create_and_decode_access_token():
    token = create_access_token("test-user-123")

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "test-user-123"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_expired_token_is_rejected():
    token = create_access_token(
        "test-user-123",
        expires_delta=timedelta(seconds=-1),
    )

    assert decode_access_token(token) is None


def test_tampered_token_is_rejected():
    token = create_access_token("test-user-123")
    tampered_token = token[:-5] + "abcde"

    assert decode_access_token(tampered_token) is None


def test_invalid_token_is_rejected():
    assert decode_access_token("not.a.valid.token") is None


def test_empty_token_is_rejected():
    assert decode_access_token("") is None


def test_empty_subject_is_rejected():
    try:
        create_access_token("")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_token_with_different_secret_is_rejected(monkeypatch):
    from app.core import security

    token = create_access_token("test-user-123")

    monkeypatch.setattr(
        security.settings,
        "jwt_secret_key",
        "different-secret-for-testing",
    )

    assert decode_access_token(token) is None
