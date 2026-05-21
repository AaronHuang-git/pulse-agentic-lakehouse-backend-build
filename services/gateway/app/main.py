from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from shared.health import health_response
from shared.logging import configure_logging
from shared.middleware import install_observability

configure_logging("gateway")

app = FastAPI(
    title="Pulse Gateway",
    description="Front-door service: auth, routing, OpenAPI aggregation.",
    version="0.1.0",
    docs_url=None,  # we replace the default /docs with our index below
    redoc_url=None,
)
install_observability(app, "gateway")


@app.get("/health")
def health() -> dict[str, str]:
    return health_response(service="gateway")


_DOCS_INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Pulse API Documentation</title>
  <style>
    body {
      font-family: -apple-system, system-ui, sans-serif;
      max-width: 720px; margin: 3em auto; padding: 0 1em; color: #222;
    }
    h1 { border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }
    h2 { margin-top: 2em; }
    ul { line-height: 1.8; }
    a { color: #0a5; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code { background: #f3f3f3; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.9em; }
    .muted { color: #666; font-size: 0.9em; }
  </style>
</head>
<body>
  <h1>Pulse API Documentation</h1>
  <p>Pulse is a self-hostable agentic lakehouse backend. Each service exposes
  its own OpenAPI/Swagger UI; this page is the index.</p>

  <h2>Service docs (Swagger UI)</h2>
  <ul>
    <li><a href="http://localhost:8001/docs">Ingest</a> &mdash;
        CSV upload, async parse, job status.
        <span class="muted">port 8001</span></li>
    <li><a href="http://localhost:8002/docs">Query</a> &mdash;
        catalog, structured DSL, safe SQL, distinct values.
        <span class="muted">port 8002</span></li>
    <li><a href="http://localhost:8003/docs">Agent</a> &mdash;
        natural-language ask with tool-call trace.
        <span class="muted">port 8003</span></li>
  </ul>

  <h2>Operational endpoints</h2>
  <ul>
    <li><code>GET /health</code> on every service (8000&ndash;8003)</li>
    <li><code>GET /metrics</code> on every service (Prometheus format)</li>
    <li>MinIO console: <a href="http://localhost:9001">localhost:9001</a></li>
  </ul>

  <h2>Authentication</h2>
  <p>All non-public endpoints require <code>Authorization: Bearer &lt;api-key&gt;</code>.
  Local dev key seeded by <code>scripts/seed_demo_tenant.py</code>:
  <code>demo-key-1234</code>.</p>

  <p class="muted">See <code>README.md</code> at the repo root for the full
  architecture diagram and quickstart.</p>
</body>
</html>
"""


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
def docs_index() -> str:
    """Aggregator index of per-service Swagger UIs."""
    return _DOCS_INDEX
