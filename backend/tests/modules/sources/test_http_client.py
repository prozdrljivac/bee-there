from collections.abc import Iterator

import httpx2
import pytest

from modules.sources.http import HttpxPageClient


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/admin",
        "http://[fd00::1]/admin",
        "file:///etc/passwd",
    ],
)
def test_page_client_blocks_unsafe_redirects(target: str) -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(302, headers={"location": target})

    client = HttpxPageClient(
        user_agent="BeeThere/test",
        client=httpx2.Client(
            transport=httpx2.MockTransport(respond), follow_redirects=True
        ),
    )
    try:
        with pytest.raises(ValueError, match="Unsafe source URL"):
            client.get_text("https://example.com/events")
    finally:
        client.close()
    assert len(requests) == 1


def test_page_client_follows_relative_and_public_redirects() -> None:
    urls: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        urls.append(str(request.url))
        if len(urls) == 1:
            return httpx2.Response(301, headers={"location": "../next"})
        if len(urls) == 2:
            return httpx2.Response(
                307, headers={"location": "https://other.example/event"}
            )
        return httpx2.Response(
            200, text="event", headers={"content-type": "text/html"}
        )

    client = HttpxPageClient(
        user_agent="BeeThere/test",
        client=httpx2.Client(transport=httpx2.MockTransport(respond)),
    )
    try:
        assert client.get_text("https://example.com/list/events") == "event"
    finally:
        client.close()
    assert urls == [
        "https://example.com/list/events",
        "https://example.com/next",
        "https://other.example/event",
    ]


def test_page_client_stops_redirect_loops() -> None:
    urls: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        urls.append(str(request.url))
        return httpx2.Response(302, headers={"location": "/loop"})

    client = HttpxPageClient(
        user_agent="BeeThere/test",
        client=httpx2.Client(transport=httpx2.MockTransport(respond)),
    )
    try:
        with pytest.raises(httpx2.TooManyRedirects):
            client.get_text("https://example.com/loop")
    finally:
        client.close()
    assert len(urls) == 6


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/event",
        "http://0.0.0.0/event",
        "http://100.100.100.200/event",
        "http://168.63.129.16/event",
        "http://224.0.0.1/event",
        "http://[fe80::1%25eth0]/event",
        "http://[::ffff:8.8.8.8]/event",
        "ftp://example.com/event",
        "https://user:password@example.com/event",
    ],
)
def test_page_client_rejects_unsafe_initial_urls(url: str) -> None:
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200)

    client = HttpxPageClient(
        user_agent="BeeThere/test",
        client=httpx2.Client(transport=httpx2.MockTransport(respond)),
    )
    try:
        with pytest.raises(ValueError, match="Unsafe source URL"):
            client.get_text(url)
    finally:
        client.close()
    assert sent == []


def test_page_client_retries_temporary_server_failures() -> None:
    attempts = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        status_code = 503 if attempts == 1 else 200
        return httpx2.Response(
            status_code,
            text="page content",
            headers={"content-type": "text/html"},
        )

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
        return httpx2.Response(
            200, text="page content", headers={"content-type": "text/html"}
        )

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
