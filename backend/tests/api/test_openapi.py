import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from main import create_application


def test_openapi_explains_event_queries(tmp_path: Path) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]["/api/events"]) == {"query"}
    operation = schema["paths"]["/api/events"]["query"]
    assert "starts_at" in operation["description"]
    assert "id" in operation["description"]
    model = schema["components"]["schemas"]["EventQuery"]
    fields = model["properties"]
    for name in ("from", "to", "category", "q", "limit", "offset", "event_ids"):
        assert fields[name]["description"]
    assert "timezone" in fields["from"]["description"]
    assert "ongoing" in fields["from"]["description"]
    assert "exclusive" in fields["to"]["description"].lower()
    assert "array" in fields["category"]["description"]
    assert "case-insensitive" in fields["q"]["description"]
    assert "title" in fields["q"]["description"]
    assert "after filtering" in fields["offset"]["description"]
    assert model["required"] == ["from"]
    assert fields["limit"]["minimum"] == 1
    assert fields["limit"]["maximum"] == 20
    assert fields["limit"]["default"] == 20
    assert fields["offset"]["minimum"] == 0
    assert fields["offset"]["default"] == 0
    category_schema = fields["category"]["anyOf"][0]
    assert category_schema["type"] == "array"
    assert category_schema["items"]["$ref"].endswith("/EventCategory")


def test_openapi_describes_event_responses_and_errors(tmp_path: Path) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        schema = client.get("/openapi.json").json()

    responses = schema["paths"]["/api/events"]["query"]["responses"]
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


def test_generated_reference_loads_without_database_io(tmp_path: Path) -> None:
    database_path = tmp_path / "missing-directory" / "events.sqlite3"
    with TestClient(create_application(database_path)) as client:
        response = client.get("/docs")
        schema = client.get("/openapi.json").json()

    assert response.status_code == 200
    assert "/openapi.json" in response.text
    health = schema["paths"]["/health"]["get"]
    assert "migrations" in health["description"]
    assert not database_path.parent.exists()


def test_query_openapi_body_reference_resolves(tmp_path: Path) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        schema = client.get("/openapi.json").json()
    assert schema["openapi"] == "3.2.0"
    operation = schema["paths"]["/api/events"]["query"]
    body = operation["requestBody"]
    assert body["required"] is True
    reference = body["content"]["application/json"]["schema"]["$ref"]
    model = schema
    for segment in reference.removeprefix("#/").split("/"):
        model = model[segment]
    assert set(model["required"]) == {"from"}
    id_schema = model["properties"]["event_ids"]
    assert id_schema["anyOf"][0]["items"]["format"] == "uuid"
    assert id_schema["anyOf"][1] == {"type": "null"}
    assert model["properties"]["category"]["anyOf"][0]["type"] == "array"
    assert model["properties"]["limit"]["maximum"] == 20


def test_swagger_is_the_only_reference_and_supports_query(
    tmp_path: Path,
) -> None:
    with TestClient(create_application(tmp_path / "events.sqlite3")) as client:
        assert client.get("/redoc").status_code == 404
        page = client.get("/docs").text
    match = re.search(r'"supportedSubmitMethods": (\[[^\]]+\])', page)
    assert match is not None
    assert json.loads(match.group(1)) == [
        "get",
        "put",
        "post",
        "delete",
        "options",
        "head",
        "patch",
        "trace",
        "query",
    ]
