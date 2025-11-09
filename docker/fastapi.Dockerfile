# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps required by scientific Python stack and paddleocr runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source
COPY pyproject.toml README.md VERSION.txt LICENSE ./
COPY src ./src

# Install python dependencies and package
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

# Cloud Run defaults to non-root user 65532; ensure writable artifact dirs
RUN mkdir -p /app/data \
    && chown -R 65532:65532 /app/data

ENV PORT=8080 \
    I4G_ENV=dev

USER 65532:65532

CMD ["uvicorn", "i4g.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
