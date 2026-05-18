"""Parse @mentions from Slack message text."""

from __future__ import annotations

import re

from src.config import AGENT_CONFIGS

# Matches @agentname (plain text, not Slack's <@U123> user mention format)
_AGENT_MENTION_RE = re.compile(
    r"@(" + "|".join(re.escape(name) for name in AGENT_CONFIGS) + r")\b",
    re.IGNORECASE,
)


def strip_bot_mention(text: str, bot_user_id: str) -> str:
    """Remove the <@BOT_ID> mention that Slack inserts for app_mention events."""
    return re.sub(r"<@%s>\s*" % re.escape(bot_user_id), "", text).strip()


def parse_agent_mention(text: str) -> tuple[str | None, str]:
    """Extract an explicit @agentname mention from the message.

    Returns (agent_name, cleaned_text) where agent_name is None if no
    explicit agent was mentioned.
    """
    match = _AGENT_MENTION_RE.search(text)
    if match:
        agent_name = match.group(1).lower()
        cleaned = text[: match.start()] + text[match.end() :]
        return agent_name, re.sub(r" {2,}", " ", cleaned).strip()
    return None, text
