
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.dependencies.auth import (
    get_current_user,
    get_active_user,
    require_roles,
    require_operator,
    require_admin,
)


def make_user(
    role="pending",
    is_active=True,
):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        is_active=is_active,
    )


def test_missing_token_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=None, db=None)

    assert exc.value.status_code == 401


def test_inactive_user_rejected():
    user = make_user(is_active=False)

    with pytest.raises(HTTPException) as exc:
        get_active_user(current_user=user)

    assert exc.value.status_code == 403


def test_active_user_allowed():
    user = make_user(is_active=True)

    result = get_active_user(current_user=user)

    assert result is user


def test_pending_user_allowed_for_pending_role():
    user = make_user(role="pending")

    checker = require_roles("pending")
    result = checker(current_user=user)

    assert result is user


def test_pending_user_rejected_from_operator_access():
    user = make_user(role="pending")

    with pytest.raises(HTTPException) as exc:
        require_operator(current_user=user)

    assert exc.value.status_code == 403


def test_operator_allowed_operator_access():
    user = make_user(role="monitoring_operator")

    result = require_operator(current_user=user)

    assert result is user


def test_operator_rejected_admin_access():
    user = make_user(role="monitoring_operator")

    with pytest.raises(HTTPException) as exc:
        require_admin(current_user=user)

    assert exc.value.status_code == 403


def test_admin_allowed_admin_access():
    user = make_user(role="administrator")

    result = require_admin(current_user=user)

    assert result is user


def test_invalid_role_configuration_rejected():
    with pytest.raises(ValueError):
        require_roles("superuser")


def test_empty_role_configuration_rejected():
    with pytest.raises(ValueError):
        require_roles()
