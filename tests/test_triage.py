"""Unit and integration test suite for schemas, tools, agent wrapper, and FastAPI."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import app
from main import load_sample_tickets
from src.agent import triage_ticket
from src.config import get_openai_api_key
from src.schemas import (
    ExtractedKeyInfo,
    NextAction,
    SupportTicketInput,
    TriageDecisionOutput,
    UrgencyLevel,
)
from src.tools import (
    TOOLS,
    check_system_status,
    lookup_customer_and_billing,
    search_knowledge_base,
)


@pytest.fixture
def sample_tickets_by_id() -> Dict[str, SupportTicketInput]:
    """Return validated sample tickets indexed by ticket_id."""
    return {ticket.ticket_id: ticket for ticket in load_sample_tickets()}


def _mock_decision(
    ticket_id: str,
    urgency: UrgencyLevel,
    action: NextAction,
    lang: str,
    tools: List[str],
    kb: str,
    reply: str,
) -> TriageDecisionOutput:
    """Create a deterministic TriageDecisionOutput fixture for unit tests."""
    return TriageDecisionOutput(
        ticket_id=ticket_id,
        urgency=urgency,
        extracted_info=ExtractedKeyInfo(
            product_or_feature="Core Platform",
            issue_type="Support",
            customer_sentiment="Urgent" if urgency == UrgencyLevel.CRITICAL else "Friendly",
            detected_language=lang,
        ),
        tools_invoked=tools,
        kb_articles_referenced=[kb],
        next_action=action,
        target_department="Support Team",
        reasoning=f"Verified via {kb} and system tools.",
        draft_customer_response=reply,
        internal_handoff_summary=f"- Ticket {ticket_id} triaged as {urgency.value}",
    )


def test_sample_tickets_and_schema_validation(
    sample_tickets_by_id: Dict[str, SupportTicketInput],
) -> None:
    """Verify sample tickets load cleanly and invalid urgency enums are rejected."""
    assert list(sample_tickets_by_id.keys()) == ["TCK-001", "TCK-002", "TCK-003"]
    with pytest.raises(ValidationError):
        SupportTicketInput.model_validate({"ticket_id": "BAD", "customer_info": {}, "messages": []})
    with pytest.raises(ValidationError):
        TriageDecisionOutput.model_validate({"ticket_id": "TCK-001", "urgency": "super_urgent"})


@pytest.mark.parametrize(
    "ticket_id, expected_plan, expected_snippet",
    [
        ("TCK-001", "Free", "3x Pending authorizations of $29.99"),
        ("TCK-002", "Enterprise", "P1 Enterprise"),
        ("TCK-003", "Pro", "macOS Desktop v2.4.1"),
    ],
)
def test_lookup_customer_and_billing_tool(
    ticket_id: str, expected_plan: str, expected_snippet: str
) -> None:
    """Verify lookup_customer_and_billing returns accurate billing/SLA data per ticket."""
    raw = lookup_customer_and_billing(ticket_id)
    assert json.loads(raw)["plan"] == expected_plan and expected_snippet in raw
    assert "error" in json.loads(lookup_customer_and_billing("TCK-999"))


@pytest.mark.parametrize(
    "region, expected_telemetry",
    [("Thailand (ap-southeast-1)", "INC-904"), ("Asia", "INC-904"), ("US", "All systems healthy")],
)
def test_check_system_status_tool(region: str, expected_telemetry: str) -> None:
    """Verify check_system_status detects active Asia incident INC-904 vs healthy Global status."""
    assert expected_telemetry in json.loads(check_system_status(region))["internal_telemetry"]


@pytest.mark.parametrize(
    "query, expected_kb_id",
    [
        ("duplicate pending charges 29.99 pro upgrade export", "KB-101"),
        ("HTTP 500 error outage Asia enterprise gateway", "KB-205"),
        ("macOS dark mode System Default sync scheduled", "KB-304"),
    ],
)
def test_search_knowledge_base_tool(query: str, expected_kb_id: str) -> None:
    """Verify token overlap search ranks KB-101, KB-205, and KB-304 first for relevant queries."""
    assert json.loads(search_knowledge_base(query))[0]["id"] == expected_kb_id and len(TOOLS) == 3


def test_agent_and_api_triage_workflow_mocked(
    sample_tickets_by_id: Dict[str, SupportTicketInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify triage_ticket and FastAPI endpoint enforce contracts across all 3 ticket scenarios."""
    expected = {
        "TCK-001": _mock_decision("TCK-001", UrgencyLevel.CRITICAL, NextAction.ESCALATE_TO_HUMAN, "en", ["lookup_customer_and_billing", "search_knowledge_base"], "KB-101", "Escalating duplicate holds."),
        "TCK-002": _mock_decision("TCK-002", UrgencyLevel.CRITICAL, NextAction.ESCALATE_TO_HUMAN, "th", ["lookup_customer_and_billing", "check_system_status", "search_knowledge_base"], "KB-205", "ขออภัยในความไม่สะดวกครับ กำลังแก้ไข INC-904 ครับ"),
        "TCK-003": _mock_decision("TCK-003", UrgencyLevel.LOW, NextAction.AUTO_RESPOND, "en", ["lookup_customer_and_billing", "search_knowledge_base"], "KB-304", "Update to v2.4.2; scheduled dark mode is on Q3 roadmap!"),
    }
    for tid, mock_out in expected.items():
        fake_run = SimpleNamespace(final_output=mock_out, new_items=[SimpleNamespace(raw_item=SimpleNamespace(name=n)) for n in mock_out.tools_invoked])
        with patch("src.agent.Runner.run_sync", return_value=fake_run):
            res = triage_ticket(sample_tickets_by_id[tid])
            assert res.ticket_id == tid and res.urgency == mock_out.urgency and res.next_action == mock_out.next_action

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-valid-key")
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    with patch("api.triage_ticket_async", new=AsyncMock(return_value=expected["TCK-002"])):
        resp = client.post("/api/v1/triage", json=sample_tickets_by_id["TCK-002"].model_dump())
        assert resp.status_code == 200 and "ครับ" in resp.json()["draft_customer_response"]


@pytest.mark.skipif(not get_openai_api_key(), reason="Requires live OPENAI_API_KEY")
def test_live_agent_triage_all_sample_tickets(sample_tickets_by_id: Dict[str, SupportTicketInput]) -> None:
    """Run live end-to-end verification against OpenAI when OPENAI_API_KEY is present."""
    r1, r2, r3 = (triage_ticket(sample_tickets_by_id[k]) for k in ("TCK-001", "TCK-002", "TCK-003"))
    assert r1.urgency in {UrgencyLevel.CRITICAL, UrgencyLevel.HIGH}
    assert r2.urgency == UrgencyLevel.CRITICAL and r3.next_action == NextAction.AUTO_RESPOND
