"""OpenAI Agents SDK initialization and execution wrappers for ticket triage."""

from typing import Any, List

from agents import Agent, RunResult, Runner

from src.config import MAX_AGENT_TURNS, get_openai_model
from src.prompts import TRIAGE_SYSTEM_PROMPT, format_ticket_prompt
from src.schemas import SupportTicketInput, TriageDecisionOutput
from src.tools import TOOLS


def create_triage_agent(model: str | None = None) -> Agent[Any]:
    """Create and configure the Support Ticket Triage Agent instance.

    Args:
        model: Optional model override. Defaults to the configured OPENAI_MODEL.

    Returns:
        Agent[Any]: Configured OpenAI Agent with tools and structured output schema.
    """
    return Agent(
        name="SupportTicketTriageAgent",
        model=model or get_openai_model(),
        instructions=TRIAGE_SYSTEM_PROMPT,
        tools=list(TOOLS),
        output_type=TriageDecisionOutput,
    )


def _normalize_tool_name(name: str) -> str:
    """Strip any 'functions.' prefix from a tool name."""
    return name.removeprefix("functions.").strip()


def _extract_invoked_tools(result: RunResult) -> List[str]:
    """Extract ordered, deduplicated tool names invoked during an agent run.

    Args:
        result: The RunResult returned by the OpenAI Agents SDK Runner.

    Returns:
        List[str]: Ordered list of unique tool names called during execution.
    """
    invoked: List[str] = []
    for item in getattr(result, "new_items", []):
        raw_item = getattr(item, "raw_item", None)
        name = getattr(raw_item, "name", None) or getattr(item, "name", None)
        if isinstance(name, str) and name:
            clean = _normalize_tool_name(name)
            if clean and clean not in invoked:
                invoked.append(clean)
    return invoked


def _finalize_decision(
    ticket: SupportTicketInput, result: RunResult
) -> TriageDecisionOutput:
    """Validate and enrich the final output from an agent run.

    Args:
        ticket: The original validated input ticket.
        result: The RunResult from the OpenAI Agents SDK Runner.

    Returns:
        TriageDecisionOutput: Validated structured triage output.
    """
    decision = TriageDecisionOutput.model_validate(result.final_output)
    decision.ticket_id = ticket.ticket_id
    observed_tools = _extract_invoked_tools(result)
    cleaned_llm_tools = [_normalize_tool_name(t) for t in decision.tools_invoked if t]
    merged = list(dict.fromkeys([*observed_tools, *cleaned_llm_tools]))
    if merged:
        decision.tools_invoked = merged
    return decision


def triage_ticket(
    ticket: SupportTicketInput | dict[str, Any],
    model: str | None = None,
) -> TriageDecisionOutput:
    """Synchronously triage a support ticket using the OpenAI Agents SDK.

    Args:
        ticket: A SupportTicketInput instance or raw ticket dictionary.
        model: Optional OpenAI model name override.

    Returns:
        TriageDecisionOutput: Strictly typed triage classification and response.
    """
    validated_ticket = SupportTicketInput.model_validate(ticket)
    agent = create_triage_agent(model=model)
    prompt = format_ticket_prompt(validated_ticket)
    result = Runner.run_sync(agent, input=prompt, max_turns=MAX_AGENT_TURNS)
    return _finalize_decision(validated_ticket, result)


async def triage_ticket_async(
    ticket: SupportTicketInput | dict[str, Any],
    model: str | None = None,
) -> TriageDecisionOutput:
    """Asynchronously triage a support ticket using the OpenAI Agents SDK.

    Args:
        ticket: A SupportTicketInput instance or raw ticket dictionary.
        model: Optional OpenAI model name override.

    Returns:
        TriageDecisionOutput: Strictly typed triage classification and response.
    """
    validated_ticket = SupportTicketInput.model_validate(ticket)
    agent = create_triage_agent(model=model)
    prompt = format_ticket_prompt(validated_ticket)
    result = await Runner.run(agent, input=prompt, max_turns=MAX_AGENT_TURNS)
    return _finalize_decision(validated_ticket, result)
