"""Tests for Slack Block Kit message builders."""

import pytest
from src.slack.blocks import (
    format_answer_blocks,
    help_blocks,
    thinking_blocks,
    _clean_for_slack,
    _strip_sql_fences,
    _text_to_blocks,
)


class TestFormatAnswerBlocks:
    def test_starts_with_context_header_when_agent_named(self):
        blocks = format_answer_blocks(text="42 orders", agent_name="TheLook")
        assert blocks[0]["type"] == "context"
        assert "TheLook" in blocks[0]["elements"][0]["text"]

    def test_divider_follows_header(self):
        blocks = format_answer_blocks(text="42 orders", agent_name="TheLook")
        assert blocks[1]["type"] == "divider"

    def test_answer_text_in_section(self):
        blocks = format_answer_blocks(text="42 orders", agent_name="TheLook")
        section = next(b for b in blocks if b["type"] == "section")
        assert "42 orders" in section["text"]["text"]

    def test_no_header_when_no_agent_name(self):
        blocks = format_answer_blocks(text="hello")
        assert blocks[0]["type"] == "section"

    def test_latency_shown_in_footer(self):
        blocks = format_answer_blocks(text="42", latency_ms=1500)
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert any("1.5s" in b["elements"][0]["text"] for b in context_blocks)

    def test_no_footer_when_zero_latency(self):
        blocks = format_answer_blocks(text="42", latency_ms=0)
        # Only header context block if agent_name given, no latency footer
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert not any(
            any(c.get("type") == "mrkdwn" and "s" in c.get("text", "") and "." in c.get("text", "")
                for c in b.get("elements", []))
            for b in context_blocks
        )

    def test_sql_fences_stripped_from_answer(self):
        text = "Here is the answer.\n```sql\nSELECT 1\n```\nDone."
        blocks = format_answer_blocks(text=text)
        section = next(b for b in blocks if b["type"] == "section")
        assert "SELECT" not in section["text"]["text"]
        assert "Here is the answer." in section["text"]["text"]

    def test_long_answer_splits_into_multiple_sections(self):
        long_text = ("word " * 600).strip()
        blocks = format_answer_blocks(text=long_text)
        sections = [b for b in blocks if b["type"] == "section"]
        assert len(sections) >= 2

    def test_markdown_bold_converted(self):
        blocks = format_answer_blocks(text="**Total:** 42 orders")
        section = next(b for b in blocks if b["type"] == "section")
        assert "*Total:*" in section["text"]["text"]

    def test_agent_emoji_included_in_header(self):
        blocks = format_answer_blocks(
            text="result", agent_name="NCAA", agent_emoji=":basketball:"
        )
        header = blocks[0]["elements"][0]["text"]
        assert ":basketball:" in header


class TestThinkingBlocks:
    def test_returns_single_section(self):
        blocks = thinking_blocks()
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"

    def test_contains_thinking_text(self):
        blocks = thinking_blocks()
        assert "Thinking" in blocks[0]["text"]["text"]


class TestHelpBlocks:
    def test_has_header(self):
        blocks = help_blocks()
        assert any(b["type"] == "header" for b in blocks)

    def test_has_divider(self):
        blocks = help_blocks()
        assert any(b["type"] == "divider" for b in blocks)

    def test_contains_tips(self):
        blocks = help_blocks()
        all_text = " ".join(
            b["text"]["text"] for b in blocks if b.get("text", {}).get("type") == "mrkdwn"
        )
        assert "Tips" in all_text or "tip" in all_text.lower()


class TestStripSqlFences:
    def test_removes_sql_block(self):
        result = _strip_sql_fences("Answer.\n```sql\nSELECT 1\n```\nDone.")
        assert "SELECT" not in result
        assert "Answer." in result
        assert "Done." in result

    def test_leaves_non_sql_fences(self):
        result = _strip_sql_fences("```python\nprint('hi')\n```")
        assert "print" in result

    def test_handles_no_fences(self):
        result = _strip_sql_fences("plain text")
        assert result == "plain text"


class TestCleanForSlack:
    def test_bold_conversion(self):
        assert "*bold*" in _clean_for_slack("**bold**")

    def test_headers_bolded(self):
        result = _clean_for_slack("### Section Title")
        assert "*Section Title*" in result

    def test_markdown_table_becomes_code_block(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = _clean_for_slack(table)
        assert "```" in result
        assert "A" in result

    def test_strips_sql_fences(self):
        result = _clean_for_slack("text ```sql\nSELECT 1\n``` more text")
        assert "SELECT" not in result


class TestTextToBlocks:
    def test_short_text_is_single_block(self):
        blocks = _text_to_blocks("short")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"

    def test_long_text_splits(self):
        long_text = "x " * 1500
        blocks = _text_to_blocks(long_text)
        assert len(blocks) >= 2
        for b in blocks:
            assert len(b["text"]["text"]) <= 2900  # allow small overage for word boundary

    def test_each_block_is_mrkdwn_section(self):
        blocks = _text_to_blocks("hello world")
        for b in blocks:
            assert b["type"] == "section"
            assert b["text"]["type"] == "mrkdwn"
