"""Alembic database migration entry point."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def upgrade_database(database_path: str | Path) -> None:
    """Configure and upgrade one SQLite database."""
    database_url = URL.create(
        "sqlite", database=str(Path(database_path).resolve())
    )
    config = Config(
        str(_BACKEND_ROOT / "alembic.ini"),
        toml_file=str(_BACKEND_ROOT / "pyproject.toml"),
    )
    config.set_main_option("sqlalchemy.url", database_url.render_as_string())
    config.attributes["database_path_is_explicit"] = True
    command.upgrade(config, "head")
