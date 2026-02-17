# Conversational Analytics API Agent

This agent leverages the Gemini Conversational Analytics API to answer questions about business analytics. It can be run locally or deployed to Agent Engine.

## Folder Structure

- `ca_api_agent/`: This folder contains the core agent logic.
  - `agent.py`: This file defines the `CaApiAgent` and the `root_agent`. The `CaApiAgent` is a custom agent class that inherits from the ADK's `BaseAgent`. It overrides the `_run_async_impl` method to support tool streaming, which allows the agent to process data from the Conversational Analytics API in real-time. The agent uses a simple client ID and secret for Looker authentication. It also saves the summary and raw data results to the agent's temporary session, which makes them accessible to subsequent agents in the same invocation.
- `deployment/`: This folder contains the deployment script and the wheel file for the agent.
  - `deploy.py`: This script handles the deployment of the agent to Agent Engine. It can create or delete an agent.
  - `ca_api_agent-0.1.0-py3-none-any.whl`: The wheel file for the agent. This is created by running `uv build --format=wheel --output-dir=deployment`.

## Running the Agent Locally

1.  **Install the dependencies:**

    ```bash
    uv sync --frozen
    ```

2.  **Enter virtual environment:**

    ```bash
    source .venv/bin/activate
    ```

3.  **Set the environment variables:**
    Create a `.env` file in the root of the `ca-api-agent` directory and add the following environment variables:

    ```
    GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
    GOOGLE_CLOUD_LOCATION=<your-gcp-location>
    GOOGLE_GENAI_USE_VERTEXAI=1
    LOOKERSDK_CLIENT_ID=<your-looker-client-id>
    LOOKERSDK_CLIENT_SECRET=<your-looker-client-secret>
    LOOKERSDK_BASE_URL=<your-looker-base-url>
    LOOKML_MODEL=<your-lookml-model>
    LOOKML_EXPLORE=<your-lookml-explore>
    ```

4.  **Run the agent:**
    ```bash
    adk web
    ```

## Building and Deploying to Agent Engine

This agent can be deployed to Agent Engine using the provided `deploy.sh` script.

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- [uv](https://github.com/astral-sh/uv)

### Deployment Steps

1.  **Configure the `.env` file:**
    Make sure the `.env` file in the root of the `ca-api-agent` directory contains the correct values for your environment.

2.  **Run the deployment script:**
    ```bash
    ./deploy.sh
    ```

The script will then:

1.  Build the wheel file for the agent.
2.  Run the `deployment/deploy.py` script to deploy the agent to Agent Engine.

The script will output the resource name of the deployed agent, which you can use to interact with it.

## Multi-Agent Workflow Examples

The following code blocks demonstrate how to create a multi-agent workflow using the `CaApiAgent`.

### Translation Agent

This agent translates the summary from the `CaApiAgent` to Japanese.

```python
from google.adk.agents import LlmAgent
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig

translation_agent = LlmAgent(
            name="TranslationAgent",
            instruction="Take the summary in the generated output: {temp:summary_data} and translate it to japanese.",
            model="gemini-2.5-flash",
            planner = BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            )
        )
```

### Code Executor Agent

This agent performs further analysis on the data from the `CaApiAgent`.

```python
from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig

code_executor_agent = LlmAgent(
            name='python_agent',
            model="gemini-2.5-flash",
            description='Agent that analyzes text and clusters and labels the results',
            instruction="""Run a further python analysis on the data to: identify anomalies, detect outliers, run forecasting if the result is time series and has suffecient rows OR cluster and label for cohort style analysis.
              Always be concise with your summarized responses. Here is the data : {temp:data_result}""",
            code_executor=BuiltInCodeExecutor(),
            planner = BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            )
        )
```

### Visualization Agent

This agent creates a visualization of the data from the `CaApiAgent`.

```python
from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig

visualization_agent = LlmAgent(
            name='visualization_agent',
            model="gemini-2.5-flash",
            description='A visualization agent that creates plots from data using Python, pandas, and matplotlib.',
            instruction="""You are a data visualization expert. Your primary purpose is to create insightful and clear plots from data.
            When you receive a request with data, your task is to:
            1.  Understand the data and the user's request for visualization.
            2.  Write Python code using pandas to prepare the data and matplotlib to generate a plot.
            3.  Ensure your code is self-contained and generates a visual output. For example, by calling `plt.show()`.
            4.  Along with the code that generates the plot, provide a brief, one-sentence summary of what the plot shows.

            The code will be executed, and the resulting plot will be displayed. Here is the data {temp:data_result}""",
            code_executor=BuiltInCodeExecutor(),
            planner = BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            )
        )
```

### Sequential Agent

This agent executes a pipeline of the above agents.

```python
from google.adk.agents import SequentialAgent
sequential_agent = SequentialAgent(
    name="TopLevelAgent",
    description="Executes a pipeline of agents. The first being a data agent that can answer any question about data. The second being an agent that takes the data result from prior output and performs advanced analysis on it. And the third, a visualization agent that visualizes the raw data intiutively based on the structure and records returned.",
    sub_agents=[root_agent,code_executor_agent,visualization_agent]
)
```
