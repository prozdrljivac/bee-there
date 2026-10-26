from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from modules.events import EventCategory
from modules.ingestion import ExtractedEvent


def test_extracted_event_requires_a_category() -> None:
    with pytest.raises(ValidationError, match="category"):
        ExtractedEvent.model_validate(
            {
                "title": "Jazz Night",
                "summary": "Live jazz in the city centre.",
                "starts_at": datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            }
        )


def test_extracted_event_normalizes_text_and_times() -> None:
    event = ExtractedEvent(
        title="  Jazz Night  ",
        summary="  Live jazz in the city centre.  ",
        category=EventCategory.MUSIC,
        starts_at=datetime(
            2026, 11, 5, 20, 0, tzinfo=timezone(timedelta(hours=1))
        ),
        ends_at=datetime(
            2026, 11, 5, 22, 0, tzinfo=timezone(timedelta(hours=1))
        ),
        location_name="  Cultural Station  ",
    )

    assert event.title == "Jazz Night"
    assert event.summary == "Live jazz in the city centre."
    assert event.category is EventCategory.MUSIC
    assert event.starts_at == datetime(2026, 11, 5, 19, 0, tzinfo=UTC)
    assert event.starts_at.tzinfo is UTC
    assert event.ends_at == datetime(2026, 11, 5, 21, 0, tzinfo=UTC)
    assert event.location_name == "Cultural Station"


def test_extracted_event_rejects_invalid_fields() -> None:
    with pytest.raises(ValidationError):
        ExtractedEvent(
            title="   ",
            summary="Valid summary",
            category=EventCategory.MUSIC,
            starts_at=datetime(2026, 11, 5, 19, 0),
        )
