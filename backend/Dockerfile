# syntax=docker/dockerfile:1
FROM python:3.14-alpine3.23 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-cache

FROM python:3.14-alpine3.23 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    BEE_THERE_DATABASE_PATH=/data/bee-there.sqlite3

# Dependencies are installed by uv in the builder. Do not ship pip or its
# vendored packages, including the wheel that ensurepip can reinstall.
RUN apk upgrade --no-cache \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip

RUN addgroup -g 10001 bee-there \
    && adduser -D -H -u 10001 -G bee-there bee-there \
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
