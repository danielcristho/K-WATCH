# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    MODEL_DIR=/app/models \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .

CMD ["python", "main.py"]
