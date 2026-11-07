"""FastAPI service exposing the Support Ticket Triage Agent over HTTP."""

from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, status
from openai import OpenAIError

from src.agent import triage_ticket_async
from src.config import get_openai_api_key, get_openai_model
from src.schemas import SupportTicketInput, TriageDecisionOutput

app = FastAPI(
    title="Support Ticket Triage Agent API",
    description="AI-powered support ticket classification, tool lookup, and routing service.",
    version="1.0.0",
)

TICKET_OPENAPI_EXAMPLES = {
    "tck_001_billing_dispute": {
        "summary": "TCK-001: Duplicate Charges & Locked Pro Export (Critical / English)",
        "description": "Free user charged 3x $29.99 with board presentation in 2 hours threatening a bank chargeback.",
        "value": {
            "ticket_id": "TCK-001",
            "customer_info": {
                "plan": "Free",
                "tenure": "4 months",
                "region": "US",
                "seats": 1,
                "notes": "Attempted upgrade to Pro today; first time contacting support.",
            },
            "messages": [
                {
                    "timestamp": "2025-03-10T09:15:00Z",
                    "text": "Hi, I just tried upgrading to the Pro plan so I can use the Export feature, but the checkout page spun forever and timed out.",
                },
                {
                    "timestamp": "2025-03-10T09:22:00Z",
                    "text": "I tried two more times and my bank app now shows THREE pending charges of $29.99 ($89.97 total), yet my account is STILL on the Free plan and Export is locked!",
                },
                {
                    "timestamp": "2025-03-10T09:30:00Z",
                    "text": "I have an executive board presentation in 2 hours and desperately need to export my deck right now. If nobody fixes my Pro access and refunds these extra charges immediately, I am calling my bank to file a fraud dispute/chargeback!",
                },
            ],
        },
    },
    "tck_002_thai_enterprise_outage": {
        "summary": "TCK-002: Thai Enterprise HTTP 500 Outage (Critical / Thai)",
        "description": "45-seat Enterprise tenant in Thailand hitting HTTP 500 across browsers ahead of an afternoon client demo.",
        "value": {
            "ticket_id": "TCK-002",
            "customer_info": {
                "plan": "Enterprise",
                "tenure": "2 years",
                "region": "Asia",
                "seats": 45,
                "notes": "Strategic Enterprise account in Thailand (ap-southeast-1) with P1 SLA.",
            },
            "messages": [
                {
                    "timestamp": "2025-03-10T10:05:00Z",
                    "text": "สวัสดีครับ ตอนนี้ทีมงานของเราเข้าใช้งานระบบไม่ได้เลย หน้าจอขึ้น HTTP Error 500 ตลอดเวลา",
                },
                {
                    "timestamp": "2025-03-10T10:12:00Z",
                    "text": "ลองเปลี่ยนเบราว์เซอร์ทั้ง Chrome และ Safari รวมถึงให้เพื่อนร่วมงานอีกหลายเครื่องในออฟฟิศลองเข้าดูแล้ว ก็เจอ Error 500 เหมือนกันทั้งหมดครับ",
                },
                {
                    "timestamp": "2025-03-10T10:18:00Z",
                    "text": "ช่วงบ่ายวันนี้เรามี Demo สำคัญกับลูกค้ารายใหญ่ด้วยครับ หน้า Status Page บอกว่าปกติ แต่ไม่แน่ใจว่าเซิร์ฟเวอร์โซน Asia มีปัญหาหรือเปล่า รบกวนช่วยตรวจสอบด่วนที่สุดเลยครับ",
                },
            ],
        },
    },
    "tck_003_macos_dark_mode": {
        "summary": "TCK-003: macOS Dark Mode Bug & Roadmap Question (Low / Auto-Respond)",
        "description": "Friendly Pro daily user reporting macOS v2.4.1 'System Default' theme sync quirk and asking about scheduled dark mode.",
        "value": {
            "ticket_id": "TCK-003",
            "customer_info": {
                "plan": "Pro",
                "tenure": "8 months",
                "region": "US",
                "seats": 1,
                "notes": "Active daily user on macOS Desktop v2.4.1; 0 prior tickets.",
            },
            "messages": [
                {
                    "timestamp": "2025-03-10T14:40:00Z",
                    "text": "Hey team! Love the app—I use it every day on my MacBook. I noticed a small quirk in the macOS desktop app (v2.4.1): when I set Appearance to 'System Default', the app stays stuck on Light theme even when macOS switches to Dark Mode.",
                },
                {
                    "timestamp": "2025-03-10T14:42:00Z",
                    "text": "Also, out of curiosity, do you have any plans to add a custom scheduled dark mode (e.g., automatically turn on dark mode at 7 PM)? No rush at all 😊 just wanted to ask!",
                },
            ],
        },
    },
}


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
async def triage_endpoint(
    ticket: Annotated[SupportTicketInput, Body(openapi_examples=TICKET_OPENAPI_EXAMPLES)],
) -> TriageDecisionOutput:
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
