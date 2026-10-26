from pathlib import Path

import pytest

from infrastructure.config import database_path_from_environment


def test_database_path_uses_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEE_THERE_DATABASE_PATH", "/data/bee-there.sqlite3")

    assert database_path_from_environment() == Path("/data/bee-there.sqlite3")


def test_database_path_has_a_local_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BEE_THERE_DATABASE_PATH", raising=False)

    assert database_path_from_environment() == Path("bee-there.sqlite3")
