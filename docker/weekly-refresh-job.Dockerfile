# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    I4G_RUNTIME__PROJECT_ROOT=/app

WORKDIR /app

# System dependencies (including Microsoft ODBC Driver 18 for SQL Server)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
        ca-certificates \
        build-essential \
        unixodbc \
        unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md VERSION.txt LICENSE ./
COPY src ./src
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /app/data \
    && chown -R 65532:65532 /app

USER 65532:65532

ENTRYPOINT ["python", "scripts/migration/run_weekly_refresh.py"]
