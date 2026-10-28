from pathlib import Path

from fastapi.testclient import TestClient

from main import create_application


def test_health_reports_a_running_application_without_database_io(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "missing-directory" / "database.sqlite3"

    with TestClient(create_application(database_path)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not database_path.parent.exists()
