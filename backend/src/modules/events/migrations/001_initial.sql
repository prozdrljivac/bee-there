CREATE TABLE events (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    location_name TEXT,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    external_id TEXT,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (ends_at IS NULL OR ends_at > starts_at)
);

CREATE UNIQUE INDEX events_source_external_id_uq
    ON events (source_id, external_id)
    WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX events_source_url_without_external_id_uq
    ON events (source_id, source_url)
    WHERE external_id IS NULL;

CREATE INDEX events_starts_at_idx ON events (starts_at);

PRAGMA user_version = 1;
