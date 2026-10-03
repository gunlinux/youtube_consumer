# syntax=docker/dockerfile:1

# ---------- Stage 1: builder — install dependencies with uv ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first so the layer is cached unless pyproject/lock change.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Add the application source.
COPY src ./src

# ---------- Stage 2: runtime — minimal image, no uv, no build tools ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Config comes from environment variables at runtime:
#   youtube_channel, amqp_dsn, amqp_exchange
CMD ["python", "-m", "src"]
