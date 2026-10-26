"""Public interface for the Sources module."""

from infrastructure.persistence import (
    PersistenceConflictError,
    PersistenceError,
)
from modules.sources.contracts import (
    CandidateListing,
    SourceDraft,
    SourceUpdate,
)
from modules.sources.domain import Source
from modules.sources.interface import SourceAdapter, SourceRepository

__all__ = [
    "CandidateListing",
    "PersistenceConflictError",
    "PersistenceError",
    "Source",
    "SourceAdapter",
    "SourceDraft",
    "SourceRepository",
    "SourceUpdate",
]
