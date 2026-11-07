"""Environment configuration and path constants for the Support Ticket Triage Agent."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
SAMPLE_TICKETS_PATH: Path = DATA_DIR / "sample_tickets.json"
MOCK_SYSTEMS_PATH: Path = DATA_DIR / "mock_systems.json"
KNOWLEDGE_BASE_PATH: Path = DATA_DIR / "knowledge_base.json"
OUTPUT_RESULTS_PATH: Path = PROJECT_ROOT / "output_results.json"

DEFAULT_MODEL: str = "gpt-4o-mini"
MAX_AGENT_TURNS: int = 10


def get_openai_model() -> str:
    """Return the configured OpenAI model name from the environment.

    Returns:
        str: The model identifier to use for the triage agent.
    """
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip()
    return model or DEFAULT_MODEL


def get_openai_api_key() -> Optional[str]:
    """Retrieve the OpenAI API key from the environment if valid.

    Returns:
        Optional[str]: The configured API key, or None if missing or a placeholder.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-your-"):
        return None
    return api_key
