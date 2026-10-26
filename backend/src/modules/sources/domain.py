"""Domain types owned by the Sources module."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Source:
    """An event source configured for ingestion."""

    id: UUID
    name: str
    base_url: str
    enabled: bool
