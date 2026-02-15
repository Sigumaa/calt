# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY examples ./examples
COPY tests ./tests

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group dev

ENTRYPOINT ["/app/.venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
CMD ["tests/unit", "tests/integration", "tests/e2e"]
