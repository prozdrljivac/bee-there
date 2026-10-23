# Architecture

## 1. Overview

BeeThere aggregates publicly available events in Novi Sad and presents them in a browser extension. Users see the essential information: title, short summary, date/time, location, and a link to the original listing—without visiting multiple websites.

**Architecture:** modular monolith with layered architecture inside each module.

**MVP priorities:** simple deployment, replaceable source integrations, reliable event data, clear boundaries, and minimal infrastructure.

## 2. High-level design

```text
Public event websites
        |
        v
 [Source adapters] ---> [Ingestion] ---> [Event catalog / database]
                              |                       |
                        [LLM extraction]              v
                                              [Read-only HTTP API]
                                                       |
                                                       v
                                               [Browser extension]
```

The backend is **one application and one deployment**. Ingestion jobs and the HTTP API run in the same codebase; scheduled ingestion can run as a separate process using the same application code if needed. The browser extension is an independent client.

## 3. Modules and responsibilities

| Module | Owns | Exposes |
|---|---|---|
| **Sources** | Source configuration, website-specific fetching/parsing adapters, retrieval metadata | Fetch candidate listings from enabled sources |
| **Ingestion** | Scheduling/orchestration, extraction with an LLM, validation, retry handling, pipeline status | Run ingestion for one or all sources |
| **Events** | Canonical event model, deduplication/upsert rules, persistence, event queries | Store/update events; list upcoming events |
| **API** | HTTP routing, request validation, response serialization | Endpoints consumed by the extension |

The API is a thin delivery layer, not a place for business logic. Cross-module access must go through **public interfaces**, not internal repositories or tables. Modules may share infrastructure utilities but should not share business logic through a generic `common` module.

### Internal layered structure

Each domain module may contain:

- **Interface / application:** publicly callable use cases and input/output contracts.
- **Domain:** business rules and types.
- **Infrastructure:** database repositories, HTTP clients, source adapters, and LLM implementations.

Dependency direction: outer layers depend on domain contracts; business rules do not depend on HTTP frameworks or database clients. Keep this lightweight—do not create empty layers just to satisfy the pattern.

## 4. Example project structure

```text
bee-there/
├── backend/
│   ├── src/
│   │   ├── modules/
│   │   │   ├── sources/
│   │   │   │   ├── interface.py
│   │   │   │   ├── domain.py
│   │   │   │   └── adapters/
│   │   │   ├── ingestion/
│   │   │   │   ├── interface.py
│   │   │   │   ├── service.py
│   │   │   │   └── extraction.py
│   │   │   └── events/
│   │   │       ├── interface.py
│   │   │       ├── domain.py
│   │   │       └── repository.py
│   │   ├── api/
│   │   ├── infrastructure/       # config, DB connection, logging
│   │   └── main.py
│   └── tests/
├── extension/
└── docs/
    └── architecture.md
```

This is an **illustrative Python layout**, not a mandatory framework or folder structure. Keep files and folders proportional to actual complexity.

## 5. End-to-end data flow

1. A scheduled job selects an enabled source.
2. Its adapter retrieves candidate event listings and their source URLs.
3. The ingestion module sends the relevant content to an LLM for conversion into the canonical event structure.
4. The system validates required fields and rejects or flags ambiguous/invalid results; an LLM response is **untrusted input**.
5. The Events module deduplicates and upserts event records, retaining original source attribution.
6. The API returns upcoming events, and the browser extension renders compact event cards linking to the original pages.

**Important:** Prefer deterministic extraction when a source exposes structured event data. Use the LLM where it adds value; it should not be the only mechanism for basic HTML parsing.

## 6. Initial data model

```text
Source
- id
- name
- base_url
- enabled

Event
- id
- title
- summary          # 1–2 sentences
- starts_at        # timezone-aware where known
- ends_at?         # optional
- location_name?
- source_id
- source_url
- external_id?     # if supplied by source
- last_seen_at
- created_at
- updated_at

IngestionRun
- id
- source_id
- status
- started_at
- completed_at?
- error_summary?
```

Use **SQLite** as the MVP relational database, stored on persistent local disk. Keep source URLs and provenance. If multiple sources describe the same real-world event, later introduce an `EventSource`/`Listing` table so one canonical event can retain multiple source references. Do not force fuzzy cross-source merging in the first iteration.

## 7. Interfaces and boundary rules

Example conceptual contracts:

```python
class SourceAdapter(Protocol):
    def fetch_candidates(self) -> list[CandidateListing]: ...

class EventCatalog(Protocol):
    def upsert(self, event: EventDraft) -> Event: ...
    def list_upcoming(self, limit: int) -> list[Event]: ...
```

- Only `Sources` knows website-specific selectors and extraction entry points.
- Only `Ingestion` knows how content is transformed into validated event drafts.
- Only `Events` owns event storage and deduplication rules.
- Other modules call exported contracts, never another module's private database access.
- Add automated import-boundary checks once module contracts stabilize.

## 8. API and extension

Initial read-only HTTP endpoint:

```http
GET /api/events?from=2026-10-23&limit=20
```

Response fields: `id`, `title`, `summary`, `starts_at`, `ends_at`, `location_name`, `source_name`, `source_url`.

The browser extension is intentionally thin: fetch, display, sort/filter upcoming listings, and open original sources. Do not duplicate backend normalization or deduplication rules in the extension.

## 9. Runtime and operational choices

- **Deployment:** one backend service, one SQLite database file on persistent storage, static extension bundle.
- **SQLite operations:** enable WAL mode for concurrent reads during writes, keep transactions short, and back up the database file regularly. SQLite supports one writer at a time; revisit the choice only if write concurrency or multi-instance deployment requires it.
- **Scheduling:** begin with a simple periodic job; avoid a message broker until ingestion throughput requires one.
- **Failure isolation:** an individual source failure should not interrupt ingestion from other sources.
- **Idempotency:** repeating an ingestion run should update existing listings rather than produce duplicates; start with `(source_id, external_id)` where available, otherwise a stable source URL key.
- **Observability:** log source, run ID, listing count, parse/validation failures, and elapsed time; do not log secrets or full sensitive payloads.
- **Security and reliability:** use request timeouts, rate limits/backoff, source allowlists, safe outbound URL handling, credentials via environment/secrets, and API input validation.
- **Responsible collection:** inspect each site's terms/robots guidance, avoid excessive traffic, and retain prominent links/attribution to original publishers. Do not reproduce full articles.

