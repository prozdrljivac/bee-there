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
