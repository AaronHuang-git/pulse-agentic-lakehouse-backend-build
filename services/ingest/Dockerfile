FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-install-project || uv sync --no-install-project

COPY shared/ ./shared/
COPY services/ingest/ ./services/ingest/
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "services.ingest.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
