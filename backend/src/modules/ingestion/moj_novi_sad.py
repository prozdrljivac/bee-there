"""Deterministic extraction for Moj Novi Sad event candidates."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from modules.events import EventCategory
from modules.ingestion.contracts import ExtractedEvent
from modules.ingestion.interface import ExtractionError
from modules.sources import CandidateListing

_LOCAL_TIMEZONE = ZoneInfo("Europe/Belgrade")
_CATEGORY_KEYWORDS = (
    (
        EventCategory.FAIR,
        ("sajam", "fair"),
    ),
    (
        EventCategory.COMEDY,
        ("stand-up", "stand up", "komedij", "comedy", "improv"),
    ),
    (
        EventCategory.FESTIVAL,
        ("festival", "fest"),
    ),
    (
        EventCategory.FILM,
        ("film", "bioskop", "cinema", "projekcij"),
    ),
    (
        EventCategory.EXHIBITION,
        ("izložb", "izlozb", "galerij", "exhibition", "vernisaž"),
    ),
    (
        EventCategory.THEATRE,
        ("pozorišt", "pozorist", "predstava", "teatar", "theatre", "theater"),
    ),
    (
        EventCategory.SPORTS,
        (
            "sport",
            "utakmic",
            "turnir",
            "maraton",
            "trka",
            "fudbal",
            "košark",
            "kosark",
        ),
    ),
    (
        EventCategory.LITERATURE,
        ("književ", "knjizev", "knjig", "poezij", "literatur", "literary"),
    ),
    (
        EventCategory.COMMUNITY,
        (
            "humanitarn",
            "volonter",
            "zajednic",
            "komšij",
            "komsij",
            "građan",
            "gradjan",
        ),
    ),
    (
        EventCategory.MUSIC,
        ("koncert", "music", "muzik", "jazz", "džez", "dzez"),
    ),
)


def _classify_event(title: str, description: str, venue: str) -> EventCategory:
    for value in (title, description, venue):
        text = value.casefold()
        for category, keywords in _CATEGORY_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return category
    return EventCategory.OTHER


class MojNoviSadExtractor:
    """Convert one standard Moj Novi Sad listing into an event."""

    def extract(self, candidate: CandidateListing) -> ExtractedEvent:
        """Extract fields emitted by the Moj Novi Sad source adapter."""
        try:
            fields = dict(
                line.split(": ", 1)
                for line in candidate.content.splitlines()
                if ": " in line
            )
            if "repertoar" in fields["Title"].casefold():
                raise ExtractionError("listing contains multiple events")
            _detail_date, event_time, location = fields["Details"].split(
                " | ", 2
            )
            starts_at = datetime.combine(
                datetime.strptime(fields["Listing date"], "%d.%m.%Y.").date(),
                datetime.strptime(event_time, "%H:%M").time(),
                tzinfo=_LOCAL_TIMEZONE,
            )
            sentences = re.split(r"(?<=[.!?])\s+", fields["Description"])
            summary = " ".join(sentences[:2])
            return ExtractedEvent(
                title=fields["Title"],
                summary=summary,
                category=_classify_event(
                    fields["Title"], fields["Description"], location
                ),
                starts_at=starts_at,
                location_name=location,
            )
        except ExtractionError:
            raise
        except (KeyError, ValueError) as error:
            raise ExtractionError("invalid event fields") from error
