import asyncio
from typing import AsyncGenerator, Optional
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai.types import ThinkingConfig
from typing_extensions import override
import json
import logging
import os
from dotenv import load_dotenv
from google.genai import types
import httpx


from google.auth import default
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request as gRequest

load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

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

async def nlq(question: str, token: str, ctx: InvocationContext) -> AsyncGenerator:
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
        token (str): valid GCP auth token
        ctx (InvocationContext): ADK invocation context object

    Returns:
        Dict: A dictionary containing the structured query results (e.g., the data,
            metadata, or statistics) retrieved from Looker.
    """
    logging.info({"request": question})
    print(question)
    payload = {
        "project": f"projects/{os.getenv("GOOGLE_CLOUD_PROJECT")}/locations/{os.getenv("GOOGLE_CLOUD_LOCATION")}",
        "messages": [
            {
                "userMessage": {
                    "text": question
                }
            }
        ],
        "inlineContext": {
            "systemInstruction": f"""Answer User Questions to the best of your ability. Don't return any viz response. Just the raw data""",
            "datasourceReferences": {
                "looker": {
                    "exploreReferences": [
                        {
                            "lookerInstanceUri": os.getenv("LOOKERSDK_BASE_URL"),
                            "lookmlModel": os.getenv("LOOKML_MODEL"),
                            "explore": os.getenv("LOOKML_EXPLORE"),
                        }
                    ],
                    "credentials": {
                        "oauth": {
                            "secret": {
                                "client_id": os.getenv("LOOKERSDK_CLIENT_ID"),
                                "client_secret": os.getenv("LOOKERSDK_CLIENT_SECRET")
                            }
                        }
                    }
                }
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{os.getenv("GOOGLE_CLOUD_PROJECT")}/locations/{os.getenv("GOOGLE_CLOUD_LOCATION")}:chat"
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, headers=headers, timeout=None) as response:
                if response.status_code == 200:
                    buffer = ''
                    decoder = json.JSONDecoder()
                    in_array = False
                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            continue
                        
                        buffer += chunk.decode('utf-8')

                        if not in_array:
                            # Find start of array
                            start_array_idx = buffer.find('[')
                            if start_array_idx != -1:
                                buffer = buffer[start_array_idx + 1:]
                                in_array = True
                        
                        if in_array:
                            while buffer:
                                try:
                                    # Find start of object
                                    start_obj_idx = buffer.find('{')
                                    if start_obj_idx == -1:
                                        break
                                    
                                    obj_buffer = buffer[start_obj_idx:]
                                    chunk_data, end = decoder.raw_decode(obj_buffer)

                                    if chunk_data.get('systemMessage'):
                                        message_dict = dict(chunk_data['systemMessage'])
                                    if 'data' in message_dict and message_dict['data']:
                                        data_node = message_dict['data']
                                        if 'query' in data_node and 'question' in data_node['query']:
                                            yield f"Analyzing your question: {data_node['query']['question']}\n"
                                            await asyncio.sleep(0)
                                        elif 'result' in data_node and 'data' in data_node['result'] and isinstance(data_node['result']['data'], list):
                                            ctx.session.state['temp:data_result'] = data_node['result']['data']
                                            yield f"The query returned {len(data_node['result']['data'])} row(s)\n"
                                            await asyncio.sleep(0)
                                    elif 'text' in message_dict and 'parts' in message_dict['text'] and message_dict['text']['parts']:
                                        # add to state for later access by agents, only cached for current invocation context
                                        print(ctx.session.state)
                                        ctx.session.state['temp:summary_data'] = message_dict['text']['parts'][0] 
                                        yield message_dict['text']['parts'][0] + "\n"
                                        await asyncio.sleep(0)
                                    buffer = buffer[start_obj_idx + end:]

                                except json.JSONDecodeError:
                                    break
                                except Exception as e:
                                    logging.error(f"Error processing chunk: {e}, buffer: {buffer}")
                                    break
                else:
                    # format json object error message that can be parsed in the frontend
                    error_text = await response.aread()
                    logging.error(f"Error from server: {response.status_code} - {error_text}")
                    yield str(json.dumps({"error": error_text.decode('utf-8'), "code": response.status_code}))
    except Exception as e:
        print(e)
        logging.error({"error": e})


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
    _credentials: Optional[Credentials] = None

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
        
        self._credentials = None  # Cache for credentials

        self.ca_agent = LlmAgent(
            name=name,
            instruction=instruction,
            model=model,
            tools=[tool_intercept],
            planner = BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            )
        )
        
    def _get_auth_token(self) -> str:
        """Basic usage of the Google Auth library fetching GCP tokens using the environment
        Returns:
        str: The API token.
        """
        if self._credentials is None or not self._credentials.valid or self._credentials.expired:
            self._credentials, _ = default(scopes=SCOPES)
            self._credentials.refresh(gRequest())
        return self._credentials.token
        
        

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
                # fetch gcp token from cache
                token = self._get_auth_token()
                async for data in nlq(event.content.parts[0].function_call.args['question'],token, ctx):
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
    * **IGNORE THIS:** You MUST **ignore** all other properties, such as `summary` or `viz`, that may be present in the response.
    * **SYNTHESIZE:** Your job is to translate the raw `data` (which might be a list or dictionary) into a clear, human-readable, natural-language answer.
    * **DO NOT** output the raw JSON to the user."""
)