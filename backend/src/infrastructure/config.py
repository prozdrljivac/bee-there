"""Runtime configuration from environment variables."""

import os
from pathlib import Path

DATABASE_PATH_ENV = "BEE_THERE_DATABASE_PATH"
USER_AGENT_ENV = "BEE_THERE_USER_AGENT"
DEFAULT_DATABASE_PATH = Path("bee-there.sqlite3")
DEFAULT_USER_AGENT = "BeeThere/0.1"


def database_path_from_environment() -> Path:
    """Return the configured SQLite database path."""
    return Path(os.getenv(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH)))


def user_agent_from_environment() -> str:
    """Return the identification sent with source HTTP requests."""
    return os.getenv(USER_AGENT_ENV, DEFAULT_USER_AGENT)
