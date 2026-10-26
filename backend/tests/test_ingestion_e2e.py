from pathlib import Path

from fastapi.testclient import TestClient

from ingest import run_moj_novi_sad_ingestion
from main import create_application

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


def test_ingests_moj_novi_sad_and_serves_the_event(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database.sqlite3"

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
            "starts_at": "2026-10-26T19:00:00Z",
            "ends_at": None,
            "location_name": "Cultural Station",
            "source_name": "Moj Novi Sad",
            "source_url": ("https://www.mojnovisad.com/navigator/jazz-night/"),
        }
    ]
