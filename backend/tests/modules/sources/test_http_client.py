from collections.abc import Iterator

import httpx2

from modules.sources.http import HttpxPageClient


def test_page_client_retries_temporary_server_failures() -> None:
    attempts = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        status_code = 503 if attempts == 1 else 200
        return httpx2.Response(status_code, text="page content")

    sleeps: list[float] = []
    client = HttpxPageClient(
        user_agent="BeeThere/0.1 (contact@example.com)",
        minimum_interval=0,
        client=httpx2.Client(transport=httpx2.MockTransport(respond)),
        sleep=sleeps.append,
    )

    try:
        content = client.get_text("https://example.com/events")
    finally:
        client.close()

    assert content == "page content"
    assert attempts == 2
    assert sleeps == [1.0]


def test_page_client_identifies_requests_and_throttles_them() -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, text="page content")

    times: Iterator[float] = iter((0.0, 0.25))
    sleeps: list[float] = []
    http_client = httpx2.Client(transport=httpx2.MockTransport(respond))
    client = HttpxPageClient(
        user_agent="BeeThere/0.1 (contact@example.com)",
        minimum_interval=1.0,
        client=http_client,
        clock=lambda: next(times),
        sleep=sleeps.append,
    )

    try:
        assert client.get_text("https://example.com/first") == "page content"
        assert client.get_text("https://example.com/second") == "page content"
    finally:
        client.close()

    assert [request.headers["user-agent"] for request in requests] == [
        "BeeThere/0.1 (contact@example.com)",
        "BeeThere/0.1 (contact@example.com)",
    ]
    assert sleeps == [0.75]
