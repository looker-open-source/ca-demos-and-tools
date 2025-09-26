import os
from dotenv import load_dotenv
load_dotenv()

from google.cloud import geminidataanalytics
from google.adk.agents import Agent
from google.adk.code_executors import VertexAiCodeExecutor
from google.adk.tools import agent_tool


# CONFIG
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
VERTEX_AI_CODE_INTERPRETER_EXTENSION = os.getenv("VERTEX_AI_CODE_INTERPRETER_EXTENSION")
#

#CA API CONFIG
LOOKER_CLIENT_ID = os.getenv("LOOKER_CLIENT_ID")
LOOKER_CLIENT_SECRET = os.getenv("LOOKER_CLIENT_SECRET")
LOOKER_INSTANCE_URI = os.getenv("LOOKER_INSTANCE_URI")
LOOKML_MODEL = os.getenv("LOOKML_MODEL")
LOOKER_EXPLORE = os.getenv("LOOKER_EXPLORE")
CA_API_SYSTEM_INSTRUCTIONS = os.getenv("CA_API_SYSTEM_INSTRUCTIONS")
CA_API_BILLING_PROJECT = os.getenv("CA_API_BILLING_PROJECT")


def get_insights(question: str):
    """Queries the Conversational Analytics API using a question as input.

  Use this tool to generate the data for data insights.

  Args:
      question: The question to post to the API.

  Returns:
      A dictionary containing the status of the operation and the insights from
      the API, categorized by type (e.g., text_insights, data_insights) to make
      the output easier for an LLM to understand and process.
  """

    data_chat_client = geminidataanalytics.DataChatServiceClient()

    credentials = geminidataanalytics.Credentials(
        oauth=geminidataanalytics.OAuthCredentials(
            secret=geminidataanalytics.OAuthCredentials.SecretBased(
                client_id=LOOKER_CLIENT_ID, client_secret=LOOKER_CLIENT_SECRET
            ),
        )
    )

    looker_explore_reference = geminidataanalytics.LookerExploreReference(
        looker_instance_uri=LOOKER_INSTANCE_URI, lookml_model=LOOKML_MODEL, explore=LOOKER_EXPLORE
    )

    
    datasource_references = geminidataanalytics.DatasourceReferences(
        looker=geminidataanalytics.LookerExploreReferences(
            explore_references=[looker_explore_reference],
            credentials=credentials
        ),
    )

    system_instruction = CA_API_SYSTEM_INSTRUCTIONS

    inline_context = geminidataanalytics.Context(
        system_instruction=system_instruction,
        datasource_references=datasource_references,
        options=geminidataanalytics.ConversationOptions(
            analysis=geminidataanalytics.AnalysisOptions(
                python=geminidataanalytics.AnalysisOptions.Python(
                    enabled=False
                )
            )
        ),
    )

    billing_project = CA_API_BILLING_PROJECT

    messages = [geminidataanalytics.Message(user_message={"text": question})]

    request = geminidataanalytics.ChatRequest(
        inline_context=inline_context,
        parent=f"projects/{billing_project}/locations/global",
        messages=messages,
    )

    # Make the request
    stream = data_chat_client.chat(request=request)

    # Categorize insights from the stream for a more descriptive output
    text_insights = []
    schema_insights = []
    data_insights = []
    chart_insights = []

    for item in stream:
        if item.system_message:
            message_dict = geminidataanalytics.SystemMessage.to_dict(
                item.system_message
            )
            if "text" in message_dict:
                text_insights.append(message_dict["text"])
            elif "schema" in message_dict:
                schema_insights.append(message_dict["schema"])
            elif "data" in message_dict:
                data_insights.append(message_dict["data"])
            elif "chart" in message_dict:
                chart_insights.append(message_dict["chart"])

    # Build a descriptive response dictionary that is easier for the LLM to parse
    response = {"status": "success"}
    if text_insights:
        response["text_insights"] = text_insights
    if schema_insights:
        response["schema_insights"] = schema_insights
    if data_insights:
        response["data_insights"] = data_insights
    if chart_insights:
        response["chart_insights"] = chart_insights
    print(response)
    return response

# Agent to get data insights
data_agent = Agent(
    model=GEMINI_MODEL,
    name="DataAgent",
    description="Use this agent to get data insights about orders, sales, and e-commerce from the Cymbal Pets Superstore.",
    instruction = """You are an agent that retrieves raw data. The tool 'get_insights' queries a governed semantic layer.
    Your task is to call the 'get_insights' tool with the user's question.
    From the tool's dictionary output, find the 'data_insights' list. Within that list, find the dictionary that contains a 'result' key.
    Extract the list of records from the 'data' key which is inside 'result'.
    Return this list of records as a JSON string. Do not add any other text or summarization.
    """,
    tools=[get_insights],
)

# Agent to create visualizations
visualization_agent = Agent(
    model=GEMINI_MODEL,
    name="VisualizationAgent",
    description="A visualization agent that creates plots from data using Python, pandas, and matplotlib.",
    instruction="""You are a data visualization expert. Your primary purpose is to create insightful and clear plots from data.
    When you receive a request with data, your task is to:
    1.  Understand the data and the user's request for visualization.
    2.  Write Python code using pandas to prepare the data and matplotlib to generate a plot.
    3.  Ensure your code is self-contained and generates a visual output. For example, by calling `plt.show()`.
    4.  Along with the code that generates the plot, provide a brief, one-sentence summary of what the plot shows.

    The code will be executed, and the resulting plot will be displayed.
    """,
    code_executor=VertexAiCodeExecutor(
        optimize_data_file=True,
        stateful=True,
        error_retry_attempts=3,
        resource_name=VERTEX_AI_CODE_INTERPRETER_EXTENSION,
    ),
)

# Root agent to orchestrate the sub-agents
root_agent = Agent(
    model=GEMINI_MODEL,
    name="RootAgent",
    instruction="""You are a helpful data analysis assistant. Your goal is to answer user questions and, if appropriate, create visualizations.

    Your workflow is as follows:
    1. When the user asks a question about data, use the `DataAgent` tool to retrieve the necessary data. The `DataAgent` will return a JSON string of the raw data.
    2. Create a human-readable summary of the data from the JSON string and present it to the user. If a table is appropriate, use markdown.
    3. After presenting the data, ask the user if they would like a visualization of the data, but ONLY if it is reasonable to do so. It is not reasonable to visualize a single data point. For multiple data points, like a time series or a list of categories, it is reasonable to offer a visualization.
    4. If the user confirms they want a visualization, call the `VisualizationAgent` tool. The prompt for the `VisualizationAgent` MUST be a request to visualize the data, and you MUST include the full, original JSON data string you received from the `DataAgent`.
    """,
    tools=[
        agent_tool.AgentTool(agent=data_agent),
        agent_tool.AgentTool(agent=visualization_agent),
    ],
)