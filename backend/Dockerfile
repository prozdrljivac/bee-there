# syntax=docker/dockerfile:1
FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-cache

FROM python:3.14-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    BEE_THERE_DATABASE_PATH=/data/bee-there.sqlite3

RUN groupadd --gid 10001 bee-there \
    && useradd --uid 10001 --gid 10001 --no-create-home bee-there \
    && mkdir /data \
    && chown 10001:10001 /data
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY src ./src

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
