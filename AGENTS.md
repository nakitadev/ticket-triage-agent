# AGENT.md — Autonomous Coding Agent Instructions

## 1. Role & Mission
You are an expert Staff AI Engineer building the **Support Ticket Triage Agent** take-home assignment.
Your source of truth for schemas, mock data, and business logic is `HANDOFF.md`.
Your skill and mcp of the specific knowledges are in .agents directory
Your code will be graded strictly on **Readability**, **Maintainability**, **Extensibility**, and **Logic**.

## 2. Tech Stack & Environment
- **Python:** 3.10+
- **Core SDK:** `openai-agents` (OpenAI Agents SDK) & `openai`
- **Data Validation:** `pydantic>=2.0`
- **CLI & API:** `rich` (for terminal output), `fastapi` + `uvicorn` (for optional API), `python-dotenv`
- **Testing:** `pytest`, `pytest-asyncio`

## 3. Essential Commands
- **Install dependencies:** `pip install -r requirements.txt`
- **Run CLI (Primary Deliverable):** `python main.py`
- **Run Unit Tests (Offline/Mocked):** `pytest -v`
- **Run API Server (Bonus):** `uvicorn api:app --reload --port 8000`

## 4. Coding Standards (The 4 Grading Pillars)
1. **Readability:**
   - Every function, method, and tool MUST have explicit Python type hints and concise Google-style docstrings.
   - Keep files under 150 lines each. Avoid deeply nested `if/else` blocks.
2. **Maintainability:**
   - Enforce strict separation of concerns:
     - `src/config.py`: Env loading & constants (NEVER hardcode `OPENAI_API_KEY`).
     - `src/schemas.py`: Pure Pydantic models & Enums only.
     - `src/prompts.py`: System prompt templates & rubrics only.
     - `src/tools.py`: `@function_tool` implementations & JSON file loaders.
     - `src/agent.py`: `Agent` definition and `Runner.run_sync` / `Runner.run` execution wrapper.
3. **Extensibility:**
   - Load data dynamically from `data/*.json` using `pathlib.Path` relative to project root.
   - Export a clean `TOOLS = [lookup_customer_and_billing, check_system_status, search_knowledge_base]` list in `src/tools.py` so adding a 4th tool requires zero changes to `src/agent.py`.
4. **Logic & Safety:**
   - Always validate incoming ticket dicts with `SupportTicketInput` before passing to the agent.
   - Enforce `output_type=TriageDecisionOutput` on the OpenAI `Agent` instance.
   - Add graceful error handling in `main.py` if `OPENAI_API_KEY` is missing or invalid.

## 5. Step-by-Step Implementation Plan
Execute these steps in order. Do not skip steps.

### Step 1: Project Scaffolding & Config
- Create `.gitignore`, `.env.example`, and `requirements.txt` (`openai-agents`, `openai`, `pydantic`, `python-dotenv`, `rich`, `fastapi`, `uvicorn`, `pytest`).
- Implement `src/config.py` to load `OPENAI_API_KEY` and `OPENAI_MODEL` (default to `"gpt-4o-mini"` or `"gpt-4o"`).

### Step 2: Mock Data Files (`data/`)
- Create `data/sample_tickets.json` containing the exact 3 tickets from the assignment prompt (`TCK-001`, `TCK-002`, `TCK-003`).
- Create `data/mock_systems.json` with customer records (Free w/ 3x $29.99 pending charges, Enterprise 45 seats in Thailand, Pro on macOS v2.4.1) and regional status (`Asia` having active HTTP 500 API Gateway incident `INC-904` vs cached public status).
- Create `data/knowledge_base.json` with `KB-101` (duplicate charges/pro upgrade), `KB-205` (Enterprise 500 outage escalation), and `KB-304` (macOS dark mode sync bug & scheduled dark mode roadmap).

### Step 3: Schemas & Tools (`src/schemas.py` & `src/tools.py`)
- Implement `SupportTicketInput` and `TriageDecisionOutput` (with `UrgencyLevel` and `NextAction` Enums) in `src/schemas.py`.
- Implement the 3 tools in `src/tools.py` using `@function_tool` from `agents`:
  1. `lookup_customer_and_billing(ticket_id: str) -> str`
  2. `check_system_status(region: str) -> str`
  3. `search_knowledge_base(query: str) -> str` (use token/keyword overlap scoring so multi-word queries reliably match relevant KB articles).

### Step 4: System Prompt & Agent (`src/prompts.py` & `src/agent.py`)
- Write `TRIAGE_SYSTEM_PROMPT` in `src/prompts.py` enforcing:
  - Mandatory tool usage (`lookup_customer_and_billing` + `search_knowledge_base` on every ticket; `check_system_status` on outages/500 errors).
  - Urgency Matrix (`critical` for outages, duplicate charges + dispute threats, or <4h deadlines; `low` for minor UI bugs/feature requests).
  - Action Rules (`escalate_to_human` for critical, `route_to_specialist` for specialized non-crisis, `auto_respond` for low-urgency with KB solution).
  - Language matching (`draft_customer_response` MUST be in Thai for `TCK-002` and English for `TCK-001`/`TCK-003`).
- In `src/agent.py`, create `triage_ticket(ticket: SupportTicketInput) -> TriageDecisionOutput` using `Agent` and `Runner.run_sync`.

### Step 5: CLI, API, and Tests (`main.py`, `api.py`, `tests/`)
- `main.py`: Load `data/sample_tickets.json`, run all 3 tickets through `triage_ticket()`, render formatted panels/tables via `rich`, and dump results to `output_results.json`.
- `api.py`: Expose `POST /api/v1/triage` accepting `SupportTicketInput` and returning `TriageDecisionOutput`.
- `tests/test_triage.py`: Write deterministic unit tests for all 3 tool functions and schema validation (must pass without requiring a live `OPENAI_API_KEY`), plus an optional `@pytest.mark.skipif` live integration test.

### Step 6: Documentation (`README.md`)
- Include quickstart setup commands (`venv`, `pip install`, `.env`, `python main.py`).
- Include the **Brief Write-up ( strictly <= 1 page )** covering:
  1. **Architecture Decisions & Why:** OpenAI Agents SDK + Pydantic Structured Outputs for zero-boilerplate readability and strict type safety; modular tool registry.
  2. **Failure Modes & Mitigations:** Hallucinated KB policies (grounded via tool outputs), infinite tool loops (`max_turns` guard), API timeouts/rate limits (retries + fallback queue), and multilingual edge cases.
  3. **Production Evaluation Strategy:** Offline golden dataset (Urgency F1, Routing Accuracy), Online shadow-mode human agreement rate, Chargeback/SLA breach prevention rate, and LLM-as-a-judge for response tone/faithfulness.

## 6. Definition of Done (Self-Check Before Completing)
- [ ] All files in the target directory structure exist and have clean imports.
- [ ] `pytest` passes 100% of unit tests locally.
- [ ] Ticket 1 resolves to `critical` (or `high`) urgency and `escalate_to_human` (or `route_to_specialist`).
- [ ] Ticket 2 resolves to `critical` urgency, `escalate_to_human`, calls `check_system_status`, and replies in Thai.
- [ ] Ticket 3 resolves to `low` urgency and `auto_respond` with KB-304 workaround.
- [ ] No API keys or secrets are hardcoded anywhere in the repository.
