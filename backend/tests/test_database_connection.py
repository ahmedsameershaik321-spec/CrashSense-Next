from sqlalchemy import text

from app.database import engine


def test_database_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_database_name():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database()")
        )
        assert result.scalar_one() == "crashsense"


def test_database_user():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_user")
        )
        assert result.scalar_one() == "crashsense_app"