"""HTTP fetching for source adapters."""

import time
from collections.abc import Callable

import httpx2

Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class HttpxPageClient:
    """Fetch text pages with identification, timeouts, and throttling."""

    _RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
    _MAX_ATTEMPTS = 3

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
            follow_redirects=True,
        )
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None

    def get_text(self, url: str) -> str:
        """Fetch one text page and raise for an unsuccessful response."""
        now = self._clock()
        if self._last_request_at is not None:
            wait = self._minimum_interval - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_request_at = now

        for attempt in range(self._MAX_ATTEMPTS):
            response = self._client.get(
                url,
                headers={"User-Agent": self._user_agent},
            )
            if (
                response.status_code in self._RETRYABLE_STATUS_CODES
                and attempt < self._MAX_ATTEMPTS - 1
            ):
                self._sleep(float(2**attempt))
                continue
            response.raise_for_status()
            return response.text
        raise AssertionError("unreachable")

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()
