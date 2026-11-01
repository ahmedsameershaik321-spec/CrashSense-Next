
from app import database
from app.database import get_db


def test_get_db_returns_session():
    generator = get_db()
    db = next(generator)

    try:
        assert db is not None
        assert db.is_active
    finally:
        generator.close()


def test_get_db_closes_session(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake_session = FakeSession()

    monkeypatch.setattr(
        database,
        "SessionLocal",
        lambda: fake_session,
    )

    generator = get_db()
    db = next(generator)

    assert db is fake_session
    assert fake_session.closed is False

    generator.close()

    assert fake_session.closed is True
