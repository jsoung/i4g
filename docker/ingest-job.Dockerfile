# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    I4G_RUNTIME__PROJECT_ROOT=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md VERSION.txt LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

COPY data/retrieval_poc ./data/retrieval_poc

RUN mkdir -p /app/data/chroma_store /app/data/reports \
    && chown -R 65532:65532 /app

USER 65532:65532

ENV I4G_ENV=dev \
    I4G_INGEST__JSONL_PATH=/app/data/retrieval_poc/cases.jsonl

CMD ["i4g-ingest-job"]
