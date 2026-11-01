
from app.core.security import (
    hash_password,
    verify_password,
    password_needs_rehash,
)


def test_password_hashing():
    password = "CrashSenseTest123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")


def test_correct_password_verification():
    password = "CrashSenseTest123!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_incorrect_password_verification():
    hashed = hash_password("CrashSenseTest123!")

    assert verify_password("WrongPassword123!", hashed) is False


def test_empty_password_verification():
    assert verify_password("", "invalid_hash") is False


def test_invalid_hash_verification():
    assert verify_password("SomePassword123!", "invalid_hash") is False


def test_password_hash_does_not_need_rehash():
    hashed = hash_password("CrashSenseTest123!")

    assert password_needs_rehash(hashed) is False
