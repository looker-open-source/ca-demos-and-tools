import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from src.agents.root import root_agent

import sys
from pathlib import Path

# Add src to path to import CAClient
sys.path.insert(0, str(Path(__file__).parent))

from ca_client import CAClient
from config import AGENT_CONFIGS, GCP_PROJECT_ID, GCP_LOCATION

app = FastAPI(title="CA Analytics Custom App")

# In-memory store for shared reports (will reset on restart)
shared_reports = {}

# Initialize ADK Runner for Web App (isolated from Slack sessions)
web_session_service = InMemorySessionService()
web_runner = Runner(
    agent=root_agent,
    app_name="web-analytics-app",
    session_service=web_session_service,
)

class ChatRequest(BaseModel):
    question: str

class ShareRequest(BaseModel):
    question: str
    answer: str
    sql: str | None = None
    chart_spec: dict | None = None

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        content = types.Content(role="user", parts=[types.Part(text=req.question)])
        
        text_parts = []
        chart_spec = None
        sql = None
        
        session_id = "default-web-session"
        user_id = "web-user"
        
        # Ensure session exists
        if await web_session_service.get_session(app_name="web-analytics-app", user_id=user_id, session_id=session_id) is None:
            await web_session_service.create_session(app_name="web-analytics-app", user_id=user_id, session_id=session_id)
            
        async for event in web_runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        text_parts.append(part.text)
                    if part.function_response:
                        resp = part.function_response.response
                        if isinstance(resp, dict):
                            chart_spec = chart_spec or resp.get("chart_spec")
                            sql = sql or resp.get("generated_sql")
                            
        answer = "".join(text_parts) or "No response from agent."
        
        return {
            "answer": answer,
            "sql": sql,
            "chart_spec": chart_spec,
            "error": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/share")
async def share(req: ShareRequest):
    share_id = str(uuid.uuid4())
    shared_reports[share_id] = req.dict()
    return {"share_id": share_id}

@app.get("/share/{share_id}", response_class=HTMLResponse)
async def get_share(share_id: str):
    report = shared_reports.get(share_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Simple HTML template for shared view
    html_content = f"""
    <html>
    <head>
        <title>Shared Report</title>
        <style>
            body {{ font-family: 'Google Sans', sans-serif; padding: 20px; background: #f8f9fa; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #1a73e8; }}
            pre {{ background: #f1f3f4; padding: 10px; border-radius: 4px; overflow-x: auto; }}
            .btn {{ background: #1a73e8; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-bottom: 20px; }}
            @media print {{
                .no-print {{ display: none; }}
                body {{ background: white; padding: 0; }}
                .card {{ box-shadow: none; padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <button class="btn no-print" onclick="window.print()">Download as PDF</button>
            <h1>Shared Data Report</h1>
            <p><strong>Question:</strong> {report['question']}</p>
            <p><strong>Answer:</strong></p>
            <div>{report['answer']}</div>
            {f"<p><strong>SQL:</strong></p><pre>{report['sql']}</pre>" if report.get('sql') else ""}
        </div>
    </body>
    </html>
    """
    return html_content

# Mount static files
app.mount("/", StaticFiles(directory="src/static", html=True), name="static")
