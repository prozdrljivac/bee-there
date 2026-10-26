"""Runtime configuration from environment variables."""

import os
from pathlib import Path

DATABASE_PATH_ENV = "BEE_THERE_DATABASE_PATH"
DEFAULT_DATABASE_PATH = Path("bee-there.sqlite3")


def database_path_from_environment() -> Path:
    """Return the configured SQLite database path."""
    return Path(os.getenv(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH)))
