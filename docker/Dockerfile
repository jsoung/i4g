FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --upgrade pip && pip install poetry && poetry install --no-dev

COPY src ./src
COPY scripts ./scripts
CMD ["python", "scripts/query_kb.py", "Hello"]
