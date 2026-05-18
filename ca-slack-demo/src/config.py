"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AgentConfig:
    """Static configuration for one CA-backed sub-agent."""

    name: str
    display_name: str
    agent_id: str
    description: str
    keywords: list[str] = field(default_factory=list)
    emoji: str = ":bar_chart:"


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError("Missing required env var: %s" % key)
    return val


# --- GCP ---
GCP_PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "")
GCP_LOCATION: str = os.environ.get("GCP_LOCATION", "global")

# --- Slack ---
SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN: str = os.environ.get("SLACK_APP_TOKEN", "")

# --- ADK ---
ROUTER_MODEL: str = os.environ.get("ROUTER_MODEL", "gemini-2.5-pro")
AGENT_MODEL: str = os.environ.get("AGENT_MODEL", "gemini-2.5-pro")

# --- Chart rendering ---
CHART_RENDER_SCALE: float = float(os.environ.get("CHART_RENDER_SCALE", "2.0"))

# --- Agent registry ---
AGENT_CONFIGS: dict[str, AgentConfig] = {
    "thelook": AgentConfig(
        name="thelook",
        display_name="TheLook E-Commerce",
        agent_id=os.environ.get("CA_AGENT_THELOOK", ""),
        description="Specializes in e-commerce data analysis for TheLook store. Use for orders, products, inventory, and customer metrics.",
        keywords=["ecommerce", "orders", "products", "customers"],
        emoji=":shopping_bags:",
    ),
}
