"""Agent function tools and dynamic JSON data loaders for ticket triage."""

import json
import re
from pathlib import Path
from typing import Any, Callable, List, TypeVar

from agents import function_tool
from agents.tool import FunctionTool

from src.config import KNOWLEDGE_BASE_PATH, MOCK_SYSTEMS_PATH

T = TypeVar("T")


class CallableFunctionTool(FunctionTool):
    """FunctionTool subclass that remains directly callable for unit testing."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the underlying Python function directly."""
        return self.__wrapped__(*args, **kwargs)


def _make_callable_tool(func: Callable[..., str]) -> CallableFunctionTool:
    """Wrap a function with @function_tool while preserving direct callability.

    Args:
        func: The tool function to decorate.

    Returns:
        CallableFunctionTool: An OpenAI Agents SDK FunctionTool that is also callable.
    """
    tool = function_tool(func)
    tool.__class__ = CallableFunctionTool
    return tool  # type: ignore[return-value]


def _load_json(path: Path) -> Any:
    """Load and parse a JSON file from disk.

    Args:
        path: Path to the JSON file.

    Returns:
        Any: Parsed JSON data structure.
    """
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@_make_callable_tool
def lookup_customer_and_billing(ticket_id: str) -> str:
    """Look up customer account status, payment gateway logs, and SLA tier by ticket ID.

    Args:
        ticket_id: The unique support ticket identifier (e.g., 'TCK-001').

    Returns:
        str: JSON-formatted customer account and billing telemetry record.
    """
    systems_data: dict[str, Any] = _load_json(MOCK_SYSTEMS_PATH)
    customers: dict[str, Any] = systems_data.get("customers", {})
    normalized_id = ticket_id.strip().upper()
    record = customers.get(normalized_id)
    if not record:
        return json.dumps(
            {"error": f"No customer or billing record found for ticket_id '{ticket_id}'."}
        )
    return json.dumps(record, ensure_ascii=False, indent=2)


@_make_callable_tool
def check_system_status(region: str) -> str:
    """Check public status page vs. internal infrastructure telemetry for a region.

    Args:
        region: Geographic region or AWS zone (e.g., 'Asia', 'Thailand', 'ap-southeast-1', 'US').

    Returns:
        str: JSON-formatted public and internal infrastructure health status.
    """
    systems_data: dict[str, Any] = _load_json(MOCK_SYSTEMS_PATH)
    status_map: dict[str, Any] = systems_data.get("system_status", {})
    normalized = region.strip().lower()

    asia_aliases = ("asia", "thailand", "ap-southeast-1", "apac", "bangkok", "th")
    if any(alias in normalized for alias in asia_aliases):
        return json.dumps(status_map.get("asia", {}), ensure_ascii=False, indent=2)

    return json.dumps(status_map.get("global", {}), ensure_ascii=False, indent=2)


@_make_callable_tool
def search_knowledge_base(query: str) -> str:
    """Search the support knowledge base using case-insensitive keyword/token overlap.

    Args:
        query: Search keywords describing the issue (e.g., 'duplicate charge pro upgrade').

    Returns:
        str: JSON-formatted list of matching KB articles ordered by relevance score.
    """
    articles: List[dict[str, Any]] = _load_json(KNOWLEDGE_BASE_PATH)
    tokens = [
        tok for tok in re.findall(r"[a-z0-9.\-]+", query.lower()) if len(tok) > 1
    ]
    if not tokens:
        return json.dumps(articles, ensure_ascii=False, indent=2)

    scored: List[tuple[int, dict[str, Any]]] = []
    for article in articles:
        haystack = " ".join(
            [
                str(article.get("id", "")),
                str(article.get("title", "")),
                str(article.get("category", "")),
                " ".join(article.get("keywords", [])),
                str(article.get("summary", "")),
                " ".join(article.get("resolution_steps", [])),
            ]
        ).lower()
        keyword_set = {k.lower() for k in article.get("keywords", [])}
        score = sum(3 if tok in keyword_set else (1 if tok in haystack else 0) for tok in tokens)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda item: item[0], reverse=True)
    matched = [item[1] for item in scored] if scored else articles
    return json.dumps(matched, ensure_ascii=False, indent=2)


TOOLS: List[FunctionTool] = [
    lookup_customer_and_billing,
    check_system_status,
    search_knowledge_base,
]
