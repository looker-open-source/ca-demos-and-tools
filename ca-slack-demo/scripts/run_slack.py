#!/usr/bin/env python3
"""Start the Slack analytics bot."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from dotenv import load_dotenv
from rich.logging import RichHandler


@click.command()
@click.option("--log-level", default="INFO", help="Logging level")
def main(log_level: str) -> None:
    """Start the Slack analytics bot in Socket Mode."""
    load_dotenv()

    import os
    
    if os.environ.get("K_SERVICE"):
        handlers = [logging.StreamHandler(sys.stdout)]
        log_format = "%(levelname)s - %(name)s - %(message)s"
    else:
        handlers = [RichHandler(rich_tracebacks=True)]
        log_format = "%(message)s"

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers,
    )

    # Import after dotenv so config picks up env vars
    from src.config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN

    if not SLACK_BOT_TOKEN:
        click.echo("Error: SLACK_BOT_TOKEN not set", err=True)
        sys.exit(1)
    if not SLACK_APP_TOKEN:
        click.echo("Error: SLACK_APP_TOKEN not set (needed for Socket Mode)", err=True)
        sys.exit(1)

    from src.slack.app import start

    asyncio.run(start())


if __name__ == "__main__":
    main()
