import gzip
from collections.abc import Iterator
from unittest.mock import patch

import httpx2
import pytest

from modules.sources.http import HttpxPageClient

MAX_PAGE_BYTES = 5 * 1024 * 1024


class TrackedStream(httpx2.SyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.reads = 0
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self.chunks:
            self.reads += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


def fetch_page(headers: dict[str, str], stream: TrackedStream) -> str:
    def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers=headers, stream=stream)

    with (
        patch(
            "socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
        ),
        patch(
            "httpx2.HTTPTransport",
            side_effect=lambda **kwargs: httpx2.MockTransport(respond),
        ),
    ):
        client = HttpxPageClient(user_agent="BeeThere/test")
        try:
            return client.get_text("https://events.example/event")
        finally:
            client.close()


@pytest.mark.parametrize(
    "headers",
    [{}, {"content-type": "application/json"}, {"content-type": "image/png"}],
)
def test_rejects_unexpected_content_type_before_reading(
    headers: dict[str, str],
) -> None:
    stream = TrackedStream([b"not an HTML page"])
    with pytest.raises(ValueError, match="content type"):
        fetch_page(headers, stream)
    assert stream.reads == 0
    assert stream.closed


@pytest.mark.parametrize("length", [None, "1"])
def test_stops_oversized_stream_without_trusting_content_length(
    length: str | None,
) -> None:
    stream = TrackedStream([b"x" * MAX_PAGE_BYTES, b"x", b"unread"])
    headers = {"content-type": "text/html"}
    if length is not None:
        headers["content-length"] = length
    with pytest.raises(ValueError, match="size limit"):
        fetch_page(headers, stream)
    assert stream.reads == 2
    assert stream.closed


def test_rejects_compressed_page_that_expands_past_limit() -> None:
    compressed = gzip.compress(b"x" * (MAX_PAGE_BYTES + 1))
    stream = TrackedStream([compressed, b"unread"])
    with pytest.raises(ValueError, match="size limit"):
        fetch_page(
            {
                "content-type": "text/html",
                "content-encoding": "gzip",
                "content-length": str(len(compressed)),
            },
            stream,
        )
    assert stream.reads == 1
    assert stream.closed


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "Text/HTML; charset=utf-8", "application/xhtml+xml"],
)
def test_accepts_supported_pages_at_exact_size_limit(content_type: str) -> None:
    body = b"x" * MAX_PAGE_BYTES
    stream = TrackedStream([body])
    assert fetch_page({"content-type": content_type}, stream) == body.decode()
    assert stream.closed


def test_accepts_compressed_html_with_declared_charset() -> None:
    text = "Café event"
    compressed = gzip.compress(text.encode("iso-8859-2"))
    stream = TrackedStream([compressed])
    assert (
        fetch_page(
            {
                "content-type": "text/html; charset=iso-8859-2",
                "content-encoding": "gzip",
            },
            stream,
        )
        == text
    )
    assert stream.closed


def test_limits_encoded_bytes_even_when_decoder_emits_nothing() -> None:
    stream = TrackedStream(
        [gzip.compress(b""), b"\x00" * MAX_PAGE_BYTES, b"unread"]
    )
    with pytest.raises(ValueError, match="size limit"):
        fetch_page(
            {"content-type": "text/html", "content-encoding": "gzip"},
            stream,
        )
    assert stream.reads == 2
    assert stream.closed


@pytest.mark.parametrize("status", [302, 503])
def test_discards_redirect_and_retry_bodies_without_reading(
    status: int,
) -> None:
    discarded = TrackedStream([b"x" * (MAX_PAGE_BYTES + 1)])
    page = TrackedStream([b"event"])
    attempts = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx2.Response(
                status, headers={"location": "/next"}, stream=discarded
            )
        return httpx2.Response(
            200, headers={"content-type": "text/html"}, stream=page
        )

    client = HttpxPageClient(
        user_agent="BeeThere/test",
        client=httpx2.Client(transport=httpx2.MockTransport(respond)),
        sleep=lambda seconds: None,
    )
    try:
        assert client.get_text("https://events.example/event") == "event"
    finally:
        client.close()
    assert discarded.reads == 0
    assert discarded.closed
    assert page.closed


def test_rejects_large_content_length_before_reading() -> None:
    stream = TrackedStream([b"page"])
    with pytest.raises(ValueError, match="size limit"):
        fetch_page(
            {
                "content-type": "text/html",
                "content-length": str(MAX_PAGE_BYTES + 1),
            },
            stream,
        )
    assert stream.reads == 0
    assert stream.closed
