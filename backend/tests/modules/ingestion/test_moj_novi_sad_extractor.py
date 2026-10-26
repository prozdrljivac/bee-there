from datetime import UTC, datetime

import pytest

from modules.events import EventCategory
from modules.ingestion import ExtractionError
from modules.ingestion.moj_novi_sad import MojNoviSadExtractor
from modules.sources import CandidateListing


def _candidate(
    *,
    title: str,
    description: str = "Opis događaja.",
    venue: str = "Kulturna stanica",
) -> CandidateListing:
    return CandidateListing(
        source_url="https://www.mojnovisad.com/navigator/event/",
        content=(
            "Listing date: 26.10.2026.\n"
            f"Title: {title}\n"
            f"Details: 26. Oct | 20:00 | {venue}\n"
            f"Description: {description}"
        ),
    )


def test_classifies_a_theatre_performance() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Pozorišna predstava Hamlet")
    )

    assert event.category is EventCategory.THEATRE


def test_classifies_a_comedy_event() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Stand-up veče komedije")
    )

    assert event.category is EventCategory.COMEDY


def test_classifies_an_exhibition() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Izložba savremene fotografije")
    )

    assert event.category is EventCategory.EXHIBITION


def test_classifies_a_film_screening() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Filmska projekcija: Novi Sad")
    )

    assert event.category is EventCategory.FILM


def test_classifies_a_festival_before_its_music_theme() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Festival ulične muzike")
    )

    assert event.category is EventCategory.FESTIVAL


def test_classifies_a_sports_event() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Fudbalska utakmica na Spensu")
    )

    assert event.category is EventCategory.SPORTS


def test_classifies_a_community_event_from_its_description() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(
            title="Akcija za naš kraj",
            description="Humanitarno okupljanje lokalne zajednice.",
        )
    )

    assert event.category is EventCategory.COMMUNITY


def test_classifies_a_literature_event() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Književno veče i čitanje poezije")
    )

    assert event.category is EventCategory.LITERATURE


def test_classifies_a_fair_before_its_literature_theme() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Međunarodni sajam knjiga")
    )

    assert event.category is EventCategory.FAIR


def test_prefers_a_title_signal_over_the_venue() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Jazz Night", venue="Gradska galerija")
    )

    assert event.category is EventCategory.MUSIC


def test_uses_other_when_no_category_signal_is_known() -> None:
    event = MojNoviSadExtractor().extract(
        _candidate(title="Večernji program", description="Detalji programa.")
    )

    assert event.category is EventCategory.OTHER


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
    assert event.category is EventCategory.MUSIC
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
