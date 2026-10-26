"""Run the Moj Novi Sad ingestion flow."""

from pathlib import Path

from infrastructure.config import (
    database_path_from_environment,
    user_agent_from_environment,
)
from infrastructure.migrations import upgrade_database
from modules.events.sqlite import SQLiteEventRepository
from modules.ingestion import IngestionResult, IngestionService
from modules.ingestion.moj_novi_sad import MojNoviSadExtractor
from modules.sources import SourceDraft
from modules.sources.adapters.moj_novi_sad import MojNoviSadAdapter, PageClient
from modules.sources.http import HttpxPageClient
from modules.sources.sqlite import SQLiteSourceRepository

_MOJ_NOVI_SAD_NAME = "Moj Novi Sad"
_MOJ_NOVI_SAD_URL = "https://www.mojnovisad.com/"


def run_moj_novi_sad_ingestion(
    database_path: str | Path,
    page_client: PageClient,
) -> IngestionResult:
    """Fetch, extract, and store Moj Novi Sad events."""
    upgrade_database(database_path)
    sources = SQLiteSourceRepository(database_path)
    source = sources.get_by_base_url(_MOJ_NOVI_SAD_URL)
    if source is None:
        source = sources.create(
            SourceDraft(
                name=_MOJ_NOVI_SAD_NAME,
                base_url=_MOJ_NOVI_SAD_URL,
            )
        )
    service = IngestionService(
        SQLiteEventRepository(database_path),
        MojNoviSadExtractor(),
    )
    return service.run(source, MojNoviSadAdapter(page_client))


def main() -> None:
    """Run ingestion using the configured database and live website."""
    client = HttpxPageClient(user_agent=user_agent_from_environment())
    try:
        result = run_moj_novi_sad_ingestion(
            database_path_from_environment(), client
        )
    finally:
        client.close()
    print(
        f"Discovered: {result.discovered_count}; "
        f"stored: {result.stored_count}; failed: {result.failed_count}"
    )


if __name__ == "__main__":
    main()
