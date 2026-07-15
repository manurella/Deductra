# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG PYTHON_IMAGE=python:3.14-slim@sha256:d3400aa122fa42cf0af0dbe8ec3091b047eac5c8f7e3539f7135e86d855dc015
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS python-base

COPY --from=uv /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

FROM python-base AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project

COPY LICENSE README.md pyproject.toml uv.lock ./
COPY Dockerfile ./
COPY docs/ docs/
COPY src/ src/
COPY tests/ tests/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

CMD ["pytest"]

FROM development AS test

RUN ruff format --check . \
    && ruff check . \
    && pyright \
    && pytest \
    && uv build

FROM development AS ci-report-builder

RUN mkdir -p /reports \
    && pytest \
        --junitxml=/reports/junit.xml \
        --cov=deductra \
        --cov-report=term-missing \
        --cov-report=xml:/reports/coverage.xml

FROM scratch AS ci-report

COPY --from=ci-report-builder /reports/ /

FROM python-base AS builder

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project --no-editable

COPY LICENSE README.md pyproject.toml uv.lock ./
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --gid "${APP_GID}" deductra \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --shell /usr/sbin/nologin deductra

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder --chown=${APP_UID}:${APP_GID} /app/.venv /app/.venv

USER ${APP_UID}:${APP_GID}

CMD ["python", "-c", "import deductra; print(deductra.__version__)"]
