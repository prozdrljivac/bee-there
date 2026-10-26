"""BeeThere application composition root."""

from pathlib import Path

from fastapi import FastAPI

from api.app import create_app
from infrastructure.config import database_path_from_environment
from modules.events.sqlite import SQLiteEventRepository
from modules.sources.sqlite import SQLiteSourceRepository


def create_application(database_path: str | Path) -> FastAPI:
    """Create the application for one database."""
    return create_app(
        SQLiteEventRepository(database_path),
        SQLiteSourceRepository(database_path),
    )


app = create_application(database_path_from_environment())
