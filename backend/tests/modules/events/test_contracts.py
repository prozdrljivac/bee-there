from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.events import EventDraft


def test_event_draft_normalizes_text_and_times_to_utc() -> None:
    starts_at = datetime(
        2026, 11, 5, 20, 0, tzinfo=timezone(timedelta(hours=1))
    )

    draft = EventDraft(
        title="  Jazz Night  ",
        summary="  Live jazz in the city centre.  ",
        starts_at=starts_at,
        location_name="  Cultural Station  ",
        source_id=uuid4(),
        source_url="https://example.com/events/jazz-night",
    )

    assert draft.title == "Jazz Night"
    assert draft.summary == "Live jazz in the city centre."
    assert draft.starts_at == datetime(2026, 11, 5, 19, 0, tzinfo=UTC)
    assert draft.location_name == "Cultural Station"


def test_event_draft_rejects_an_end_time_not_after_the_start_time() -> None:
    starts_at = datetime(2026, 11, 5, 19, 0, tzinfo=UTC)

    with pytest.raises(
        ValidationError, match="end time must be after start time"
    ):
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=starts_at,
            ends_at=starts_at,
            source_id=uuid4(),
            source_url="https://example.com/events/jazz-night",
        )


def test_event_draft_rejects_a_start_time_without_a_timezone() -> None:
    with pytest.raises(
        ValidationError, match="datetime must include a timezone"
    ):
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0),
            source_id=uuid4(),
            source_url="https://example.com/events/jazz-night",
        )
