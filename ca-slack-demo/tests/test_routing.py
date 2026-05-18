"""Integration tests for the ADK agent routing layer.

Verifies the root agent correctly routes questions to the right sub-agent.
CA tool calls are allowed to run (and will fail gracefully with stub IDs)
since we only inspect event.author, not the tool result.

Run with:
    uv run pytest tests/test_routing.py -v -m integration

Requires GCP credentials for the Gemini routing model. CA agent IDs can be
stubs — routing only needs the model, not real CA agents.
"""

import os

import pytest

pytestmark = pytest.mark.integration


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires real GCP credentials")


@pytest.fixture(scope="module", autouse=True)
def require_env():
    required = ["GCP_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "ROUTER_MODEL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip("Missing env vars for routing tests: %s" % ", ".join(missing))

    # Ensure all agents are registered even without real CA agent IDs
    stubs = {
        "CA_AGENT_THELOOK": "stub",
        "CA_AGENT_STACKOVERFLOW": "stub",
        "CA_AGENT_NCAA": "stub",
        "CA_AGENT_CENSUS": "stub",
        "CA_AGENT_GA4": "stub",
        "CA_AGENT_GA360": "stub",
    }
    for k, v in stubs.items():
        os.environ.setdefault(k, v)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("AGENT_MODEL", os.environ.get("ROUTER_MODEL", ""))


@pytest.fixture(scope="module")
def runner():
    """One Runner shared across all routing tests in this module."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from src.agents.root import root_agent

    svc = InMemorySessionService()
    return Runner(agent=root_agent, app_name="test-routing", session_service=svc), svc


@pytest.mark.asyncio
@pytest.mark.parametrize("question,expected_agent", [
    ("How many orders were placed last month?", "thelook"),
    ("What are the top Python tags on Stack Overflow?", "stackoverflow"),
    ("Which team won March Madness in 2019?", "ncaa"),
    ("What is the median household income in California?", "census"),
    ("How many purchase events happened last week?", "ga4"),
])
async def test_routing_selects_correct_agent(question, expected_agent, runner):
    """Root agent routes each question to the expected sub-agent.

    We capture the first non-router author and treat it as the routing decision.
    The CA tool call that follows will fail with stub agent IDs, but that doesn't
    affect the routing assertion.
    """
    from google.genai import types

    r, svc = runner
    user_id = "test-user"
    session_id = "routing-%s" % expected_agent

    existing = await svc.get_session(
        app_name="test-routing", user_id=user_id, session_id=session_id,
    )
    if existing is None:
        await svc.create_session(
            app_name="test-routing", user_id=user_id, session_id=session_id,
        )

    content = types.Content(role="user", parts=[types.Part(text=question)])
    routed_to: str | None = None

    async for event in r.run_async(
        user_id=user_id, session_id=session_id, new_message=content,
    ):
        if event.author and event.author not in ("data_router", "") and routed_to is None:
            routed_to = event.author
            break  # we have our routing decision; don't wait for CA to finish

    assert routed_to is not None, "No routing event received — router may have failed"
    assert routed_to == expected_agent, (
        "Expected routing to %r, got %r for: %r" % (expected_agent, routed_to, question)
    )
