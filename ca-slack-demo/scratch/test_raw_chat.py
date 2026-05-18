import asyncio
import os
import sys
from google.auth import default
from google.auth.transport.requests import AuthorizedSession

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ca_client import CAClient
from src.config import AGENT_CONFIGS

from dotenv import load_dotenv

async def main():
    load_dotenv()
    client = CAClient()
    agent_id = "cymbal_gadgets_looker"
    
    print("Creating conversation...")
    conversation_name = await client.create_conversation(agent_id)
    print(f"Conversation created: {conversation_name}")
    
    # Get credentials
    credentials, project = default()
    session = AuthorizedSession(credentials)
    
    # Load context to get credentials
    import json
    context_path = f"context/{agent_id}/context.json"
    with open(context_path, "r") as f:
        context = json.load(f)
        
    oauth = context["looker"]["credentials"]["oauth"]
    secret = oauth["secret"]
    
    explore_refs = []
    for r in context["looker"]["explore_references"]:
        explore_refs.append({
            "lookerInstanceUri": r.get("looker_instance_uri"),
            "lookmlModel": r.get("lookml_model"),
            "explore": r.get("explore")
        })

    # Construct URL
    # Pattern: projects/{project}/locations/{location}:chat
    url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{client.project_id}/locations/{client.location}:chat"
    print(f"URL: {url}")
    
    body = {
        "parent": f"projects/{client.project_id}/locations/{client.location}",
        "conversationReference": {
            "conversation": conversation_name,
            "dataAgentContext": {
                "dataAgent": client._agent_resource_name(agent_id),
                "contextVersion": "PUBLISHED",
                "credentials": {
                    "oauth": {
                        "secret": {
                            "clientId": secret.get("client_id"),
                            "clientSecret": secret.get("client_secret")
                        }
                    }
                }
            }
        },
        "messages": [
            {
                "userMessage": {
                    "text": "top 10 products sold in 2025"
                }
            }
        ]
    }
    
    print("Sending request...")
    response = session.post(url, json=body, stream=True)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code >= 400:
        print(f"Error: {response.text}")
    else:
        print("Response stream:")
        for line in response.iter_lines():
            if line:
                print(line.decode('utf-8'))

if __name__ == "__main__":
    # Run async main
    import asyncio
    asyncio.run(main())
