"""CLI and PORT-aware server entrypoint for the Support Ticket Triage Agent."""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import uvicorn
from openai import OpenAIError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.agent import triage_ticket
from src.config import OUTPUT_RESULTS_PATH, SAMPLE_TICKETS_PATH, get_openai_api_key, get_openai_model
from src.schemas import CustomerMetadata, SupportTicketInput, TicketMessage, TriageDecisionOutput, UrgencyLevel

console = Console()

URGENCY_COLORS: Dict[UrgencyLevel, str] = {
    UrgencyLevel.CRITICAL: "bold red",
    UrgencyLevel.HIGH: "bold yellow",
    UrgencyLevel.MEDIUM: "bold cyan",
    UrgencyLevel.LOW: "bold green",
}


def load_sample_tickets(path: Path = SAMPLE_TICKETS_PATH) -> List[SupportTicketInput]:
    """Load and validate sample support tickets from a JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        return [SupportTicketInput.model_validate(item) for item in json.load(handle)]


def build_custom_ticket(args: argparse.Namespace) -> SupportTicketInput:
    """Construct a SupportTicketInput from CLI flags or interactive terminal prompts."""
    if args.interactive and not args.message:
        console.print("[bold cyan]Interactive Custom Ticket Builder[/bold cyan]")
        tid = Prompt.ask("Ticket ID", default=args.ticket_id)
        plan = Prompt.ask("Customer Plan", choices=["Free", "Pro", "Enterprise"], default=args.plan)
        region = Prompt.ask("Region", default=args.region)
        seats = int(Prompt.ask("Seats", default=str(args.seats)))
        notes = Prompt.ask("Account Notes", default=args.notes)
        text = Prompt.ask("Customer Message")
    else:
        tid, plan, region, seats, notes, text = args.ticket_id, args.plan, args.region, args.seats, args.notes, args.message
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info = CustomerMetadata(plan=plan, tenure=args.tenure, region=region, seats=seats, notes=notes)
    return SupportTicketInput(ticket_id=tid, customer_info=info, messages=[TicketMessage(timestamp=now_iso, text=text)])


def render_ticket_decision(decision: TriageDecisionOutput) -> None:
    """Render a rich terminal panel summarizing a single ticket's triage result."""
    color = URGENCY_COLORS.get(decision.urgency, "white")
    info = decision.extracted_info
    body = (
        f"[bold]Urgency:[/bold] [{color}]{decision.urgency.value.upper()}[/{color}]    "
        f"[bold]Next Action:[/bold] [bold magenta]{decision.next_action.value}[/bold magenta]\n"
        f"[bold]Target Dept:[/bold] {decision.target_department}\n"
        f"[bold]Issue Type:[/bold] {info.issue_type} ({info.product_or_feature})\n"
        f"[bold]Sentiment:[/bold] {info.customer_sentiment}    [bold]Language:[/bold] {info.detected_language}\n"
        f"[bold]Tools Invoked:[/bold] {', '.join(decision.tools_invoked)}\n"
        f"[bold]KB Referenced:[/bold] {', '.join(decision.kb_articles_referenced)}\n\n"
        f"[bold underline]Reasoning:[/bold underline]\n{decision.reasoning}\n\n"
        f"[bold underline]Internal Handoff Summary:[/bold underline]\n{decision.internal_handoff_summary}\n\n"
        f"[bold underline]Draft Customer Response:[/bold underline]\n[italic]{decision.draft_customer_response}[/italic]"
    )
    console.print(Panel(body, title=f"[bold white]Ticket {decision.ticket_id} Triage Result[/bold white]", border_style=color, expand=False))


def render_summary_table(decisions: List[TriageDecisionOutput]) -> None:
    """Render an executive summary table of all triaged tickets."""
    table = Table(title="Support Ticket Triage Summary", show_lines=True)
    for col in ("Ticket ID", "Urgency", "Next Action", "Lang", "Tools Invoked", "KB Articles"):
        table.add_column(col)
    for item in decisions:
        color = URGENCY_COLORS.get(item.urgency, "white")
        table.add_row(
            f"[bold]{item.ticket_id}[/bold]", f"[{color}]{item.urgency.value.upper()}[/{color}]",
            f"[magenta]{item.next_action.value}[/magenta]", item.extracted_info.detected_language,
            ", ".join(item.tools_invoked), ", ".join(item.kb_articles_referenced),
        )
    console.print(table)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for sample batch run or custom/interactive ticket triage."""
    parser = argparse.ArgumentParser(description="Support Ticket Triage AI Agent CLI")
    parser.add_argument("-i", "--interactive", action="store_true", help="Prompt interactively for a custom ticket")
    parser.add_argument("-m", "--message", type=str, help="Custom customer support message to triage")
    parser.add_argument("--ticket-id", type=str, default="TCK-CUSTOM", help="Ticket ID (default: TCK-CUSTOM)")
    parser.add_argument("--plan", type=str, default="Pro", help="Customer plan: Free, Pro, Enterprise")
    parser.add_argument("--region", type=str, default="US", help="Customer region (e.g., US, Asia, Thailand)")
    parser.add_argument("--seats", type=int, default=1, help="Number of seats")
    parser.add_argument("--tenure", type=str, default="6 months", help="Customer tenure")
    parser.add_argument("--notes", type=str, default="Custom CLI ticket submission.", help="Account notes")
    parser.add_argument("--cli", action="store_true", help="Force CLI mode even when PORT is set")
    return parser.parse_args(argv)


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    """Execute the CLI triage pipeline across sample or custom tickets."""
    args = _parse_args(argv)
    if not get_openai_api_key():
        console.print(Panel("[bold red]Missing or placeholder OPENAI_API_KEY.[/bold red]\nCopy [bold].env.example[/bold] to [bold].env[/bold] and set a valid [bold]OPENAI_API_KEY[/bold].", title="Configuration Error", border_style="red"))
        return 1
    tickets = [build_custom_ticket(args)] if (args.interactive or args.message) else load_sample_tickets()
    console.print(f"[bold cyan]Running Support Ticket Triage Agent[/bold cyan] (model: [bold]{get_openai_model()}[/bold], tickets: {len(tickets)})\n")
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
    OUTPUT_RESULTS_PATH.write_text(json.dumps([d.model_dump(mode="json") for d in decisions], ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[bold green]Saved results to {OUTPUT_RESULTS_PATH}[/bold green]")
    return 0


if __name__ == "__main__":
    port = os.getenv("PORT", "").strip()
    if port and not any(flag in sys.argv for flag in ("--cli", "-i", "--interactive", "-m", "--message")):
        uvicorn.run("api:app", host="0.0.0.0", port=int(port))
    else:
        sys.exit(run_cli())
