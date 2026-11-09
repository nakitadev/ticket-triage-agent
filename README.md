# Support Ticket Triage Agent

A production-grade **Support Ticket Triage AI Agent** built with Python 3.10+, the official **OpenAI Agents SDK (`openai-agents`)**, and **Pydantic v2** structured outputs.

The agent ingests multi-message customer support threads, invokes deterministic verification tools (customer billing history, regional system health telemetry, and knowledge base documentation), and outputs a strictly typed triage decision (`critical` / `high` / `medium` / `low` urgency, routing actions, and localized response drafts).

---

## 1. Prerequisites & System Requirements

Before setting up the project, ensure you have the following installed on your machine:

- **Python:** Version 3.10 or higher (tested on Python 3.12)
- **OpenAI API Key:** An active key with access to `gpt-4o-mini` (or `gpt-4o`)
- **Package Manager (Choose one):**
  - **`uv` (Recommended):** Ultra-fast Python package installer and resolver. If not installed, you can install it via:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
  - **Standard `pip` & `venv`:** Python's built-in virtual environment manager.

---

## 2. Installation & Setup

### Option A: Using `uv` (Recommended)

```bash
# 1. Clone the repository and enter the directory
cd ticket-triage-agent

# 2. Sync all project dependencies into an isolated environment
uv sync

# 3. Configure your environment variables
cp .env.example .env
# Edit .env and insert your OpenAI API key:
# OPENAI_API_KEY=sk-...
```

### Option B: Using Standard Python `venv` + `pip`

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# 2. Upgrade pip and install the package with dependencies
pip install --upgrade pip
pip install -e .

# 3. Configure your environment variables
cp .env.example .env
# Edit .env and insert your OpenAI API key
```

---

## 3. How to Run

### 3.1 CLI Triage Runner
Processes all sample customer support tickets and outputs an interactive table with tool invocation traces and results:

```bash
# With uv
uv run python main.py

# With standard virtualenv
python main.py
```

### 3.2 Running Automated Unit Tests
Executes the comprehensive test suite (unit tests with mocked tool providers run offline without consuming OpenAI API credits):

```bash
# With uv
uv run pytest -v

# With standard virtualenv
pytest -v
```

### 3.3 REST API Service (Optional)
Starts the asynchronous FastAPI microservice exposing HTTP endpoints for ticket ingestion:

```bash
# With uv
uv run uvicorn api:app --reload --port 8000

# With standard virtualenv
uvicorn api:app --reload --port 8000
```

Once running, access interactive OpenAPI documentation at: `http://localhost:8000/docs`
- `GET  /health` — Service liveness check
- `POST /api/v1/triage` — Ingest support ticket thread and return structured decision

---

## 4. Sample Ticket Scenarios & Verified Outcomes

| Ticket ID | Scenario Context | Tools Invoked | Urgency | Action | Verified Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`TCK-001`** | Free user, 3x `$29.99` pending charges, Pro locked, presentation in 2 hours | `lookup_customer_and_billing`, `search_knowledge_base` | `CRITICAL` | `escalate_to_human` | Overrides Free plan trap; immediately routed to Billing Specialist |
| **`TCK-002`** | Enterprise Thai client (45 seats), HTTP 500 error, client demo this afternoon | `lookup_customer_and_billing`, `check_system_status` | `CRITICAL` | `escalate_to_human` | Discovers internal INC-904 Asia regional incident; drafts formal Thai reply |
| **`TCK-003`** | Pro user on macOS, Dark Mode system default sync issue + auto-schedule request | `lookup_customer_and_billing`, `search_knowledge_base` | `LOW` | `auto_respond` | Provides KB-304 self-service workaround; records product backlog idea |

---

## 5. Project Structure

```text
ticket-triage-agent/
├── api.py                                              # FastAPI REST microservice (/api/v1/triage)
├── main.py                                             # CLI runner with rich console outputs
├── pyproject.toml                                      # Project metadata, dependencies & tool configs
├── README.md                                           # Setup, execution & documentation guide
├── src/
│   ├── __init__.py
│   ├── agent.py                                        # OpenAI Agents SDK runner & execution loop
│   ├── config.py                                       # Settings & environment variable validation
│   ├── prompts.py                                      # Grounding prompt & localization guardrails
│   ├── schemas.py                                      # Pydantic v2 data models & Enums
│   └── tools.py                                        # Deterministic tools (Billing, Status, KB)
└── tests/
    ├── __init__.py
    ├── conftest.py                                     # Pytest fixtures and mock tools
    └── test_triage.py                                  # Test suite (Unit, Schemas, Tools & Agent)
```
