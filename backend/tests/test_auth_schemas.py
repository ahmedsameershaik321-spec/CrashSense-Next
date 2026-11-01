
import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, LoginRequest
from app.schemas.user import UserApprovalRequest


def test_valid_registration():
    user = RegisterRequest(
        email="TEST@example.com",
        password="CrashSenseSecure123!",
        first_name="Sameer",
    )

    assert user.email == "TEST@example.com"
    assert user.first_name == "Sameer"


def test_registration_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="test@example.com",
            password="short",
            first_name="Test",
        )


def test_registration_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="invalid-email",
            password="CrashSenseSecure123!",
            first_name="Test",
        )


def test_registration_rejects_empty_first_name():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="test@example.com",
            password="CrashSenseSecure123!",
            first_name="",
        )


def test_login_schema():
    credentials = LoginRequest(
        email="test@example.com",
        password="password123",
    )

    assert credentials.email == "test@example.com"


def test_registration_does_not_accept_role():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="test@example.com",
            password="CrashSenseSecure123!",
            first_name="Test",
            role="administrator",
        )


def test_approval_schema():
    approval = UserApprovalRequest(role="monitoring_operator")

    assert approval.role == "monitoring_operator"

def test_approval_accepts_operator_role():
    from app.schemas.user import UserApprovalRequest

    request = UserApprovalRequest(
        role="monitoring_operator"
    )

    assert request.role == "monitoring_operator"


def test_approval_accepts_admin_role():
    from app.schemas.user import UserApprovalRequest

    request = UserApprovalRequest(
        role="administrator"
    )

    assert request.role == "administrator"


def test_approval_rejects_pending_role():
    from pydantic import ValidationError
    from app.schemas.user import UserApprovalRequest

    with pytest.raises(ValidationError):
        UserApprovalRequest(role="pending")


def test_approval_rejects_invalid_role():
    from pydantic import ValidationError
    from app.schemas.user import UserApprovalRequest

    with pytest.raises(ValidationError):
        UserApprovalRequest(role="superuser")
