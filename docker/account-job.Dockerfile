# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ARG SMOKER=false

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
        rsync \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md VERSION.txt LICENSE ./
COPY src ./src
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN --mount=type=bind,from=smoke_data,target=/tmp/sample_data,ro \
    if [ "$SMOKER" = "true" ]; then \
        echo "Including sample data for smoke testing"; \
        mkdir -p /app/data; \
        cp -a /tmp/sample_data/. /app/data/; \
        if [ -d /app/data/bundles ]; then \
            for jsonl in /app/data/bundles/*.jsonl; do \
                if [ ! -f "$jsonl" ]; then \
                    continue; \
                fi; \
                echo "Preloading local stores from $(basename "$jsonl")"; \
                I4G_ENV=dev \
                I4G_DATA_DIR=/app/data \
                I4G_STORAGE__SQLITE_PATH=/app/data/i4g_store.db \
                I4G_VECTOR__CHROMA_DIR=/app/data/chroma_store \
                python scripts/ingest_bundles.py --input "$jsonl" >/tmp/ingest.log 2>&1 || (cat /tmp/ingest.log && exit 1); \
            done; \
        fi; \
    else \
        echo "Skipping sample data (SMOKER=$SMOKER)"; \
        rm -rf /app/data; \
        mkdir -p /app/data; \
    fi

RUN mkdir -p /app/data/reports/account_list \
    && chown -R 65532:65532 /app

USER 65532:65532

ENV I4G_ENV=dev

CMD ["/app/scripts/run_account_job.sh"]
