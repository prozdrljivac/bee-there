from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_application


def test_openapi_explains_event_queries(tmp_path: Path) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/events"]["get"]
    assert "starts_at" in operation["description"]
    assert "id" in operation["description"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    for name in ("from", "to", "category", "q", "limit", "offset"):
        assert parameters[name]["description"]
    assert "timezone" in parameters["from"]["description"]
    assert "ongoing" in parameters["from"]["description"]
    assert "exclusive" in parameters["to"]["description"]
    assert "Repeat" in parameters["category"]["description"]
    assert "case-insensitive" in parameters["q"]["description"]
    assert "title" in parameters["q"]["description"]
    assert "after filtering" in parameters["offset"]["description"]
    assert parameters["from"]["required"] is True
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 20
    assert parameters["limit"]["schema"]["default"] == 20
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["default"] == 0
    category_schema = parameters["category"]["schema"]["anyOf"][0]
    assert category_schema["type"] == "array"
    assert category_schema["items"]["$ref"].endswith("/EventCategory")


def test_openapi_describes_event_responses_and_errors(tmp_path: Path) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        schema = client.get("/openapi.json").json()

    responses = schema["paths"]["/api/events"]["get"]["responses"]
    success = responses["200"]["content"]["application/json"]["schema"]
    assert success["type"] == "array"
    assert success["items"]["$ref"].endswith("/EventResponse")
    event = schema["components"]["schemas"]["EventResponse"]
    for field in event["properties"].values():
        assert field["description"]
    assert "empty array" in responses["200"]["description"]

    validation = responses["422"]["content"]["application/json"]
    variants = validation["schema"]["anyOf"]
    assert {item["$ref"].rsplit("/", 1)[1] for item in variants} == {
        "QueryValidationError",
        "ErrorResponse",
    }
    assert validation["examples"]["invalid_range"]["value"] == {
        "detail": "to must be after from"
    }
    assert isinstance(
        validation["examples"]["invalid_query"]["value"]["detail"], list
    )
    server_error = responses["500"]["content"]["application/json"]
    assert server_error["schema"]["$ref"].endswith("/ErrorResponse")
    assert server_error["examples"]["missing_source"]["value"] == {
        "detail": "event source is not configured"
    }


@pytest.mark.parametrize("path", ("/docs", "/redoc"))
def test_generated_reference_loads_without_database_io(
    tmp_path: Path, path: str
) -> None:
    database_path = tmp_path / "missing-directory" / "events.sqlite3"
    with TestClient(create_application(database_path)) as client:
        response = client.get(path)
        schema = client.get("/openapi.json").json()

    assert response.status_code == 200
    assert "/openapi.json" in response.text
    health = schema["paths"]["/health"]["get"]
    assert "migrations" in health["description"]
    assert not database_path.parent.exists()
