from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from modules.events import TimeRange


def test_time_range_defaults_to_no_upper_bound() -> None:
    start = datetime(2026, 11, 1, tzinfo=UTC)

    time_range = TimeRange(from_time=start)

    assert time_range.from_time == start
    assert time_range.to_time is None


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (
            datetime(2026, 11, 1),
            None,
            "from_time must include a timezone",
        ),
        (
            datetime(2026, 11, 1, tzinfo=UTC),
            datetime(2026, 11, 2),
            "to_time must include a timezone",
        ),
    ],
)
def test_time_range_rejects_bounds_without_a_timezone(
    start: datetime, end: datetime | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        TimeRange(from_time=start, to_time=end)


@pytest.mark.parametrize(
    "end",
    [
        datetime(2026, 10, 31, tzinfo=UTC),
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 11, 1, 2, tzinfo=timezone(timedelta(hours=2))),
    ],
)
def test_time_range_rejects_an_end_at_or_before_the_start(
    end: datetime,
) -> None:
    with pytest.raises(ValueError, match="to_time must be after from_time"):
        TimeRange(from_time=datetime(2026, 11, 1, tzinfo=UTC), to_time=end)


def test_time_range_accepts_ordered_bounds_in_different_timezones() -> None:
    start = datetime(2026, 11, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    end = datetime(2026, 11, 1, 1, tzinfo=UTC)

    time_range = TimeRange(from_time=start, to_time=end)

    assert time_range.from_time == start
    assert time_range.to_time == end


@pytest.mark.parametrize("bound", ["from_time", "to_time"])
def test_time_range_bounds_are_immutable(bound: str) -> None:
    time_range = TimeRange(datetime(2026, 11, 1, tzinfo=UTC))

    with pytest.raises(FrozenInstanceError):
        setattr(time_range, bound, datetime(2026, 11, 2, tzinfo=UTC))
