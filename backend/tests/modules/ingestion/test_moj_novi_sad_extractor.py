from datetime import UTC, datetime

import pytest

from modules.events import EventCategory
from modules.ingestion import ExtractionError
from modules.ingestion.moj_novi_sad import MojNoviSadExtractor
from modules.sources import CandidateListing


def test_extracts_a_standard_moj_novi_sad_event_deterministically() -> None:
    candidate = CandidateListing(
        source_url="https://www.mojnovisad.com/navigator/jazz-night/",
        external_id="295734",
        content=(
            "Listing date: 26.10.2026.\n"
            "Title: Jazz Night\n"
            "Details: 26. Oct | 20:00 | Cultural Station\n"
            "Description: Live jazz in the city centre. Doors open at 19:30. "
            "Tickets are available online."
        ),
    )

    event = MojNoviSadExtractor().extract(candidate)

    assert event.title == "Jazz Night"
    assert event.summary == (
        "Live jazz in the city centre. Doors open at 19:30."
    )
    assert event.category is EventCategory.OTHER
    assert event.starts_at == datetime(2026, 10, 26, 19, 0, tzinfo=UTC)
    assert event.ends_at is None
    assert event.location_name == "Cultural Station"


def test_rejects_a_listing_that_contains_multiple_events() -> None:
    candidate = CandidateListing(
        source_url=(
            "https://www.mojnovisad.com/navigator/cineplexx-novi-sad-repertoar/"
        ),
        content=(
            "Listing date: 26.10.2026.\n"
            "Title: Cineplexx Novi Sad - repertoar za ponedeljak\n"
            "Details: 26. Oct | 15:00 | Cineplexx Promenada\n"
            "Description: First film: 19:50. Second film: 21:00."
        ),
    )

    with pytest.raises(ExtractionError, match="multiple events"):
        MojNoviSadExtractor().extract(candidate)


def test_rejects_a_candidate_with_missing_event_fields() -> None:
    candidate = CandidateListing(
        source_url="https://www.mojnovisad.com/navigator/incomplete/",
        content="Title: Incomplete event",
    )

    with pytest.raises(ExtractionError, match="invalid event fields"):
        MojNoviSadExtractor().extract(candidate)
