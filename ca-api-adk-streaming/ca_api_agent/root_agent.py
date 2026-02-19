# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Root agent for deterministic CA-first orchestration with optional sub-agents."""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, cast

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import PrivateAttr
from typing_extensions import override

from ca_api_agent.agents import (
    DATA_RESULT_STATE_KEY,
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
    """Always runs CA first, then conditionally runs optional sub-agents."""

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

    def _select_optional_sub_agents(
        self, ctx: InvocationContext
    ) -> list[OptionalSubAgentSpec]:
        selected: list[OptionalSubAgentSpec] = []

        for spec in self._optional_sub_agents:
            try:
                if spec.run_when(ctx):
                    selected.append(spec)
            except Exception:  # pragma: no cover - defensive route guard
                logger.exception("Failed while evaluating routing rule for '%s'.", spec.key)
        return selected

    @staticmethod
    def _as_non_terminal(event: Event) -> Event:
        """Returns a copy of the event marked as non-terminal for orchestration streaming."""
        if not event.turn_complete:
            return event
        copy_fn = getattr(event, "model_copy", None)
        if callable(copy_fn):
            return cast(Event, copy_fn(update={"turn_complete": False}))
        event.turn_complete = False
        return event

    @staticmethod
    def _strip_code_blocks(text: str) -> str:
        return re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    @staticmethod
    def _sanitize_visualization_content(
        content: types.Content | None,
    ) -> types.Content | None:
        if not content or not content.parts:
            return content

        sanitized_parts: list[types.Part] = []
        for part in content.parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                mime_type = getattr(inline_data, "mime_type", None) or "image/png"
                if mime_type.startswith("image/"):
                    b64_data = base64.b64encode(inline_data.data).decode("ascii")
                    sanitized_parts.append(
                        types.Part(text=f"![chart](data:{mime_type};base64,{b64_data})")
                    )
                    continue

            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                cleaned = RootAgent._strip_code_blocks(text).strip()
                if cleaned:
                    sanitized_parts.append(types.Part(text=cleaned))

        if not sanitized_parts:
            return None
        return types.Content(role=content.role, parts=sanitized_parts)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        async for event in self.query_agent.run_async(ctx):
            yield self._as_non_terminal(event)

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
                    forward_event = event
                    if spec.key == "visualization":
                        sanitized_content = self._sanitize_visualization_content(
                            event.content
                        )
                        if sanitized_content is None:
                            continue
                        copy_fn = getattr(event, "model_copy", None)
                        if callable(copy_fn):
                            forward_event = cast(
                                Event, copy_fn(update={"content": sanitized_content})
                            )
                        else:
                            event.content = sanitized_content
                            forward_event = event
                    yield self._as_non_terminal(forward_event)
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
        description="data-result-driven visualization rendering",
        agent=visualization_agent,
        run_when=lambda ctx: RootAgent._has_non_empty_state(ctx, DATA_RESULT_STATE_KEY),
    ),
]

root_agent = RootAgent(
    name="root_agent",
    description=(
        "Top-level deterministic root agent. It always runs the CA query agent, then "
        "conditionally runs optional sub-agents based on response shape."
    ),
    query_agent=data_query_agent,
    optional_sub_agents=optional_sub_agents,
)

__all__ = ["root_agent"]
