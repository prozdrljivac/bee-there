"""Public interface for the Ingestion module."""

from modules.ingestion.contracts import ExtractedEvent, IngestionResult
from modules.ingestion.interface import EventExtractor
from modules.ingestion.service import IngestionService

__all__ = [
    "EventExtractor",
    "ExtractedEvent",
    "IngestionResult",
    "IngestionService",
]
