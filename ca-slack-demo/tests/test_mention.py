"""Tests for @mention parsing."""

from src.slack.mention import parse_agent_mention, strip_bot_mention


class TestStripBotMention:
    def test_removes_bot_id(self):
        assert strip_bot_mention("<@U123ABC> hello", "U123ABC") == "hello"

    def test_preserves_other_mentions(self):
        result = strip_bot_mention("<@U123ABC> ask <@U999>", "U123ABC")
        assert result == "ask <@U999>"

    def test_no_mention(self):
        assert strip_bot_mention("just a message", "U123ABC") == "just a message"


class TestParseAgentMention:
    def test_thelook(self):
        agent, text = parse_agent_mention("@thelook how many orders?")
        assert agent == "thelook"
        assert text == "how many orders?"

    def test_stackoverflow(self):
        agent, text = parse_agent_mention("@stackoverflow top python tags")
        assert agent == "stackoverflow"
        assert text == "top python tags"

    def test_case_insensitive(self):
        agent, text = parse_agent_mention("@TheLook revenue?")
        assert agent == "thelook"

    def test_no_agent(self):
        agent, text = parse_agent_mention("how many orders?")
        assert agent is None
        assert text == "how many orders?"

    def test_agent_mid_sentence(self):
        agent, text = parse_agent_mention("ask @thelook about revenue")
        assert agent == "thelook"
        assert text == "ask about revenue"
