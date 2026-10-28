"""Opt-in image test: BEE_THERE_TEST_CONTAINER=1 uv run pytest tests/test_container.py."""

import json
import os
import subprocess
from http.client import RemoteDisconnected
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import MagicMock, Mock
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _docker(*args: str, input: str | None = None) -> str:
    return subprocess.run(
        ["docker", *args],
        input=input,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    ).stdout.strip()


def _wait_for_health(base_url: str, container: str) -> None:
    deadline = monotonic() + 20
    while True:
        try:
            with urlopen(f"{base_url}/health", timeout=1) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ok"}
            return
        except URLError, TimeoutError, RemoteDisconnected, ConnectionResetError:
            if monotonic() >= deadline:
                pytest.fail(_docker("logs", container))
            sleep(0.2)


def test_health_check_retries_a_connection_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = b'{"status": "ok"}'
    request = Mock(
        side_effect=[ConnectionResetError("reset by peer"), response]
    )
    monkeypatch.setattr("test_container.urlopen", request)
    monkeypatch.setattr("test_container.sleep", lambda _seconds: None)

    _wait_for_health("http://127.0.0.1:8000", "test-api")

    assert request.call_count == 2


@pytest.mark.skipif(
    os.environ.get("BEE_THERE_TEST_CONTAINER") != "1",
    reason="requires a running Docker daemon and image registry access",
)
def test_container_ingests_and_serves_a_persistent_database() -> None:
    suffix = uuid4().hex
    image = f"bee-there-test:{suffix}"
    volume = f"bee-there-test-{suffix}"
    container = f"bee-there-test-{suffix}"
    try:
        _docker("build", "-t", image, str(BACKEND))
        _docker("volume", "create", volume)
        options = (
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--mount",
            f"type=volume,src={volume},dst=/data",
        )
        assert _docker("run", "--rm", image, "id", "-u") == "10001"
        _docker("run", "--rm", *options, image, "alembic", "upgrade", "head")
        _docker(
            "run",
            "--rm",
            "-i",
            *options,
            "--mount",
            f"type=bind,src={BACKEND / 'tests/fixtures/moj_novi_sad'},"
            "dst=/fixtures,readonly",
            image,
            "python",
            "-",
            input="""
from pathlib import Path
import sqlite3
from ingest import run_moj_novi_sad_ingestion

class Pages:
    def get_text(self, url):
        name = "listing.html" if url.endswith("/desavanja/") else "detail.html"
        return (Path("/fixtures") / name).read_text()

result = run_moj_novi_sad_ingestion("/data/bee-there.sqlite3", Pages())
assert result.stored_count == 1, result
assert result.failed_count == 0, result
with sqlite3.connect("/data/bee-there.sqlite3") as db:
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
""",
        )
        for _ in range(2):
            _docker(
                "run",
                "-d",
                "--name",
                container,
                *options,
                "-p",
                "127.0.0.1::8000",
                image,
            )
            port = _docker("port", container, "8000/tcp").rsplit(":", 1)[1]
            base_url = f"http://127.0.0.1:{port}"
            _wait_for_health(base_url, container)
            with urlopen(
                f"{base_url}/api/events?from=2026-10-26T00:00:00%2B00:00",
                timeout=5,
            ) as response:
                assert response.status == 200
                events = json.load(response)
                assert len(events) == 1
                assert events[0]["title"] == "Jazz Night"
                assert events[0]["source_name"] == "Moj Novi Sad"
            _docker("rm", "-f", container)
    finally:
        for args in (
            ("rm", "-f", container),
            ("volume", "rm", volume),
            ("image", "rm", image),
        ):
            subprocess.run(
                ["docker", *args], capture_output=True, check=False, timeout=30
            )
