"""Source adapter for Moj Novi Sad event listings."""

from typing import Protocol
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from modules.sources import CandidateListing, Source


class PageClient(Protocol):
    """Fetch text pages over HTTP."""

    def get_text(self, url: str) -> str:
        """Return one page as text."""
        ...


class MojNoviSadAdapter:
    """Fetch event candidates from Moj Novi Sad."""

    _ALLOWED_HOSTS = frozenset({"mojnovisad.com", "www.mojnovisad.com"})

    def __init__(self, client: PageClient) -> None:
        self._client = client

    def fetch_candidates(self, source: Source) -> list[CandidateListing]:
        """Fetch current Moj Novi Sad event listings."""
        source_url = urlsplit(source.base_url)
        if (
            source_url.scheme != "https"
            or source_url.hostname not in self._ALLOWED_HOSTS
        ):
            raise ValueError("unexpected Moj Novi Sad host")
        listing_url = urljoin(source.base_url, "/desavanja/")
        listing = BeautifulSoup(
            self._client.get_text(listing_url), "html.parser"
        )
        event_pages: dict[str, str] = {}
        for date_heading in listing.select("#eventsContainer .date-separator"):
            date_group = date_heading.find_next_sibling(class_="date-group")
            if not isinstance(date_group, Tag):
                continue
            listing_date = date_heading.get_text(" ", strip=True)
            for link in date_group.select(
                '.single-card__details > a[href*="/navigator/"]'
            ):
                href = link.get("href")
                if not isinstance(href, str):
                    continue
                event_url = self._event_url(source.base_url, href)
                if event_url is not None:
                    event_pages.setdefault(event_url, listing_date)

        return [
            self._candidate_from_page(
                event_url,
                listing_date,
                self._client.get_text(event_url),
            )
            for event_url, listing_date in event_pages.items()
        ]

    @staticmethod
    def _event_url(base_url: str, href: str) -> str | None:
        event_url = urlsplit(urljoin(base_url, href))
        source_url = urlsplit(base_url)
        if (
            event_url.scheme not in {"http", "https"}
            or event_url.netloc != source_url.netloc
            or not event_url.path.startswith("/navigator/")
        ):
            return None
        return urlunsplit(event_url._replace(query="", fragment=""))

    @staticmethod
    def _candidate_from_page(
        event_url: str, listing_date: str, html: str
    ) -> CandidateListing:
        page = BeautifulSoup(html, "html.parser")
        canonical = page.select_one('link[rel="canonical"]')
        canonical_href = canonical.get("href") if canonical else None
        source_url = event_url
        if isinstance(canonical_href, str):
            source_url = (
                MojNoviSadAdapter._event_url(event_url, canonical_href)
                or event_url
            )

        shortlink = page.select_one('link[rel="shortlink"]')
        shortlink_href = shortlink.get("href") if shortlink else None
        external_id = None
        if isinstance(shortlink_href, str):
            external_id = parse_qs(urlsplit(shortlink_href).query).get(
                "p", [None]
            )[0]

        title = page.select_one(".single-post-page h1.single-blog__title")
        details = page.select(".single-blog__info-details span")
        description = page.select_one(".single-blog__content")
        if title is None or description is None:
            raise ValueError(f"invalid Moj Novi Sad event page: {event_url}")

        content = "\n".join(
            (
                f"Listing date: {listing_date}",
                f"Title: {title.get_text(' ', strip=True)}",
                "Details: "
                + " | ".join(
                    detail.get_text(" ", strip=True) for detail in details
                ),
                f"Description: {description.get_text(' ', strip=True)}",
            )
        )
        return CandidateListing(
            source_url=source_url,
            content=content,
            external_id=external_id,
        )
