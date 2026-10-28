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

## Production container

Build from the repository root. The build installs only locked runtime
dependencies with uv; tests and local databases are excluded from the context.

```shell
docker build -t bee-there:local backend
```

Create a persistent volume, then run migrations as the image's non-root user:

```shell
docker volume create bee-there-data
docker run --rm --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --mount type=volume,src=bee-there-data,dst=/data \
  bee-there:local alembic upgrade head
```

Start the API with the same volume:

```shell
docker run --rm --name bee-there --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --mount type=volume,src=bee-there-data,dst=/data \
  -p 127.0.0.1:8000:8000 bee-there:local
curl --fail http://127.0.0.1:8000/health
```

Run the `docker run` command in one terminal and `curl` in another.
`GET /health` returns `200` with `{"status":"ok"}`. It checks only whether the
application can respond. It does not access SQLite or external services and
does not verify migrations or database readiness. Apply migrations before
starting the API. Kubernetes can use this route for process startup, readiness,
and liveness probes; database checks must be handled separately.

Run ingestion as a separate job, not during API startup:

```shell
docker run --rm --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --mount type=volume,src=bee-there-data,dst=/data \
  -e BEE_THERE_USER_AGENT="BeeThere/0.1 (your-real-contact@example.com)" \
  bee-there:local python src/ingest.py
```

The container uses UID/GID `10001:10001`. Named Docker volumes inherit the
image's `/data` ownership on first use. For bind mounts or Kubernetes volumes,
make the directory writable by this UID/GID before running migrations. Mount
the whole directory: SQLite must write its WAL and shared-memory files beside
the database. Do not store the database in the container filesystem.

The image runs one Uvicorn process on `0.0.0.0:8000`. Logs go to standard
output/error. Terminate TLS at the production ingress; the local example binds
only to loopback. Migrations and ingestion use the same image and database path.

### Container smoke test

With Docker running, execute from `backend`:

```shell
BEE_THERE_TEST_CONTAINER=1 uv run pytest tests/test_container.py
```

This opt-in test builds an image, checks the non-root UID, applies migrations,
ingests local HTML fixtures, and queries `/health` and `/api/events`. It runs
with a read-only root filesystem and a writable named volume, then recreates
the API container to check persistence. It removes its containers, image, and
volume when done. The build needs registry access; fixture ingestion does not
contact the source website. Normal test runs skip this Docker-dependent test.

Build guidance: [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)
and [FastAPI containers guide](https://fastapi.tiangolo.com/deployment/docker/).

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
