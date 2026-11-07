"""Pydantic v2 data contracts and enums for the Support Ticket Triage Agent."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class TicketMessage(BaseModel):
    """A single message in a customer support ticket thread."""

    timestamp: str = Field(description="ISO-8601 timestamp of the message")
    text: str = Field(description="Raw message body sent by the customer")


class CustomerMetadata(BaseModel):
    """Account metadata attached to an incoming support ticket."""

    plan: str = Field(description="Subscription tier, e.g., Free, Pro, Enterprise")
    tenure: str = Field(description="Length of time the customer has held an account")
    region: str | None = Field(default="Global", description="Customer geographic region")
    seats: int | None = Field(default=1, description="Number of licensed seats")
    notes: str = Field(description="Account notes or CRM context")


class SupportTicketInput(BaseModel):
    """Validated input payload representing a customer support ticket."""

    ticket_id: str = Field(description="Unique ticket identifier, e.g., TCK-001")
    customer_info: CustomerMetadata = Field(description="Customer account metadata")
    messages: List[TicketMessage] = Field(
        min_length=1,
        description="Chronological list of customer messages in the thread",
    )


class UrgencyLevel(str, Enum):
    """Urgency classification levels for support ticket triage."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NextAction(str, Enum):
    """Routing and resolution action types for triaged tickets."""

    AUTO_RESPOND = "auto_respond"
    ROUTE_TO_SPECIALIST = "route_to_specialist"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ExtractedKeyInfo(BaseModel):
    """Structured signals extracted from the ticket thread and tool lookups."""

    product_or_feature: str = Field(description="Affected product area or feature")
    issue_type: str = Field(
        description="Category: Billing, Outage/Infra, Bug, Feature Request, Account"
    )
    customer_sentiment: str = Field(
        description="Current emotional state and progression across messages"
    )
    detected_language: str = Field(
        description="ISO language code of customer messages, e.g., 'en', 'th'"
    )


class TriageDecisionOutput(BaseModel):
    """Final structured triage decision emitted by the OpenAI Agent."""

    ticket_id: str = Field(description="Ticket ID matching the input payload")
    urgency: UrgencyLevel = Field(description="Classified urgency level")
    extracted_info: ExtractedKeyInfo = Field(
        description="Key entities and sentiment extracted from the ticket"
    )
    tools_invoked: List[str] = Field(
        description="Names of the tools called during triage"
    )
    kb_articles_referenced: List[str] = Field(
        description="IDs and titles of relevant KB docs found"
    )
    next_action: NextAction = Field(description="Recommended next workflow action")
    target_department: str = Field(
        description="e.g., Billing Team, Incident Response/SRE, Automated Tier-1"
    )
    reasoning: str = Field(
        description="Concise explanation linking evidence from tools + messages to the urgency and action"
    )
    draft_customer_response: str = Field(
        description="Empathetic reply in the customer's language"
    )
    internal_handoff_summary: str = Field(
        description="Actionable bulleted summary for internal staff"
    )
