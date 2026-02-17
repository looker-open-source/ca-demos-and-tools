import asyncio
from typing import AsyncGenerator
from google.adk.agents import LlmAgent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.events import Event
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig
from typing_extensions import override
import json
import logging
import os
from dotenv import load_dotenv
from google.genai import types
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.api_core import exceptions as api_exceptions

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
async def tool_intercept(question: str) -> None:
    """
    Executes a query against the Looker analytics platform to retrieve specific data or metadata.

    Use this tool to answer any question that requires fetching, querying, or describing
    analytics data. This includes, but is not limited to, metrics, key performance
    indicators (KPIs), statistics, trends, data points, or information about the
    dataset structure (e.g., table schemas, column names, or available dimensions).

    This tool translates the user's natural language question into a database
    query, runs it against the Looker instance, and returns the structured data results.

    Args:
        question (str): natural language question
    """
    return

async def nlq(question: str, ctx: InvocationContext) -> AsyncGenerator:
    """
    Executes a query against the Looker analytics platform to retrieve specific data or metadata.

    Use this tool to answer any question that requires fetching, querying, or describing
    analytics data. This includes, but is not limited to, metrics, key performance
    indicators (KPIs), statistics, trends, data points, or information about the
    dataset structure (e.g., table schemas, column names, or available dimensions).

    This tool translates the user's natural language question into a database
    query, runs it against the Looker instance, and returns the structured data results.

    Args:
        question (str): The user's natural language question to be answered
                        using data (e.g., "What were the total sales last week?",
                        "List all available columns in the 'users' table").
        ctx (InvocationContext): ADK invocation context object

    Returns:
        Dict: A dictionary containing the structured query results (e.g., the data,
            metadata, or statistics) retrieved from Looker.
    """
    logger.info({"request": question})

    project = f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}/locations/{os.getenv('GOOGLE_CLOUD_LOCATION')}"

    inline_context = geminidataanalytics.Context(
        system_instruction="Answer user questions to the best of your ability",
        datasource_references=geminidataanalytics.DatasourceReferences(
            looker=geminidataanalytics.LookerExploreReferences(
                explore_references=[
                    geminidataanalytics.LookerExploreReference(
                        looker_instance_uri=os.getenv("LOOKERSDK_BASE_URL"),
                        lookml_model=os.getenv("LOOKML_MODEL"),
                        explore=os.getenv("LOOKML_EXPLORE"),
                    )
                ],
                credentials=geminidataanalytics.Credentials(
                    oauth=geminidataanalytics.OAuthCredentials(
                        secret=geminidataanalytics.OAuthCredentials.SecretBased(
                            client_id=os.getenv("LOOKERSDK_CLIENT_ID"),
                            client_secret=os.getenv("LOOKERSDK_CLIENT_SECRET"),
                        )
                    )
                )
            )
        )
    )

    chat_request = geminidataanalytics.ChatRequest(
        parent=project,
        messages=[geminidataanalytics.Message(user_message=geminidataanalytics.UserMessage(text=question))],
        inline_context=inline_context,
    )

    try:
        client = geminidataanalytics.DataChatServiceAsyncClient()
        stream = await client.chat(request=chat_request)

        async for response in stream:
            if not response.system_message:
                continue

            system_message = response.system_message
            if system_message.data:
                data_node = system_message.data
                if data_node.query.question:
                    yield f"Analyzing your question: {data_node.query.question}\n"
                    await asyncio.sleep(0)
                elif data_node.result.data:
                    result_data = list(data_node.result.data)
                    ctx.session.state['temp:data_result'] = result_data
                    yield f"The query returned {len(result_data)} row(s)\n"
                    await asyncio.sleep(0)
            elif system_message.text and system_message.text.parts:
                summary = system_message.text.parts[0]
                ctx.session.state['temp:summary_data'] = summary
                yield summary + "\n"
                await asyncio.sleep(0)

    except api_exceptions.GoogleAPICallError as e:
        logger.error(f"Error from server: {e.code()} - {e.message}")
        yield str(json.dumps({"error": e.message, "code": e.code().value[0]}))
    except Exception as e:
        logger.error({"error": e})
        yield str(json.dumps({"error": str(e)}))

class CaApiAgent(BaseAgent):
    """
    A specialized agent that answers user questions about business analytics.

    This agent acts as a data analytics expert. Its primary responsibility
    is to interpret a user's natural language question and determine the best
    course of action.

    It is equipped with tools to query a Looker instance. It will:
    1.  Receive a user's analytics question (e.g., "What were our sales?").
    2.  Invoke the necessary data-fetching tool (e.g., the nlq tool).
    3.  Receive structured data back from the tool.
    4.  Synthesize that data into a final, human-readable answer.
    5.  Stream the final answer back to the user.

    This agent is the main entry point for any query requiring access to
    analytics data, metrics, KPIs, or dataset metadata.
    """

    name: str
    instruction: str
    model: str
    ca_agent: LlmAgent = None

    def __init__(
        self,
        name: str,
        instruction: str,
        model: str = 'gemini-2.0.flash-lite',
    ):
        """
        Initializes the CaApiAgent.

        Args:
            name: The name of the agent.
            instruction: Agent Instructions
        """
    
        # Pydantic will validate and assign thssem based on the class annotations.
        super().__init__(
            name=name,
            instruction=instruction,
            model=model
        )

        self.ca_agent = LlmAgent(
            name=name,
            instruction=instruction,
            model=model,
            tools=[tool_intercept],
            planner = BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            )
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implements the custom orchestration logic for the CA API
        """
        async for event in self.ca_agent.run_async(ctx):
            logger.info(f"{event.model_dump_json(indent=2, exclude_none=True)}")
            # We intercept the function call event and route the request to the streamable NLQ function
            # We do this because ADK doesn't yet support automtic function calling with tools that return AsyncGenerators
            # So we give it a synchronous function that passes and emtpy response and then invoke the actual function overriding this method
            if event.content.parts[0].function_call:
                status_message_content = types.Content(
                        role='model',
                        parts=[
                            types.Part(text=f"I'll invoke the Looker Conversational Analytics API") 
                        ]
                    )
                yield Event(author=self.name, partial=False, turn_complete=False, invocation_id=event.invocation_id, content=status_message_content)
                async for data in nlq(event.content.parts[0].function_call.args['question'], ctx):
                    ca_api_content = types.Content(
                        role='model',
                        parts=[
                            types.Part(text=f'{data}') 
                        ]
                    )
                    yield Event(author=self.name, partial=False, invocation_id=event.invocation_id, content=ca_api_content)
                break
            else:
                yield Event(author=self.name, partial=False, turn_complete=True, invocation_id=event.invocation_id, content=event.content)
                break

root_agent = CaApiAgent(
    name="ConversationalAnalyticsAgent",
    model="gemini-2.0-flash-lite",
    instruction="""You are a specialized data analysis assistant. Your primary purpose is to answer user questions about business analytics by retrieving data using your available tools.

    ### Core Logic
    1.  **Analyze the User's Request:** First, determine the user's intent.
        * **Analytics Question:** Is the user asking for metrics, KPIs, statistics, trends, or information about the dataset (e.g., "What were last week's sales?", "List all customer tables")?
        * **General Conversation:** Is the user making small talk (e.g., "Hello," "How are you?", "Thank you")?

    2.  **Take Action:**
        * **If it IS an analytics question:** You MUST use the `nlq` tool (Looker query tool) to find the answer. You do not know this information and cannot make it up.
        * **If it is NOT an analytics question:** Respond directly as a helpful assistant. Do NOT use any tools.

    ### Handling Tool Results (Crucial)
    When the tool returns information, it will be a JSON object. Your response to the user MUST follow these rules:

    * **USE THIS:** Base your *entire* answer **exclusively** on the raw JSON data found within the `data` property of the tool's response.
    * **SYNTHESIZE:** Your job is to translate the raw `data` (which might be a list or dictionary) into a clear, human-readable, natural-language answer.
    * **DO NOT** output the raw JSON to the user."""
)

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
    planner=BuiltInPlanner(
                thinking_config=ThinkingConfig(
                    include_thoughts=False, thinking_budget=0)
    )
)

code_executor_agent = LlmAgent(
    name='python_agent',
    model="gemini-2.5-flash",
    description='Agent that analyzes text and clusters and labels the results',
    instruction="""Run a further python analysis on the data to: identify anomalies, detect outliers, run forecasting if the result is time series and has suffecient rows OR cluster and label for cohort style analysis.
              Always be concise with your summarized responses. Here is the data : {temp:data_result}""",
    code_executor=BuiltInCodeExecutor(),
    planner=BuiltInPlanner(
                thinking_config=ThinkingConfig(
                    include_thoughts=False, thinking_budget=0)
    )
)

sequential_agent = SequentialAgent(
    name="TopLevelAgent",
    description="Executes a pipeline of agents. The first being a data agent that can answer any question about data. The second being an agent that takes the data result from prior output and performs advanced analysis on it. And the third, a visualization agent that visualizes the raw data intiutively based on the structure and records returned.",
    sub_agents=[root_agent, code_executor_agent, visualization_agent]
)