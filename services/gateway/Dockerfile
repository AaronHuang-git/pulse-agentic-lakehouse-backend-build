FROM python:3.11-slim

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (better layer caching — only re-installs when deps change)
COPY pyproject.toml uv.lock* ./

# Install deps into a virtual env at /app/.venv
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

# Copy source code
COPY shared/ ./shared/
COPY services/gateway/ ./services/gateway/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "services.gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
