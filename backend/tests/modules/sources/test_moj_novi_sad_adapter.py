from pathlib import Path
from uuid import UUID

import pytest

from modules.sources import Source
from modules.sources.adapters.moj_novi_sad import MojNoviSadAdapter

FIXTURES = Path(__file__).parents[2] / "fixtures" / "moj_novi_sad"


class StubPageClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        return self._pages[url]


def test_fetch_candidates_rejects_an_unexpected_source_host() -> None:
    client = StubPageClient({})
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Unexpected Source",
        base_url="https://attacker.example/",
        enabled=True,
    )

    with pytest.raises(ValueError, match="unexpected Moj Novi Sad host"):
        MojNoviSadAdapter(client).fetch_candidates(source)

    assert client.requested_urls == []


def test_fetch_candidates_ignores_a_cross_origin_canonical_url() -> None:
    listing_url = "https://www.mojnovisad.com/desavanja/"
    detail_url = "https://www.mojnovisad.com/navigator/jazz-night/"
    listing = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    detail = (
        (FIXTURES / "detail.html")
        .read_text(encoding="utf-8")
        .replace(
            detail_url,
            "https://attacker.example/events/jazz-night",
            1,
        )
    )
    client = StubPageClient({listing_url: listing, detail_url: detail})
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Moj Novi Sad",
        base_url="https://www.mojnovisad.com/",
        enabled=True,
    )

    candidates = MojNoviSadAdapter(client).fetch_candidates(source)

    assert candidates[0].source_url == detail_url


def test_fetch_candidates_reads_and_deduplicates_event_pages() -> None:
    listing_url = "https://www.mojnovisad.com/desavanja/"
    detail_url = "https://www.mojnovisad.com/navigator/jazz-night/"
    client = StubPageClient(
        {
            listing_url: (FIXTURES / "listing.html").read_text(
                encoding="utf-8"
            ),
            detail_url: (FIXTURES / "detail.html").read_text(encoding="utf-8"),
        }
    )
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Moj Novi Sad",
        base_url="https://www.mojnovisad.com/",
        enabled=True,
    )

    candidates = MojNoviSadAdapter(client).fetch_candidates(source)

    assert client.requested_urls == [listing_url, detail_url]
    assert len(candidates) == 1
    assert candidates[0].source_url == detail_url
    assert candidates[0].external_id == "295734"
    assert candidates[0].content == (
        "Listing date: 26.10.2026.\n"
        "Title: Jazz Night\n"
        "Details: 26. Oct | 20:00 | Cultural Station\n"
        "Description: Live jazz in the city centre."
    )
