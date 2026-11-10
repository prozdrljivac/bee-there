import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infrastructure.migrations import upgrade_database
from ingest import run_moj_novi_sad_ingestion
from main import create_application
from modules.sources import PersistenceError

FIXTURES = Path(__file__).parent / "fixtures" / "moj_novi_sad"


class FixturePageClient:
    def __init__(self) -> None:
        self._pages = {
            "https://www.mojnovisad.com/desavanja/": (
                FIXTURES / "listing.html"
            ).read_text(encoding="utf-8"),
            "https://www.mojnovisad.com/navigator/jazz-night/": (
                FIXTURES / "detail.html"
            ).read_text(encoding="utf-8"),
        }

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_ingestion_requires_migrations_without_creating_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "unmigrated.sqlite3"

    with pytest.raises(PersistenceError):
        run_moj_novi_sad_ingestion(database_path, FixturePageClient())

    with closing(sqlite3.connect(database_path)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == []


def test_ingests_moj_novi_sad_and_serves_the_event(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database.sqlite3"
    upgrade_database(database_path)

    result = run_moj_novi_sad_ingestion(database_path, FixturePageClient())

    assert result.discovered_count == 1
    assert result.stored_count == 1
    assert result.failed_count == 0
    with TestClient(create_application(database_path)) as client:
        response = client.get(
            "/api/events",
            params={"from": "2026-10-26T00:00:00+00:00"},
        )
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "title": "Jazz Night",
            "summary": "Live jazz in the city centre.",
            "category": "music",
            "starts_at": "2026-10-26T19:00:00Z",
            "ends_at": None,
            "location_name": "Cultural Station",
            "source_name": "Moj Novi Sad",
            "source_url": ("https://www.mojnovisad.com/navigator/jazz-night/"),
        }
    ]
