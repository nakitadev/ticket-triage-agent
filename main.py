"""CLI and PORT-aware server entrypoint for the Support Ticket Triage Agent."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import uvicorn
from openai import OpenAIError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agent import triage_ticket
from src.config import (
    OUTPUT_RESULTS_PATH,
    SAMPLE_TICKETS_PATH,
    get_openai_api_key,
    get_openai_model,
)
from src.schemas import SupportTicketInput, TriageDecisionOutput, UrgencyLevel

console = Console()

URGENCY_COLORS: Dict[UrgencyLevel, str] = {
    UrgencyLevel.CRITICAL: "bold red",
    UrgencyLevel.HIGH: "bold yellow",
    UrgencyLevel.MEDIUM: "bold cyan",
    UrgencyLevel.LOW: "bold green",
}


def load_sample_tickets(path: Path = SAMPLE_TICKETS_PATH) -> List[SupportTicketInput]:
    """Load and validate sample support tickets from a JSON file.

    :param path: Path to the sample tickets JSON file.
    :return: Validated list of support ticket inputs.
    """
    with path.open("r", encoding="utf-8") as handle:
        return [SupportTicketInput.model_validate(item) for item in json.load(handle)]


def render_ticket_decision(decision: TriageDecisionOutput) -> None:
    """Render a rich terminal panel summarizing a single ticket's triage result.

    :param decision: The structured triage decision output from the agent.
    """
    color = URGENCY_COLORS.get(decision.urgency, "white")
    info = decision.extracted_info
    body = (
        f"[bold]Urgency:[/bold] [{color}]{decision.urgency.value.upper()}[/{color}]    "
        f"[bold]Next Action:[/bold] [bold magenta]{decision.next_action.value}[/bold magenta]\n"
        f"[bold]Target Dept:[/bold] {decision.target_department}\n"
        f"[bold]Issue Type:[/bold] {info.issue_type} ({info.product_or_feature})\n"
        f"[bold]Sentiment:[/bold] {info.customer_sentiment}    "
        f"[bold]Language:[/bold] {info.detected_language}\n"
        f"[bold]Tools Invoked:[/bold] {', '.join(decision.tools_invoked)}\n"
        f"[bold]KB Referenced:[/bold] {', '.join(decision.kb_articles_referenced)}\n\n"
        f"[bold underline]Reasoning:[/bold underline]\n{decision.reasoning}\n\n"
        f"[bold underline]Internal Handoff Summary:[/bold underline]\n"
        f"{decision.internal_handoff_summary}\n\n"
        f"[bold underline]Draft Customer Response:[/bold underline]\n"
        f"[italic]{decision.draft_customer_response}[/italic]"
    )
    console.print(
        Panel(
            body,
            title=f"[bold white]Ticket {decision.ticket_id} Triage Result[/bold white]",
            border_style=color,
            expand=False,
        )
    )


def render_summary_table(decisions: List[TriageDecisionOutput]) -> None:
    """Render an executive summary table of all triaged tickets.

    :param decisions: List of completed triage decisions.
    """
    table = Table(title="Support Ticket Triage Summary", show_lines=True)
    columns = ("Ticket ID", "Urgency", "Next Action", "Lang", "Tools Invoked", "KB Articles")
    for col in columns:
        table.add_column(col)

    for item in decisions:
        color = URGENCY_COLORS.get(item.urgency, "white")
        table.add_row(
            f"[bold]{item.ticket_id}[/bold]",
            f"[{color}]{item.urgency.value.upper()}[/{color}]",
            f"[magenta]{item.next_action.value}[/magenta]",
            item.extracted_info.detected_language,
            ", ".join(item.tools_invoked),
            ", ".join(item.kb_articles_referenced),
        )
    console.print(table)


def run_cli() -> int:
    """Execute the CLI triage pipeline across all sample tickets.

    :return: Process exit code (0 for success, 1 for configuration/runtime error).
    """
    if not get_openai_api_key():
        console.print(
            Panel(
                "[bold red]Missing or placeholder OPENAI_API_KEY.[/bold red]\n"
                "Copy [bold].env.example[/bold] to [bold].env[/bold] and set a valid "
                "[bold]OPENAI_API_KEY[/bold] before running [bold]uv run python main.py[/bold].",
                title="Configuration Error",
                border_style="red",
            )
        )
        return 1

    tickets = load_sample_tickets()
    console.print(
        f"[bold cyan]Running Support Ticket Triage Agent[/bold cyan] "
        f"(model: [bold]{get_openai_model()}[/bold], tickets: {len(tickets)})\n"
    )
    decisions: List[TriageDecisionOutput] = []
    try:
        for ticket in tickets:
            with console.status(f"[bold green]Triaging {ticket.ticket_id}..."):
                decision = triage_ticket(ticket)
            decisions.append(decision)
            render_ticket_decision(decision)
    except (OpenAIError, Exception) as exc:
        console.print(Panel(f"[bold red]Triage error:[/bold red] {exc}", border_style="red"))
        return 1

    render_summary_table(decisions)
    payload = [d.model_dump(mode="json") for d in decisions]
    OUTPUT_RESULTS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console.print(f"\n[bold green]Saved results to {OUTPUT_RESULTS_PATH}[/bold green]")
    return 0


if __name__ == "__main__":
    port = os.getenv("PORT", "").strip()
    if port and "--cli" not in sys.argv:
        uvicorn.run("api:app", host="0.0.0.0", port=int(port))
    else:
        sys.exit(run_cli())
