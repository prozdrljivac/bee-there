"""Ingestion orchestration service."""

from pydantic import ValidationError

from modules.events import EventDraft, EventRepository
from modules.ingestion.contracts import IngestionResult
from modules.ingestion.interface import EventExtractor, ExtractionError
from modules.sources import Source, SourceAdapter


class IngestionService:
    """Transform source listings and store canonical events."""

    def __init__(
        self,
        event_repository: EventRepository,
        extractor: EventExtractor,
    ) -> None:
        self._event_repository = event_repository
        self._extractor = extractor

    def run(self, source: Source, adapter: SourceAdapter) -> IngestionResult:
        """Ingest all candidate listings from one source."""
        if not source.enabled:
            raise ValueError("source must be enabled")
        candidates = adapter.fetch_candidates(source)
        stored_count = 0
        failed_count = 0
        for candidate in candidates:
            try:
                extracted = self._extractor.extract(candidate)
                draft = EventDraft(
                    title=extracted.title,
                    summary=extracted.summary,
                    category=extracted.category,
                    starts_at=extracted.starts_at,
                    ends_at=extracted.ends_at,
                    location_name=extracted.location_name,
                    source_id=source.id,
                    source_url=candidate.source_url,
                    external_id=candidate.external_id,
                )
            except ExtractionError, ValidationError:
                failed_count += 1
                continue
            self._event_repository.upsert(draft)
            stored_count += 1
        return IngestionResult(
            discovered_count=len(candidates),
            stored_count=stored_count,
            failed_count=failed_count,
        )
