#!/usr/bin/env python3
"""Provision CA API agents for each dataset.

Creates or updates agents with context from the context/ directory.
Prints the agent IDs to add to .env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ca_client import CAClient
from config import AGENT_CONFIGS, GCP_LOCATION, GCP_PROJECT_ID

console = Console()
CONTEXT_DIR = Path(__file__).parent.parent / "context"


def _load_context(agent_name: str) -> dict:
    """Load context.json for an agent, stripping _meta."""
    context_path = CONTEXT_DIR / agent_name / "context.json"
    if not context_path.exists():
        raise FileNotFoundError("No context at %s" % context_path)
    with context_path.open() as fh:
        ctx = json.load(fh)
    ctx.pop("_meta", None)
    return ctx


@click.command()
@click.option(
    "--agent",
    "agent_names",
    multiple=True,
    help="Specific agent(s) to provision. Default: all in registry.",
)
@click.option(
    "--create/--update",
    default=True,
    help="Create new agent (default) or update existing.",
)
@click.option("--dry-run", is_flag=True, help="Show what would be done without calling API.")
def main(agent_names: tuple[str, ...], create: bool, dry_run: bool) -> None:
    """Provision CA API agents with context from context/ directory."""
    if not GCP_PROJECT_ID:
        console.print("[red]Error: GCP_PROJECT_ID not set[/red]")
        sys.exit(1)

    targets = list(agent_names) if agent_names else list(AGENT_CONFIGS.keys())

    table = Table(title="Agent Provisioning Plan")
    table.add_column("Agent")
    table.add_column("Context Path")
    table.add_column("Action")
    table.add_column("Status")

    results: list[tuple[str, str]] = []

    for name in targets:
        context_path = CONTEXT_DIR / name / "context.json"
        action = "create" if create else "update"

        if not context_path.exists():
            table.add_row(name, str(context_path), action, "[yellow]no context.json[/yellow]")
            continue

        if dry_run:
            table.add_row(name, str(context_path), action, "[dim]dry run[/dim]")
            continue

        try:
            ctx = _load_context(name)
            client = CAClient(project_id=GCP_PROJECT_ID, location=GCP_LOCATION)

            if create:
                agent_id = name  # Use agent name as ID
                resource_name = asyncio.run(client.create_agent(agent_id, ctx))
                table.add_row(name, str(context_path), "create", "[green]created[/green]")
                results.append((name, agent_id))
            else:
                config = AGENT_CONFIGS.get(name)
                if not config or not config.agent_id:
                    table.add_row(
                        name, str(context_path), "update",
                        "[red]no agent_id in config[/red]",
                    )
                    continue
                asyncio.run(client.update_agent_published(config.agent_id, ctx))
                table.add_row(name, str(context_path), "update", "[green]updated[/green]")
                results.append((name, config.agent_id))

        except Exception as exc:
            table.add_row(name, str(context_path), action, "[red]%s[/red]" % exc)

    console.print(table)

    if results:
        console.print("\n[bold]Add to .env:[/bold]")
        for name, agent_id in results:
            env_key = "CA_AGENT_%s" % name.upper()
            console.print("  %s=%s" % (env_key, agent_id))


if __name__ == "__main__":
    main()
