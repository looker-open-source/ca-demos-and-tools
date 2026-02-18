"""Factory for optional visualization sub-agent."""

from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig


def build_visualization_agent() -> LlmAgent:
    """Creates the optional visualization sub-agent."""
    return LlmAgent(
        name="visualization_render_agent",
        model="gemini-2.5-flash",
        description=(
            "Renders visualizations from CA API chart output using executable Python."
        ),
        instruction="""You are a data visualization expert.
Use only the CA API Vega config at {temp:chart_result_vega_config}.

Requirements:
1. Write self-contained Python with pandas + matplotlib.
2. Recreate a chart that matches the Vega config intent as closely as practical.
3. Ensure the code renders output (for example, via plt.show()).
4. Return a one-sentence interpretation after the code output.

Do not invent data; only use the provided Vega config.""",
        code_executor=BuiltInCodeExecutor(),
        planner=BuiltInPlanner(
            thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
        ),
    )
