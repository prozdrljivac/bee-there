# BeeThere backend

The backend application and domain modules for BeeThere.

## Run the API

Apply migrations, then start the FastAPI application:

```shell
uv run alembic upgrade head
uv run uvicorn main:app --app-dir src
```

The application uses `bee-there.sqlite3` by default. Set
`BEE_THERE_DATABASE_PATH` to use another database file.

## Test the end-to-end flow

Run ingestion from the `backend` directory:

```shell
export BEE_THERE_USER_AGENT="BeeThere/0.1 (contact@example.com)"
uv run python src/ingest.py
```

The command applies migrations, creates the Moj Novi Sad source when needed,
fetches its current listings, and stores supported events. Standard event pages
are extracted deterministically. Aggregate cinema repertoire pages are counted
as failed because they contain several events and cannot yet be split safely.

Start the API:

```shell
uv run uvicorn main:app --app-dir src
```

Then request events using a timezone-aware start time:

```shell
curl --get http://127.0.0.1:8000/api/events \
  --data-urlencode 'from=2026-10-26T00:00:00+00:00' \
  --data-urlencode 'limit=20'
```

Set `BEE_THERE_DATABASE_PATH` for both commands if you do not want to use the
default `bee-there.sqlite3` file.

## Database migrations

Apply all pending migrations before starting the application:

```shell
uv run alembic upgrade head
```

Alembic uses `bee-there.sqlite3` by default. The event repository assumes that
migrations have already been applied.

Create and review a migration after changing SQLAlchemy models:

```shell
uv run alembic revision --autogenerate -m "describe schema change"
```
