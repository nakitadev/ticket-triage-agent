"""FastAPI service exposing the Support Ticket Triage Agent over HTTP."""

from fastapi import FastAPI, HTTPException, status
from openai import OpenAIError

from src.agent import triage_ticket_async
from src.config import get_openai_api_key, get_openai_model
from src.schemas import SupportTicketInput, TriageDecisionOutput

app = FastAPI(
    title="Support Ticket Triage Agent API",
    description="AI-powered support ticket classification, tool lookup, and routing service.",
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Return service readiness and active model configuration.

    Returns:
        dict[str, str]: Health status and configured OpenAI model name.
    """
    return {"status": "ok", "model": get_openai_model()}


@app.post(
    "/api/v1/triage",
    response_model=TriageDecisionOutput,
    status_code=status.HTTP_200_OK,
    tags=["Triage"],
)
async def triage_endpoint(ticket: SupportTicketInput) -> TriageDecisionOutput:
    """Triage an incoming support ticket and return a structured decision.

    Args:
        ticket: Validated SupportTicketInput request body.

    Returns:
        TriageDecisionOutput: Structured urgency, routing action, and draft response.

    Raises:
        HTTPException: 503 if OPENAI_API_KEY is missing, or 502 on upstream LLM failure.
    """
    if not get_openai_api_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured on the server.",
        )

    try:
        return await triage_ticket_async(ticket)
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream OpenAI API error: {exc}",
        ) from exc
