import pytest

from app import bootstrap_admin


def test_bootstrap_refuses_example_administrator_password(monkeypatch):
    monkeypatch.setattr(
        bootstrap_admin.settings,
        "initial_admin_email",
        "admin@example.com",
    )
    monkeypatch.setattr(
        bootstrap_admin.settings,
        "initial_admin_password",
        "replace_with_a_strong_password",
    )

    with pytest.raises(RuntimeError, match="Replace the example"):
        bootstrap_admin.bootstrap_admin()
