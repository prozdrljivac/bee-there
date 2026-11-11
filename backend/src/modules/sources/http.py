"""HTTP fetching for source adapters."""

import time
from collections.abc import Callable, Iterator

import httpx2

from modules.sources.transport import (
    PublicNetworkTransport,
    validate_source_url,
)

Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class _LimitedStream(httpx2.SyncByteStream):
    def __init__(self, stream: httpx2.SyncByteStream, limit: int) -> None:
        self._stream = stream
        self._limit = limit

    def __iter__(self) -> Iterator[bytes]:
        size = 0
        for chunk in self._stream:
            size += len(chunk)
            if size > self._limit:
                raise ValueError("Ingestion response exceeds size limit")
            yield chunk

    def close(self) -> None:
        self._stream.close()


class HttpxPageClient:
    """Fetch text pages with identification, timeouts, and throttling."""

    _RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
    _MAX_ATTEMPTS = 3
    _MAX_REDIRECTS = 5
    _MAX_RESPONSE_BYTES = 5 * 1024 * 1024

    def __init__(
        self,
        *,
        user_agent: str,
        minimum_interval: float = 1.0,
        client: httpx2.Client | None = None,
        clock: Clock = time.monotonic,
        sleep: Sleeper = time.sleep,
    ) -> None:
        self._user_agent = user_agent
        self._minimum_interval = minimum_interval
        self._client = client or httpx2.Client(
            timeout=httpx2.Timeout(10.0, connect=5.0),
            follow_redirects=False,
            transport=PublicNetworkTransport(),
            trust_env=False,
        )
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None

    def get_text(self, url: str) -> str:
        """Fetch one text page and raise for an unsuccessful response."""
        target = httpx2.URL(url)
        validate_source_url(target)
        self._wait_for_request_slot()

        redirects = 0
        attempt = 0
        while True:
            validate_source_url(target)
            with self._client.stream(
                "GET",
                target,
                headers={"User-Agent": self._user_agent},
                follow_redirects=False,
            ) as response:
                if response.has_redirect_location:
                    target = self._redirect_target(target, response, redirects)
                    redirects += 1
                    attempt = 0
                    continue
                if (
                    response.status_code in self._RETRYABLE_STATUS_CODES
                    and attempt < self._MAX_ATTEMPTS - 1
                ):
                    self._sleep(float(2**attempt))
                    attempt += 1
                    continue
                response.raise_for_status()
                return self._read_page(response)

    def _read_page(self, response: httpx2.Response) -> str:
        self._validate_response_headers(response)

        assert isinstance(response.stream, httpx2.SyncByteStream)
        response.stream = _LimitedStream(
            response.stream, self._MAX_RESPONSE_BYTES
        )

        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > self._MAX_RESPONSE_BYTES:
                raise ValueError("Ingestion response exceeds size limit")
            content.extend(chunk)

        return content.decode(response.encoding or "utf-8", "replace")

    def _validate_response_headers(self, response: httpx2.Response) -> None:
        media_type = (
            response.headers.get("content-type", "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("Unexpected ingestion content type")

        length = response.headers.get("content-length")
        if length is not None and int(length) > self._MAX_RESPONSE_BYTES:
            raise ValueError("Ingestion response exceeds size limit")

    def _wait_for_request_slot(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            wait = self._minimum_interval - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_request_at = now

    def _redirect_target(
        self, current: httpx2.URL, response: httpx2.Response, redirects: int
    ) -> httpx2.URL:
        if redirects >= self._MAX_REDIRECTS:
            raise httpx2.TooManyRedirects(
                "Exceeded ingestion redirect limit",
                request=response.request,
            )
        target = current.join(response.headers["location"])
        validate_source_url(target)
        return target

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()
