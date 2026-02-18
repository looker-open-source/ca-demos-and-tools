"""Root agent for CA query + optional specialized sub-agents."""

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr
from typing_extensions import override

from ca_api_agent.agents import (
    CHART_RESULT_VEGA_CONFIG_STATE_KEY,
    build_conversational_analytics_query_agent,
    build_visualization_agent,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionalSubAgentSpec:
    """Configuration for deterministic optional sub-agent routing."""

    key: str
    description: str
    agent: BaseAgent
    run_when: Callable[[InvocationContext], bool]


class RootAgent(BaseAgent):
    """Runs the CA query agent first, then optional sub-agents by response shape."""

    name: str
    description: str = ""
    query_agent: BaseAgent
    _optional_sub_agents: list[OptionalSubAgentSpec] = PrivateAttr(default_factory=list)

    def __init__(
        self,
        name: str,
        description: str,
        query_agent: BaseAgent,
        optional_sub_agents: list[OptionalSubAgentSpec],
    ) -> None:
        init_data: dict[str, Any] = {
            "name": name,
            "description": description,
            "query_agent": query_agent,
        }
        super().__init__(**init_data)
        self._optional_sub_agents = optional_sub_agents

    @staticmethod
    def _has_non_empty_state(ctx: InvocationContext, key: str) -> bool:
        value = ctx.session.state.get(key)
        if value is None:
            return False
        if isinstance(value, (str, bytes, list, tuple, set, dict)):
            return len(value) > 0
        return bool(value)

    def _select_optional_sub_agents(self, ctx: InvocationContext) -> list[OptionalSubAgentSpec]:
        selected: list[OptionalSubAgentSpec] = []

        for spec in self._optional_sub_agents:
            try:
                if spec.run_when(ctx):
                    selected.append(spec)
            except Exception:  # pragma: no cover - defensive route guard
                logger.exception("Failed while evaluating routing rule for '%s'.", spec.key)
        return selected

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        async for event in self.query_agent.run_async(ctx):
            event.turn_complete = False
            yield event

        selected_agents = self._select_optional_sub_agents(ctx)
        if selected_agents:
            logger.info(
                "Optional sub-agents selected: %s",
                ", ".join(spec.key for spec in selected_agents),
            )
        else:
            logger.info("No optional sub-agents selected for this request.")

        for spec in selected_agents:
            status_content = types.Content(
                role="model",
                parts=[types.Part(text=f"Running optional step: {spec.description}")],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=False,
                invocation_id=ctx.invocation_id,
                content=status_content,
            )

            try:
                async for event in spec.agent.run_async(ctx):
                    event.turn_complete = False
                    yield event
            except Exception as err:  # pragma: no cover - defensive runtime guard
                logger.exception("Optional sub-agent '%s' failed.", spec.key)
                error_content = types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=(
                                f"Optional step '{spec.key}' failed with error: {err}. "
                                "Continuing with available results."
                            )
                        )
                    ],
                )
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=False,
                    invocation_id=ctx.invocation_id,
                    content=error_content,
                )

        yield Event(
            author=self.name,
            partial=False,
            turn_complete=True,
            invocation_id=ctx.invocation_id,
        )


data_query_agent = build_conversational_analytics_query_agent()
visualization_agent = build_visualization_agent()

# Add new optional sub-agents here to extend orchestration behavior.
optional_sub_agents = [
    OptionalSubAgentSpec(
        key="visualization",
        description="vega-config-driven visualization rendering",
        agent=visualization_agent,
        run_when=lambda ctx: RootAgent._has_non_empty_state(
            ctx, CHART_RESULT_VEGA_CONFIG_STATE_KEY
        ),
    ),
]

root_agent = RootAgent(
    name="root_agent",
    description=(
        "Top-level root agent. It always runs the CA query agent, then "
        "conditionally runs optional sub-agents based on response shape."
    ),
    query_agent=data_query_agent,
    optional_sub_agents=optional_sub_agents,
)
