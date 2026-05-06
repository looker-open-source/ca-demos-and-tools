import asyncio
import os
import sys
from google.cloud import geminidataanalytics_v1beta as gda

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ca_client import CAClient
from dotenv import load_dotenv

async def main():
    load_dotenv()
    client = CAClient()
    agent_id = "cymbal_gadgets_looker"
    
    print("Creating conversation (via gRPC)...")
    conversation_name = await client.create_conversation(agent_id)
    print(f"Conversation created: {conversation_name}")
    
    # Create REST client for chat
    print("Creating REST client for chat...")
    rest_client = gda.DataChatServiceAsyncClient(transport="rest")
    
    # Load context to get credentials
    import json
    context_path = f"context/{agent_id}/context.json"
    with open(context_path, "r") as f:
        context = json.load(f)
        
    oauth = context["looker"]["credentials"]["oauth"]
    secret = oauth["secret"]
    
    cred = gda.Credentials()
    cred.oauth.secret.client_id = secret.get("client_id")
    cred.oauth.secret.client_secret = secret.get("client_secret")

    agent_name = client._agent_resource_name(agent_id)
    
    request = gda.ChatRequest(
        parent=f"projects/{client.project_id}/locations/{client.location}",
        conversation_reference=gda.ConversationReference(
            conversation=conversation_name,
            data_agent_context=gda.DataAgentContext(
                data_agent=agent_name,
                context_version=gda.DataAgentContext.ContextVersion.PUBLISHED,
                credentials=cred
            ),
        ),
        messages=[
            gda.Message(user_message=gda.UserMessage(text="top 10 products sold in 2025"))
        ],
    )
    
    print("Sending chat request via REST client...")
    try:
        stream = await rest_client.chat(request=request)
        print("Got stream, iterating...")
        async for response in stream:
            print(f"Received: {response}")
    except Exception as e:
        print(f"Error during chat: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
