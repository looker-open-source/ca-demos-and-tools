#!/usr/bin/env python3
"""CLI test harness — test ADK routing + CA API without Slack.

Ask questions interactively and see which agent handles them.
"""

from __future__ import annotations

import asyncio
import logging

import click
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--log-level", default="INFO")
@click.option("--session-id", default="test-session", help="Reuse session for multi-turn")
@click.option("--user-id", default="test-user")
def main(log_level: str, session_id: str, user_id: str) -> None:
    """Interactive CLI to test agent routing."""
    load_dotenv()

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    from src.agents.root import root_agent

    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="test-cli",
        session_service=session_service,
    )

    async def run_loop() -> None:
        # Create session
        await session_service.create_session(
            app_name="test-cli",
            user_id=user_id,
            session_id=session_id,
        )

        console.print(Panel(
            "[bold]Slack Analytics Agents — Test CLI[/bold]\n"
            "Type a question to test routing. Use @thelook or @stackoverflow\n"
            "to force routing. Type 'quit' to exit.",
            title="Test Harness",
        ))

        while True:
            try:
                question = console.input("\n[bold cyan]You:[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                break

            if question.strip().lower() in ("quit", "exit", "q"):
                break

            content = types.Content(
                role="user",
                parts=[types.Part(text=question)],
            )

            console.print()
            agent_name = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if event.author and event.author != "data_router":
                    agent_name = event.author

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            prefix = "[bold green]%s:[/bold green] " % (agent_name or "agent")
                            console.print(prefix + part.text)
                        if part.function_response:
                            resp = part.function_response.response
                            if isinstance(resp, dict) and resp.get("generated_sql"):
                                console.print(
                                    "[dim]SQL: %s[/dim]" % resp["generated_sql"][:200]
                                )

    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
