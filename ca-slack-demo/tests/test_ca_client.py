"""Integration tests for CAClient — require real GCP credentials and CA agent IDs.

Run with:
    uv run pytest tests/test_ca_client.py -v -m integration

Skipped automatically when CA_AGENT_THELOOK and GCP_PROJECT_ID are not set.
"""

import os

import pytest

pytestmark = pytest.mark.integration


def _skip_if_not_configured():
    if not os.environ.get("GCP_PROJECT_ID") or not os.environ.get("CA_AGENT_THELOOK"):
        pytest.skip("GCP_PROJECT_ID and CA_AGENT_THELOOK required for integration tests")


@pytest.fixture(autouse=True)
def require_env():
    _skip_if_not_configured()


@pytest.fixture
def client():
    from src.ca_client import CAClient
    return CAClient()


@pytest.mark.asyncio
async def test_create_conversation(client):
    """CA API creates a conversation and returns a resource name."""
    agent_id = os.environ["CA_AGENT_THELOOK"]
    conv_id = await client.create_conversation(agent_id)
    assert conv_id.startswith("projects/")
    assert "conversations/" in conv_id


@pytest.mark.asyncio
async def test_chat_returns_text_answer(client):
    """A real question against TheLook returns a non-empty text answer."""
    agent_id = os.environ["CA_AGENT_THELOOK"]
    response = await client.chat(agent_id=agent_id, question="How many orders are there in total?")
    assert response.error is None, f"CA API returned error: {response.error}"
    assert response.text_answer, "Expected a text answer, got none"
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_chat_returns_sql(client):
    """CA API includes generated SQL for a quantitative question."""
    agent_id = os.environ["CA_AGENT_THELOOK"]
    response = await client.chat(agent_id=agent_id, question="What is the total revenue?")
    assert response.error is None
    assert response.generated_sql, "Expected SQL in response"
    assert "SELECT" in response.generated_sql.upper()


@pytest.mark.asyncio
async def test_chat_multi_turn_reuses_conversation(client):
    """Follow-up question in the same conversation builds on the first answer."""
    agent_id = os.environ["CA_AGENT_THELOOK"]

    first = await client.chat(agent_id=agent_id, question="How many orders are there?")
    assert first.error is None
    assert first.conversation_id

    second = await client.chat(
        agent_id=agent_id,
        question="Break that down by status.",
        conversation_id=first.conversation_id,
    )
    assert second.error is None
    assert second.text_answer


@pytest.mark.asyncio
async def test_chat_progress_callbacks_fire(client):
    """on_progress callback receives at least one milestone during a real query."""
    agent_id = os.environ["CA_AGENT_THELOOK"]
    progress_steps: list[str] = []

    async def on_progress(label: str) -> None:
        progress_steps.append(label)

    response = await client.chat(
        agent_id=agent_id,
        question="How many orders are there?",
        on_progress=on_progress,
    )
    assert response.error is None
    # CA streams at least one progress label (Planning, SQL generation, etc.)
    assert len(progress_steps) >= 1


@pytest.mark.asyncio
async def test_chat_bad_agent_returns_not_found_error(client):
    """An invalid agent ID returns a structured 'not_found' error, not an exception."""
    response = await client.chat(agent_id="nonexistent-agent-id-xyz", question="test")
    assert response.error is not None
    assert response.error.startswith("not_found") or response.error.startswith("permission_denied")
