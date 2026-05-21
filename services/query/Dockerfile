FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-install-project || uv sync --no-install-project

COPY shared/ ./shared/
COPY services/query/ ./services/query/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "services.query.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
