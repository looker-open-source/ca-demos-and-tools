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
            "Creates plots from query data using Python, pandas, and matplotlib."
        ),
        instruction="""You are a data visualization expert. Your primary purpose is to create insightful and clear plots from data.
When you receive a request with data, your task is to:
1. Understand the data and the user's request for visualization.
2. Write Python code using pandas to prepare the data and matplotlib to generate a plot.
3. Ensure your code is self-contained and generates a visual output, for example by calling plt.show().
4. Along with the code that generates the plot, provide a brief, one-sentence summary of what the plot shows.

The code will be executed and the resulting plot will be displayed.
Here is the data: {temp:data_result}""",
        code_executor=BuiltInCodeExecutor(),
        planner=BuiltInPlanner(
            thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
        ),
    )
