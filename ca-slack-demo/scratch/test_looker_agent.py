import asyncio
import logging
import os
import sys

# Add src to path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(base_dir, 'src'))

from ca_client import CAClient

logging.basicConfig(level=logging.INFO)

async def main():
    # Ensure environment variables are set or use defaults
    project_id = os.environ.get("GCP_PROJECT_ID", "brk3-010-874158")
    location = os.environ.get("GCP_LOCATION", "global")
    
    agent_id = os.environ.get("CA_AGENT_CYMBAL_GADGETS_LOOKER", "cymbal_gadgets_looker")
    
    print(f"Testing Looker agent: {agent_id} in project: {project_id}")
    
    client = CAClient(project_id=project_id, location=location)
    
    context = None
    context_path = os.path.join(base_dir, "context", "cymbal_gadgets_looker", "context.json")
    if os.path.exists(context_path):
        import json
        with open(context_path, "r") as f:
            context = json.load(f)
            print(f"Loaded context from {context_path}")
    else:
        print(f"Context file not found at {context_path}")
            
    async def on_progress(label):
        print(f"Progress: {label}")
        
    async def on_query_start():
        print("Query started!")
            
    try:
        response = await client.chat(
            agent_id=agent_id,
            question="list all stores",
            conversation_id=None,
            context=context,
            on_progress=on_progress,
            on_query_start=on_query_start
        )
        print("\n--- Response ---")
        print(f"Text Answer: {response.text_answer}")
        print(f"Generated SQL: {response.generated_sql}")
        print(f"Error: {response.error}")
        print(f"Result Rows: {response.result_rows}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
