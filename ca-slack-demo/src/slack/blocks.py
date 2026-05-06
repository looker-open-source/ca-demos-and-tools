"""Build Slack Block Kit messages from agent responses."""

from __future__ import annotations

import re
from typing import Any

from src.config import AGENT_CONFIGS

# Slack section blocks cap out at 3000 chars
_MAX_BLOCK_TEXT = 2800
# Max table rows to show before truncating
_MAX_TABLE_ROWS = 8


def _parse_md_table(table_lines: list[str]) -> list[list[str]]:
    """Parse markdown table lines into a list of cell-lists, skipping separator rows."""
    rows = []
    for line in table_lines:
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
            continue  # separator row
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def _render_table(rows: list[list[str]], max_rows: int = _MAX_TABLE_ROWS) -> str:
    """Render parsed table rows as a fixed-width monospace code block."""
    truncated = len(rows) > max_rows + 1  # +1 for header
    display = rows[:max_rows + 1]
    if not display:
        return ""

    num_cols = max(len(r) for r in display)
    widths = [0] * num_cols
    for row in display:
        for i, cell in enumerate(row):
            if i < num_cols:
                widths[i] = max(widths[i], len(cell))

    lines = []
    for i, row in enumerate(display):
        padded = [
            (row[j] if j < len(row) else "").ljust(widths[j])
            for j in range(num_cols)
        ]
        lines.append("  ".join(padded).rstrip())
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))

    if truncated:
        lines.append("... %d more rows" % (len(rows) - max_rows - 1))

    return "```\n%s\n```" % "\n".join(lines)


def _strip_sql_fences(text: str) -> str:
    """Remove ```sql ... ``` blocks — SQL is shown separately in its own message."""
    return re.sub(r"```sql\b.*?```", "", text, flags=re.DOTALL).strip()


def _clean_for_slack(text: str) -> str:
    """Convert markdown to Slack mrkdwn and trim unsupported constructs.

    - Strips embedded ```sql``` blocks (shown separately)
    - **bold** → *bold*
    - _italic_ and *italic* preserved as-is (already valid mrkdwn)
    - ### headers → *bold*
    - Markdown tables → fixed-width code block
    - Long answers split by caller into multiple blocks; this fn doesn't truncate
    """
    text = _strip_sql_fences(text)

    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    lines = text.splitlines()
    result_parts: list[str] = []
    table_buffer: list[str] = []

    def flush_table() -> None:
        if table_buffer:
            rows = _parse_md_table(table_buffer)
            if rows:
                result_parts.append(_render_table(rows))
            table_buffer.clear()

    for line in lines:
        if re.match(r"^\s*\|", line):
            table_buffer.append(line)
            continue

        flush_table()

        header_match = re.match(r"^#{1,3}\s+(.*)", line)
        if header_match:
            result_parts.append("*%s*" % header_match.group(1))
            continue

        result_parts.append(line)

    flush_table()
    return "\n".join(result_parts)


def _text_to_blocks(text: str) -> list[dict[str, Any]]:
    """Split a long cleaned text into multiple section blocks (≤ _MAX_BLOCK_TEXT each)."""
    blocks = []
    while text:
        chunk = text[:_MAX_BLOCK_TEXT]
        # Don't cut mid-word
        if len(text) > _MAX_BLOCK_TEXT:
            cut = chunk.rfind("\n")
            if cut > _MAX_BLOCK_TEXT // 2:
                chunk = text[:cut]
        text = text[len(chunk):].lstrip("\n")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": chunk},
        })
    return blocks


def format_answer_blocks(
    text: str,
    agent_emoji: str = ":bar_chart:",
    agent_name: str = "",
    latency_ms: int = 0,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an agent answer."""
    blocks: list[dict[str, Any]] = []

    # Header with agent identity
    if agent_name:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "%s *%s*" % (agent_emoji, agent_name)}],
        })
        blocks.append({"type": "divider"})

    # Main answer — converted and split into multiple blocks if needed
    cleaned = _clean_for_slack(text)
    blocks.extend(_text_to_blocks(cleaned))

    # Footer: latency
    footer_parts = []
    if latency_ms:
        footer_parts.append("%.1fs" % (latency_ms / 1000))
    if footer_parts:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " · ".join(footer_parts)}],
        })

    return blocks


def thinking_blocks() -> list[dict[str, Any]]:
    """Block Kit blocks for the 'Thinking...' placeholder."""
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":hourglass_flowing_sand: Thinking..."},
        }
    ]


def help_blocks() -> list[dict[str, Any]]:
    """Block Kit blocks for the @ca-bot-demo help response."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Conversational Analytics"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Ask natural language questions about any of the datasets below. "
                    "I'll figure out which one you mean, write the SQL, run it against BigQuery, "
                    "and return an answer — with a chart when it makes sense.\n\n"
                    "Powered by Google's *Conversational Analytics API* + *Gemini*."
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Available datasets*"},
        },
    ]

    for cfg in AGENT_CONFIGS.values():
        if not cfg.agent_id:
            continue
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "%s *%s*\n%s" % (cfg.emoji, cfg.display_name, cfg.description),
            },
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Tips*\n"
                    "• Follow-up questions in the same thread reuse the same conversation\n"
                    # "• Force a specific dataset: `@ca-bot-demo @thelook what were top products?`\n"
                    "• Questions can span multiple turns: ask a broad question, then drill down\n"
                    "• The bot interprets the time horizon of the question and determines the right agent to use for querying"
                ),
            },
        },
    ]

    return blocks
