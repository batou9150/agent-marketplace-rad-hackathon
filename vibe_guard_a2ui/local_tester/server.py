"""Local testing server for Vibe Guard A2UI agent.

Provides JSON-RPC 2.0 A2A protocol emulation, schema validation, and web mock client.
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

# Setup paths to import agent and core packages
current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
project_dir = agent_dir.parent
sys.path.extend([str(agent_dir), str(project_dir), str(project_dir / "src")])

load_dotenv(project_dir / ".env")

import agent
from agent_executor import extract_action_context, split_a2ui_payload
from google.adk import runners
from google.adk.artifacts import in_memory_artifact_service
from google.adk.memory import in_memory_memory_service
from google.adk.sessions import in_memory_session_service
from google.genai import types as genai_types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a2ui_local_tester")

app = FastAPI(title="Vibe Guard A2UI Local Tester")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

adk_agent = agent.root_agent
session_service = in_memory_session_service.InMemorySessionService()
runner = runners.Runner(
    app_name=adk_agent.name,
    agent=adk_agent,
    session_service=session_service,
    artifact_service=in_memory_artifact_service.InMemoryArtifactService(),
    memory_service=in_memory_memory_service.InMemoryMemoryService(),
)


@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    card_path = agent_dir / ".well-known" / "agent-card.json"
    if card_path.is_file():
        with open(card_path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "name": adk_agent.name,
        "capabilities": {
            "streaming": False,
            "extensions": [{"uri": "https://a2ui.org/a2a-extension/a2ui/v0.9", "required": False}],
        },
        "url": "/jsonrpc",
    }


@app.get("/")
async def get_index():
    index_file = current_dir / "index.html"
    return FileResponse(index_file)


@app.post("/jsonrpc")
async def handle_jsonrpc(request: Request):
    body = await request.json()
    logger.info(f"Received JSON-RPC request: {body.get('method')}")

    if body.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: jsonrpc must be 2.0"},
            "id": body.get("id"),
        }

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    if method != "message/send":
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not supported: {method}"},
            "id": request_id,
        }

    message = params.get("message", {})
    query = message.get("text", "")
    parts = message.get("parts", [])
    session_id = params.get("session_id", "local_session")

    # Extract user action and context from DataPart
    action_query, action_context = extract_action_context(parts)

    session = await runner.session_service.get_session(
        app_name=adk_agent.name,
        user_id="local_user",
        session_id=session_id,
    )
    if not session:
        session = await runner.session_service.create_session(
            app_name=adk_agent.name,
            user_id="local_user",
            state={},
            session_id=session_id,
        )

    state = session.state if session.state else {}

    # Update state with action context
    if action_context:
        for k, v in action_context.items():
            if k != "message":
                state[k] = v
        session.state = state

    if action_query:
        query = action_query

    # Inject state into query for multi-replica continuity
    state_str = " ".join([f"[State: {k}={v}]" for k, v in state.items()])
    effective_query = f"{query} {state_str}".strip() if state_str else query.strip()
    logger.info(f"Effective query: {effective_query}")

    final_text = ""

    # Check for direct tool execution shortcut if no LLM key or deterministic trigger
    action_name = (
        action_context.get("event")
        or action_context.get("action")
        or (action_context.get("name") if isinstance(action_context, dict) else None)
    )

    if (
        "scan repository" in query.lower()
        or action_name == "submit_scan"
        or "repo_url" in action_context
    ):
        repo_url = action_context.get("repo_url", "fixtures/nonconform/app_llm_injection")
        branch = action_context.get("branch", "main")
        families = action_context.get("families", ["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"])
        if isinstance(families, str):
            families = [f.strip() for f in families.split(",")]
        final_text = agent.scan_repository(
            source=repo_url, branch=branch, families=families, no_llm=True
        )
    elif "explain finding" in query.lower() or action_name == "explain_finding":
        finding_id = action_context.get("finding_id") or action_context.get("rule_id", "")
        final_text = agent.explain_finding(finding_id=finding_id)
    elif "dashboard" in query.lower() or action_name == "show_dashboard":
        final_text = agent.show_dashboard()
    elif not query or query.lower() in ["hi", "hello", "bonjour", "start", "help"]:
        final_text = agent.render_scan_form()
    else:
        # Pass to ADK Runner with Gemini model
        try:
            content = genai_types.Content(role="user", parts=[{"text": effective_query}])
            async for event in runner.run_async(
                user_id="local_user", session_id=session.id, new_message=content
            ):
                if event.is_final_response():
                    if event.content and event.content.parts and event.content.parts[0].text:
                        final_text = "\n".join(
                            [p.text for p in event.content.parts if p.text]
                        )
        except Exception as e:
            logger.warning(
                f"LLM run failed (falling back to deterministic form): {e}"
            )
            final_text = agent.render_scan_form()

    # Split text and A2UI payload
    conversational_text, ui_messages = split_a2ui_payload(final_text)

    response_parts: list[dict[str, Any]] = []
    if conversational_text:
        response_parts.append({"text": conversational_text})

    for msg in ui_messages:
        response_parts.append(
            {
                "data": msg,
                "metadata": {"mimeType": "application/json+a2ui"},
            }
        )

    return {
        "jsonrpc": "2.0",
        "result": {
            "message": {
                "role": "model",
                "parts": response_parts,
            }
        },
        "id": request_id,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
