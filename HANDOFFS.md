# Project Handoff Specification: Support Ticket Triage Agent

## 1. Project Overview & Objective
Build a production-grade **Support Ticket Triage AI Agent** in Python using the **OpenAI Agents SDK (`openai-agents`)** and **Pydantic (v2)**. 
The system ingests incoming customer support tickets (metadata + multi-message threads), invokes tools to gather context (billing/account status, infrastructure status, and knowledge base articles), and outputs a strictly typed triage decision.

### Evaluation Criteria (Strict Adherence Required)
1. **Readability:** Clean, self-documenting code, full Python type hints, modular layout, and rich CLI output.
2. **Maintainability:** Strict separation of concerns (schemas, tools, prompts, agent orchestration, and mock data must live in separate files).
3. **Extensibility:** Easy to register new `@function_tool` functions, swap OpenAI models via environment variables, or expose the core runner via CLI and REST API.
4. **Logic:** Deterministic rubric in the system prompt for urgency classification, tool verification before answering, and accurate routing decisions.

---

## 2. Technical Constraints & Stack
- **Language:** Python 3.10+
- **Core Framework:** `openai-agents` (OpenAI Agents SDK) + `openai`
- **Validation & Structured Outputs:** `pydantic>=2.0`
- **Configuration:** `python-dotenv` (Wait for user's `OPENAI_API_KEY` via `.env`. **NEVER hardcode API keys**).
- **Interfaces:**
  - **Primary (Required):** Terminal Console (`main.py`) using `rich` for clean, formatted console tables/panels and saving output to `output_results.json`.
  - **Secondary (Bonus for Extensibility):** FastAPI (`api.py`) exposing `POST /api/v1/triage`.

---

## 3. Target Directory Structure
The Coding Agent must generate the exact file structure below:

```text
support-ticket-triage-agent/
├── .env.example              # Template for OPENAI_API_KEY and OPENAI_MODEL
├── .gitignore                # Ignore .env, __pycache__, .venv, etc.
├── requirements.txt          # Pinned dependencies
├── README.md                 # Setup instructions + 1-page Architecture Write-up
├── main.py                   # CLI entry point (runs all 3 sample tickets)
├── api.py                    # FastAPI entry point (POST /api/v1/triage)
├── data/
│   ├── sample_tickets.json   # The 3 official test tickets from the prompt
│   ├── knowledge_base.json   # Mock FAQ & internal troubleshooting docs
│   └── mock_systems.json     # Mock customer DB, billing logs, and regional server status
├── src/
│   ├── __init__.py
│   ├── config.py             # Env loader (default model: gpt-4o-mini or gpt-4o)
│   ├── schemas.py            # Input & Output Pydantic models
│   ├── prompts.py            # System prompt with explicit triage rubric
│   ├── tools.py              # @function_tool definitions & mock data lookup logic
│   └── agent.py              # Agent initialization and execution wrapper
└── tests/
    └── test_triage.py        # Pytest suite verifying schemas, tools, and agent decisions
```

---

## 4. Data Contracts & Pydantic Schemas (`src/schemas.py`)

### 4.1 Input Schema
```python
from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class TicketMessage(BaseModel):
    timestamp: str
    text: str

class CustomerMetadata(BaseModel):
    plan: str
    tenure: str
    region: str | None = "Global"
    seats: int | None = 1
    notes: str

class SupportTicketInput(BaseModel):
    ticket_id: str
    customer_info: CustomerMetadata
    messages: List[TicketMessage]
```

### 4.2 Output Schema (`output_type` for the OpenAI Agent)
```python
class UrgencyLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class NextAction(str, Enum):
    AUTO_RESPOND = "auto_respond"
    ROUTE_TO_SPECIALIST = "route_to_specialist"
    ESCALATE_TO_HUMAN = "escalate_to_human"

class ExtractedKeyInfo(BaseModel):
    product_or_feature: str = Field(description="Affected product area or feature")
    issue_type: str = Field(description="Category: Billing, Outage/Infra, Bug, Feature Request, Account")
    customer_sentiment: str = Field(description="Current emotional state and progression across messages")
    detected_language: str = Field(description="ISO language code of customer messages, e.g., 'en', 'th'")

class TriageDecisionOutput(BaseModel):
    ticket_id: str
    urgency: UrgencyLevel
    extracted_info: ExtractedKeyInfo
    tools_invoked: List[str] = Field(description="Names of the tools called during triage")
    kb_articles_referenced: List[str] = Field(description="IDs and titles of relevant KB docs found")
    next_action: NextAction
    target_department: str = Field(description="e.g., Billing Team, Incident Response/SRE, Automated Tier-1")
    reasoning: str = Field(description="Concise explanation linking evidence from tools + messages to the urgency and action")
    draft_customer_response: str = Field(description="Empathetic reply in the customer's language")
    internal_handoff_summary: str = Field(description="Actionable bulleted summary for internal staff")
```

---

## 5. Tool Definitions & Mock Data Specification (`src/tools.py` & `data/`)
The agent must be equipped with **3 tools** decorated with `@function_tool`:

1. **`lookup_customer_and_billing(ticket_id: str) -> str`**
   - Queries `data/mock_systems.json` for account status, recent payment gateway logs, and SLA tier.
   - **Mock Data for Ticket 1:** Plan = `Free`, Upgrade Attempted = `True`, Billing Logs = `3x Pending authorizations of $29.99 (Gateway timeout on webhook, funds held, Pro entitlement not provisioned)`.
   - **Mock Data for Ticket 2:** Plan = `Enterprise`, Seats = `45`, Region = `Thailand (ap-southeast-1)`, SLA = `P1 Enterprise (15-min response time)`.
   - **Mock Data for Ticket 3:** Plan = `Pro`, App Version = `macOS Desktop v2.4.1`, Active Daily User = `True`, Previous Tickets = `0`.

2. **`check_system_status(region: str) -> str`**
   - Queries `data/mock_systems.json` for public vs. internal infrastructure health.
   - **Mock Data for `Asia` / `Thailand` / `ap-southeast-1`:** Public status page reads `All Systems Operational (cached)`, but Internal Telemetry shows `ACTIVE INCIDENT INC-904: API Gateway HTTP 500 spike in ap-southeast-1 starting 2 hours ago affecting Enterprise clusters`.
   - **Mock Data for `Global` / `US`:** `All systems healthy`.

3. **`search_knowledge_base(query: str) -> str`**
   - Performs case-insensitive keyword/token matching against `data/knowledge_base.json` and returns top matching articles.
   - **Required Mock KB Articles:**
     - `KB-101`: *Duplicate Pending Charges & Failed Pro Upgrades* — Instructs support to immediately escalate to Billing Specialist to manually provision temporary Pro access and void duplicate holds; warns that chargeback threats are high/critical priority.
     - `KB-205`: *HTTP 500 Outage & Regional API Gateway Troubleshooting* — Instructs immediate P1 escalation to On-Call SRE/Incident Response if multiple machines/browsers fail for an Enterprise tenant.
     - `KB-304`: *macOS Dark Mode 'System Default' Sync Bug & Feature Requests* — Known minor bug in macOS v2.4.1 where `System Default` stays on Light theme until the user toggles macOS appearance once or updates to v2.4.2. Scheduled Dark Mode is currently on the Q3 Product Roadmap (log as feature request).

---

## 6. System Prompt Logic Rubric (`src/prompts.py`)
The system prompt must instruct the agent to follow this strict workflow:
1. **Context Gathering (Mandatory):** Always call `lookup_customer_and_billing` and `search_knowledge_base` for every ticket. Call `check_system_status` whenever errors (e.g., 500), downtime, or regional issues are mentioned.
2. **Urgency Classification Matrix:**
   - `critical`: Production outage (HTTP 500) blocking multiple users/Enterprise tenants, multiple unauthorized/duplicate billing charges with chargeback/dispute threats, or imminent business-critical deadlines (< 4 hours, e.g., client demo or presentation).
   - `high`: Core feature broken for paid user without workaround, or non-critical billing errors.
   - `medium`: Partial functionality issue with a known workaround.
   - `low`: Cosmetic UI bugs (e.g., theme sync), general "how-to" questions, or feature requests with "no rush".
3. **Next Action Decision Rules:**
   - `escalate_to_human`: Required for all `critical` tickets (financial dispute risk, imminent deadline, or Enterprise outage).
   - `route_to_specialist`: Required for `high`/`medium` issues needing backend changes or manual billing adjustments without immediate crisis.
   - `auto_respond`: Permitted ONLY for `low` (or resolved `medium`) tickets where the Knowledge Base provides a complete, self-service solution/workaround.
4. **Localization:** Write `draft_customer_response` in the exact language used by the customer (English for Tickets 1 & 3; polite Thai for Ticket 2).

---

## 7. Acceptance Criteria & Test Plan (`tests/test_triage.py`)
The Coding Agent must verify that running the agent against the 3 sample tickets produces outputs matching the table below:

| Test Case | Input Summary | Expected Tool Calls (Min 2) | Expected `urgency` | Expected `next_action` | Key Verification Checks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ticket 1** (`TCK-001`) | Free user, 3x $29.99 pending charges, no Pro access, presentation in 2 hrs, threatens bank dispute. | `lookup_customer_and_billing`, `search_knowledge_base` | `critical` (or `high`) | `escalate_to_human` (or `route_to_specialist`) | • Identifies billing/duplicate charge + Export feature<br>• Captures angry/escalating sentiment<br>• References `KB-101` |
| **Ticket 2** (`TCK-002`) | Thai Enterprise user (45 seats), Error 500 across browsers/coworkers, major client demo this afternoon, asks about Asia region. | `lookup_customer_and_billing`, `check_system_status`, `search_knowledge_base` | `critical` | `escalate_to_human` | • Detects unannounced Asia (`ap-southeast-1`) outage (`INC-904`)<br>• References `KB-205`<br>• `draft_customer_response` is written in Thai (`th`) |
| **Ticket 3** (`TCK-003`) | Pro daily user, Dark mode 'System Default' not syncing on Mac, asks for scheduled dark mode ("No rush 😊"). | `lookup_customer_and_billing`, `search_knowledge_base` | `low` | `auto_respond` | • Identifies minor macOS theme bug + feature request<br>• Captures friendly/curious sentiment<br>• References `KB-304` workaround (v2.4.2 / toggle) |

---

## 8. Deliverable Requirements (`README.md` + 1-Page Write-up)
The `README.md` must be concise, well-formatted (tables + bullet points, zero fluff), and contain:
1. **Quick Start Guide:** Virtual environment setup, `pip install -r requirements.txt`, configuring `.env`, running `python main.py`, running `pytest`, and starting the optional FastAPI server (`uvicorn api:app --reload`).
2. **Brief Write-Up (Strictly <= 1 Page):**
   - **Architecture Decisions & Why:** Why `openai-agents` + Pydantic v2 was chosen over heavier graph frameworks (low boilerplate, high readability, native structured outputs, strict type safety) and how the core runner decouples from CLI/FastAPI (and could easily plug into workflow orchestrators like n8n in production).
   - **What Could Go Wrong & Mitigations:**
     1. *Infinite Tool Loops / High Latency:* Mitigated via `max_turns` limit in `Runner.run` and strict tool docstrings.
     2. *Hallucinated Policies or Actions:* Mitigated by forcing tool execution before synthesis and locking outputs to Pydantic Enums.
     3. *API Timeouts / Rate Limits:* Handled via retry/backoff wrappers and a fallback safe-mode that routes unprocessable tickets to a human queue.
     4. *Prompt Injection in Ticket Text:* Mitigated by isolating customer text inside structured XML/JSON delimiters and enforcing read-only tool permissions.
   - **Production Evaluation Strategy:**
     1. *Offline Golden Dataset (CI/CD):* Regression suite measuring Urgency & Action accuracy (Macro-F1 / Cohen's Kappa against human labels) and Critical Recall (must be ~100% so P1 outages are never auto-responded).
     2. *Online Shadow Mode & Human-in-the-Loop:* Track escalation override rate (how often humans change the AI's triage tag) and draft edit distance.
     3. *LLM-as-a-Judge & Operational Metrics:* Automated scoring for tone/hallucination against KB articles, alongside P95 latency and token cost per ticket.