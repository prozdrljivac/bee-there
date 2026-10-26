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
        ends_at=datetime(
            2026, 11, 5, 22, 0, tzinfo=timezone(timedelta(hours=1))
        ),
        location_name="  Cultural Station  ",
        source_id=uuid4(),
        source_url="https://example.com/events/jazz-night",
    )

    assert draft.title == "Jazz Night"
    assert draft.summary == "Live jazz in the city centre."
    assert draft.starts_at == datetime(2026, 11, 5, 19, 0, tzinfo=UTC)
    assert draft.ends_at == datetime(2026, 11, 5, 21, 0, tzinfo=UTC)
    assert draft.location_name == "Cultural Station"


@pytest.mark.parametrize(
    "field",
    ("title", "summary", "location_name", "external_id"),
)
def test_event_draft_rejects_blank_text(field: str) -> None:
    data = {
        "title": "Jazz Night",
        "summary": "Live jazz in the city centre.",
        "starts_at": datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        "source_id": uuid4(),
        "source_url": "https://example.com/events/jazz-night",
        field: "   ",
    }

    with pytest.raises(ValidationError, match="at least 1 character"):
        EventDraft.model_validate(data)


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


def test_event_draft_rejects_an_invalid_source_url() -> None:
    with pytest.raises(ValidationError, match="valid URL"):
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            source_id=uuid4(),
            source_url="not-a-url",
        )


def test_event_draft_rejects_an_end_time_without_a_timezone() -> None:
    with pytest.raises(
        ValidationError, match="datetime must include a timezone"
    ):
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            ends_at=datetime(2026, 11, 5, 21, 0),
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
