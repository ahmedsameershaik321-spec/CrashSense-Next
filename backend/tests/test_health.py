from unittest.mock import Mock

from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["application"] == "CrashSense API"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"


def test_health_endpoint_reports_database_unavailable():
    def unavailable_database():
        db = Mock()
        db.execute.side_effect = SQLAlchemyError("database unavailable")
        yield db

    app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable."