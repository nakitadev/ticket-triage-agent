# Support Ticket Triage Agent

A production-grade **Support Ticket Triage AI Agent** built with Python 3.10+, the **OpenAI Agents SDK (`openai-agents`)**, and **Pydantic v2**. It ingests multi-message customer support threads, invokes deterministic tools to inspect billing logs, regional infrastructure health, and knowledge base articles, and outputs a strictly typed `TriageDecisionOutput`.

---

## 1. Quick Start (`uv` Recommended)

```bash
# 1. Sync dependencies using uv (or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)
uv sync

# 2. Configure environment variables
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY (and optional OPENAI_MODEL, default: gpt-4o-mini)

# 3. Run CLI Triage Pipeline (processes TCK-001, TCK-002, TCK-003 & writes output_results.json)
uv run python main.py

# 4. Run Offline Unit Test Suite (no API key required)
uv run pytest -v

# 5. Run Optional FastAPI Server (exposes /health and POST /api/v1/triage)
uv run uvicorn api:app --reload --port 8000
```

### Sample Expected Outcomes

| Ticket ID | Scenario Summary | Tools Invoked | Urgency | Next Action | Language |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`TCK-001`** | Free user, 3x `$29.99` pending charges, Pro Export locked, board presentation in 2 hrs, threatens bank dispute | `lookup_customer_and_billing`, `search_knowledge_base` (`KB-101`) | `critical` | `escalate_to_human` | English (`en`) |
| **`TCK-002`** | Thai Enterprise user (45 seats), HTTP 500 across browsers/coworkers, afternoon client demo, cached status page | `lookup_customer_and_billing`, `check_system_status` (`INC-904`), `search_knowledge_base` (`KB-205`) | `critical` | `escalate_to_human` | Thai (`th`) |
| **`TCK-003`** | Pro daily user on macOS v2.4.1, Dark Mode `'System Default'` sync bug + scheduled dark mode request ("No rush 😊") | `lookup_customer_and_billing`, `search_knowledge_base` (`KB-304`) | `low` | `auto_respond` | English (`en`) |

---

## 2. Brief Architecture Write-Up (<= 1 Page)

### 2.1 Architecture Decisions & Why
- **OpenAI Agents SDK + Pydantic v2 Structured Outputs:** We chose `openai-agents` (`Agent`, `Runner`, `@function_tool`) paired with `output_type=TriageDecisionOutput` over heavier graph-based frameworks. This provides native tool-calling loops and zero-boilerplate schema enforcement while keeping every module concise (< 150 lines), readable, and strictly typed.
- **Strict Separation of Concerns:** Configuration (`src/config.py`), data contracts (`src/schemas.py`), system rubrics (`src/prompts.py`), tool implementations (`src/tools.py`), and agent execution (`src/agent.py`) are isolated into dedicated modules.
- **Extensible Tool Registry & Transport Decoupling:** `src/tools.py` exports a single `TOOLS` list so registering a new tool requires zero modifications to `src/agent.py`. The core `triage_ticket()` / `triage_ticket_async()` runners are transport-agnostic, powering both the `rich` CLI (`main.py`) and the REST API (`api.py`), and can plug directly into webhook orchestrators (e.g., Zendesk, Intercom, or n8n) in production.

### 2.2 What Could Go Wrong & Mitigations
1. **Hallucinated KB Policies or Unverified Account Claims:**
   - *Mitigation:* The system prompt enforces a mandatory tool-first protocol (`lookup_customer_and_billing` and `search_knowledge_base` on every ticket; `check_system_status` on 500/outage reports). Outputs are locked to Pydantic `UrgencyLevel` and `NextAction` Enums, and `src/agent.py` deterministically reconciles `tools_invoked` against actual `RunResult.new_items` tool spans.
2. **Infinite Tool Loops & High Latency:**
   - *Mitigation:* `Runner.run` / `Runner.run_sync` is bounded by `max_turns=MAX_AGENT_TURNS` (10), and tools return deterministic JSON payloads even on missing keys so the model never retries failed lookups indefinitely.
3. **Upstream API Timeouts, Rate Limits, or Missing Credentials:**
   - *Mitigation:* `src/config.py`, `main.py`, and `api.py` validate `OPENAI_API_KEY` upfront and catch `OpenAIError` exceptions. In production, transient `429`/`5xx` errors use exponential backoff, and exhausted retries trigger a dead-letter fallback that routes the raw ticket to a human triage queue (`escalate_to_human`) so P1 issues are never dropped.
4. **Prompt Injection & Multilingual Drift:**
   - *Mitigation:* Customer messages are isolated inside `<support_ticket>` XML delimiters, all tools are strictly read-only, and explicit localization rules ensure replies match the customer's language (e.g., polite Thai for `TCK-002`).

### 2.3 Production Evaluation Strategy
1. **Offline Golden Dataset (CI/CD Gate):**
   - Maintain a curated benchmark of 200+ historical tickets across languages, plans, and edge cases. Track **Urgency Macro-F1 / Cohen's Kappa**, **Routing Accuracy**, **Tool Recall**, and **Critical Recall** (must be ~100% so P1 outages or chargeback threats are never auto-responded).
2. **Online Shadow Mode & Human-in-the-Loop Metrics:**
   - Deploy initially in shadow mode alongside human agents to measure **Human Agreement / Escalation Override Rate** (how often staff re-tag urgency or department) and **Draft Edit Distance** before enabling autonomous `auto_respond` on `low`-urgency tickets.
3. **LLM-as-a-Judge & Business/Operational KPIs:**
   - Run an asynchronous evaluator grading **KB Faithfulness** (zero fabricated workarounds) and **Tone/Localization Quality**, paired with operational SLAs (**P95 triage latency**, **token cost per ticket**, **chargeback prevention rate**, and **Enterprise P1 SLA compliance**).
