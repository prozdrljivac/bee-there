from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from infrastructure.migrations import upgrade_database
from main import create_application
from modules.events import EventDraft
from modules.events.sqlite import SQLiteEventRepository
from modules.sources import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository


def test_application_composes_the_events_api(tmp_path: Path) -> None:
    database_path = tmp_path / "database.sqlite3"
    upgrade_database(database_path)
    source_id = UUID("019a57c0-8800-7000-8000-000000000010")
    sources = SQLiteSourceRepository(
        database_path,
        id_factory=lambda: source_id,
    )
    sources.create(
        SourceDraft(
            name="Cultural Station",
            base_url="https://example.com",
        )
    )
    SQLiteEventRepository(database_path).upsert(
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            source_id=source_id,
            source_url="https://example.com/events/jazz-night",
        )
    )

    with TestClient(create_application(database_path)) as client:
        response = client.get(
            "/api/events",
            params={"from": "2026-11-01T00:00:00+00:00"},
        )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Jazz Night"
    assert response.json()[0]["source_name"] == "Cultural Station"
