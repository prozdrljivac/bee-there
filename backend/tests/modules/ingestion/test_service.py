from datetime import UTC, datetime
from uuid import UUID

import pytest

from modules.events import Event, EventDraft
from modules.ingestion import ExtractedEvent, ExtractionError, IngestionService
from modules.sources import CandidateListing, Source


class StubSourceAdapter:
    def __init__(self, candidates: list[CandidateListing]) -> None:
        self._candidates = candidates

    def fetch_candidates(self, source: Source) -> list[CandidateListing]:
        return self._candidates


class StubEventExtractor:
    def extract(self, candidate: CandidateListing) -> ExtractedEvent:
        return ExtractedEvent(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            location_name="Cultural Station",
        )


class PartiallyInvalidExtractor:
    def extract(self, candidate: CandidateListing) -> ExtractedEvent:
        title = "   " if candidate.content == "invalid" else "Jazz Night"
        return ExtractedEvent(
            title=title,
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        )


class UnsupportedListingExtractor:
    def extract(self, candidate: CandidateListing) -> ExtractedEvent:
        raise ExtractionError("listing contains multiple events")


class RecordingEventRepository:
    def __init__(self) -> None:
        self.drafts: list[EventDraft] = []

    def upsert(self, draft: EventDraft) -> Event:
        self.drafts.append(draft)
        now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
        return Event(
            id=UUID("019a57c0-8800-7000-8000-000000000001"),
            title=draft.title,
            summary=draft.summary,
            starts_at=draft.starts_at,
            ends_at=draft.ends_at,
            location_name=draft.location_name,
            source_id=draft.source_id,
            source_url=draft.source_url,
            external_id=draft.external_id,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )

    def list_upcoming(self, *, from_time: datetime, limit: int) -> list[Event]:
        raise NotImplementedError


def test_run_continues_after_an_invalid_extraction() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    candidates = [
        CandidateListing(
            source_url="https://example.com/events/invalid",
            content="invalid",
        ),
        CandidateListing(
            source_url="https://example.com/events/jazz-night",
            content="valid",
        ),
    ]
    repository = RecordingEventRepository()
    service = IngestionService(repository, PartiallyInvalidExtractor())

    result = service.run(source, StubSourceAdapter(candidates))

    assert result.discovered_count == 2
    assert result.stored_count == 1
    assert result.failed_count == 1
    assert [draft.source_url for draft in repository.drafts] == [
        "https://example.com/events/jazz-night"
    ]


def test_run_counts_an_unsupported_listing_as_failed() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Moj Novi Sad",
        base_url="https://www.mojnovisad.com/",
        enabled=True,
    )
    candidate = CandidateListing(
        source_url="https://www.mojnovisad.com/navigator/cinema/",
        content="unsupported",
    )
    service = IngestionService(
        RecordingEventRepository(), UnsupportedListingExtractor()
    )

    result = service.run(source, StubSourceAdapter([candidate]))

    assert result.discovered_count == 1
    assert result.stored_count == 0
    assert result.failed_count == 1


def test_run_rejects_a_disabled_source() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=False,
    )
    service = IngestionService(RecordingEventRepository(), StubEventExtractor())

    with pytest.raises(ValueError, match="source must be enabled"):
        service.run(source, StubSourceAdapter([]))


def test_run_extracts_and_stores_candidates_with_source_attribution() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    candidate = CandidateListing(
        source_url="https://example.com/events/jazz-night",
        content="Event page content",
        external_id="jazz-2026",
    )
    repository = RecordingEventRepository()
    service = IngestionService(repository, StubEventExtractor())

    result = service.run(source, StubSourceAdapter([candidate]))

    assert result.discovered_count == 1
    assert result.stored_count == 1
    assert result.failed_count == 0
    assert repository.drafts == [
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            location_name="Cultural Station",
            source_id=source.id,
            source_url=candidate.source_url,
            external_id="jazz-2026",
        )
    ]
