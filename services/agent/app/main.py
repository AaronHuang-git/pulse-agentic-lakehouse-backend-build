"""Pulse agent service — LLM tool-calling orchestrator."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from services.agent.app.loop import run_agent
from services.agent.app.models import AskRequest, AskResponse
from shared.auth import require_tenant
from shared.health import health_response
from shared.logging import configure_logging
from shared.middleware import install_observability

configure_logging("agent")

app = FastAPI(
    title="Pulse Agent",
    description="LLM tool-calling orchestrator over the query and catalog APIs.",
    version="0.1.0",
)
install_observability(app, "agent")


@app.get("/health")
def health() -> dict[str, str]:
    return health_response(service="agent")


@app.post("/v1/agent/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    tenant_id: Annotated[str, Depends(require_tenant)],
    authorization: Annotated[str | None, Header()] = None,
) -> AskResponse:
    # require_tenant has already validated; pull the bearer token from the
    # same header to forward to downstream services.
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required.",
        )
    return await run_agent(question=body.question, bearer_token=authorization)
