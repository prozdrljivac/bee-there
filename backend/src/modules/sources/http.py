"""HTTP fetching for source adapters."""

import time
from collections.abc import Callable

import httpx2

from modules.sources.transport import (
    PublicNetworkTransport,
    validate_source_url,
)

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
        now = self._clock()
        if self._last_request_at is not None:
            wait = self._minimum_interval - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_request_at = now

        redirects = 0
        attempt = 0
        while True:
            validate_source_url(target)
            response = self._client.get(
                target,
                headers={"User-Agent": self._user_agent},
                follow_redirects=False,
            )
            if response.has_redirect_location:
                if redirects >= 5:
                    raise httpx2.TooManyRedirects(
                        "Exceeded ingestion redirect limit",
                        request=response.request,
                    )
                target = target.join(response.headers["location"])
                validate_source_url(target)
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
            return response.text

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()
