"""JSON-RPC 2.0 A2A server for the Vibe Guard A2UI agent.

Serves the A2A `message/send` endpoint, the agent card, and the bundled mock
client used for local testing. This is also the process `deploy/Dockerfile`
runs on Cloud Run, so it resolves the caller identity from the IAP headers and
isolates cached reports per conversation.
"""

import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Setup paths to import agent and core packages
current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
project_dir = agent_dir.parent
sys.path.extend([str(agent_dir), str(project_dir), str(project_dir / "src")])

# ruff: noqa: E402
import agent
from agent_executor import (
    A2UI_EXTENSION_BASE_URI,
    A2UI_EXTENSION_URI,
    A2UI_MIME_TYPE,
    extract_action_context,
    split_a2ui_payload,
)
from google.adk import runners
from google.adk.artifacts import in_memory_artifact_service
from google.adk.memory import in_memory_memory_service
from google.adk.sessions import in_memory_session_service
from google.genai import types as genai_types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vibe_guard_a2a_server")

# Detect Git URLs, repo archives, or local fixture paths pasted into chat
GIT_OR_PATH_REGEX = re.compile(
    r"(https?://[^\s]+|git@[^\s]+|fixtures/[^\s]+|[\w./-]+\.(?:zip|tar\.gz|tgz|tar))"
)

app = FastAPI(title="Vibe Guard A2UI Agent")

# The mock client is same-origin, so no cross-origin access is needed by default.
# Set VIBE_GUARD_CORS_ORIGINS to a comma-separated allowlist to widen it; a
# wildcard is deliberately unsupported because credentials are allowed.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "VIBE_GUARD_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origin.strip() and origin.strip() != "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-A2A-Extensions"],
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


@app.api_route("/healthz", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "agent": adk_agent.name}


@app.get("/a2a/vibe_guard_a2ui/.well-known/agent-card.json")
async def get_namespaced_agent_card():
    return await get_agent_card()


@app.api_route("/", methods=["GET", "HEAD"])
async def get_index():
    index_file = current_dir / "index.html"
    return FileResponse(index_file)


@app.post("/a2a/vibe_guard_a2ui")
async def handle_namespaced_jsonrpc(request: Request):
    return await handle_jsonrpc(request)


class _CallerContext:
    """Minimal ToolContext stand-in carrying the authenticated caller.

    The deterministic routes below call the agent tools directly rather than
    through the ADK runner, so they still need to hand `resolve_caller_id` the
    identity the transport authenticated.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.session = None
        self.state = None


def _resolve_caller(request: Request) -> str:
    """Resolve the authenticated caller for this request (SPEC-AUD-4).

    IAP strips any client-supplied copy of `X-Goog-Authenticated-User-Email`
    before forwarding, so it is trustworthy behind IAP; the raw JWT assertion is
    only honoured once verified. Falls back to 'anonymous', which the agent
    rejects in production.
    """
    email = request.headers.get("x-goog-authenticated-user-email")
    if email:
        return email.split("accounts.google.com:", 1)[-1].strip()

    verified = agent._email_from_iap_assertion(request.headers.get("x-goog-iap-jwt-assertion"))
    if verified:
        return verified

    # Identity forwarded by a trusted front end. These headers are only as
    # trustworthy as the ingress: cloudrun.yaml keeps the service private behind
    # IAP, which is what makes them usable here.
    for header in ("x-caller-id", "x-user-id", "x-user-email"):
        forwarded = request.headers.get(header)
        if forwarded:
            return forwarded.split("accounts.google.com:", 1)[-1].strip()

    for env_var in ("IAP_CALLER_IDENTITY", "AUTHENTICATED_USER_EMAIL", "CALLER_ID"):
        if os.environ.get(env_var):
            return os.environ[env_var]

    return "anonymous"


def _resolve_session_id(params: dict[str, Any], message: dict[str, Any]) -> str:
    """Resolve the conversation id that scopes cached reports."""
    for candidate in (
        message.get("contextId"),
        message.get("context_id"),
        params.get("contextId"),
        params.get("context_id"),
        params.get("session_id"),
    ):
        if candidate:
            return str(candidate)
    return "local_session"


def _activated_extensions(request: Request) -> str | None:
    """Return the A2UI extension to echo back, if the client asked for it."""
    header = request.headers.get("x-a2a-extensions") or request.headers.get("a2a-extensions")
    if not header:
        return None
    requested = [uri.strip() for uri in header.split(",") if uri.strip()]
    if A2UI_EXTENSION_URI in requested:
        return A2UI_EXTENSION_URI
    if any(uri.startswith(A2UI_EXTENSION_BASE_URI) for uri in requested):
        logger.warning("Client requested unsupported A2UI versions: %s", requested)
    return None


def _jsonrpc_error(request_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": request_id}
    )


@app.post("/jsonrpc")
async def handle_jsonrpc(request: Request):
    body = await request.json()
    logger.info(f"Received JSON-RPC request: {body.get('method')}")

    if body.get("jsonrpc") != "2.0":
        return _jsonrpc_error(body.get("id"), -32600, "Invalid Request: jsonrpc must be 2.0")

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    if method != "message/send":
        return _jsonrpc_error(request_id, -32601, f"Method not supported: {method}")

    message = params.get("message", {}) if isinstance(params, dict) else {}
    if not isinstance(message, dict):
        message = {}

    parts = message.get("parts", []) if isinstance(message.get("parts"), list) else []
    query = message.get("text", "") or ""
    if not query and parts:
        text_parts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
        if text_parts:
            query = " ".join(text_parts).strip()

    caller_id = _resolve_caller(request)
    session_id = _resolve_session_id(params, message)
    caller_context = _CallerContext(caller_id)

    # Extract the A2UI action (event name, chat prompt, form values) from DataParts
    action_name, action_query, action_context = extract_action_context(parts)

    session = await runner.session_service.get_session(
        app_name=adk_agent.name,
        user_id=caller_id,
        session_id=session_id,
    )
    if not session:
        session = await runner.session_service.create_session(
            app_name=adk_agent.name,
            user_id=caller_id,
            state={},
            session_id=session_id,
        )

    state = session.state if session.state else {}

    # Update state with action context (minus the human-readable chat prompt)
    if action_context:
        for key, value in action_context.items():
            if key not in ("prompt", "message"):
                state[key] = value
        session.state = state

    if action_query:
        query = action_query

    # Inject state into query for multi-replica continuity
    state_str = " ".join([f"[State: {k}={v}]" for k, v in state.items()])
    effective_query = f"{query} {state_str}".strip() if state_str else query.strip()
    logger.info(
        "A2A turn: caller=%s session=%s action=%s query=%s",
        caller_id,
        session_id,
        action_name,
        effective_query[:200],
    )

    lowered = query.lower()
    final_text = ""

    # A repository pasted straight into the chat is a scan request too.
    url_match = GIT_OR_PATH_REGEX.search(query)
    detected_url = url_match.group(0).strip(".,;:\"'<> ") if url_match else None
    is_scan_intent = (
        action_name in ("submit_scan", "scan")
        or "scan" in lowered
        or "repo_url" in action_context
        or (
            detected_url is not None
            and not any(word in lowered for word in ("explain", "finding", "help"))
        )
    )

    # Cached reports are scoped to this conversation so a replica shared by
    # several callers never serves one caller another caller's findings.
    with agent.session_scope(session_id):
        # Deterministic routes for A2UI actions and for running without an LLM key
        if is_scan_intent:
            repo_url = action_context.get("repo_url") or detected_url or state.get("repo_url")
            if not repo_url:
                final_text = (
                    "No repository was provided. Enter a Git HTTPS URL or an archive "
                    "path in the scan form, then launch the audit again."
                )
            else:
                repo_url = str(repo_url).strip(".,;:\"'<> ")
                branch = action_context.get("branch") or "main"
                families = action_context.get("families", ["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"])
                if isinstance(families, str):
                    families = [f.strip() for f in families.split(",")]
                final_text = agent.scan_repository(
                    source=repo_url,
                    branch=branch,
                    families=families,
                    no_llm=True,
                    tool_context=caller_context,
                )
        elif action_name == "explain_finding" or "explain finding" in lowered:
            finding_id = action_context.get("finding_id") or action_context.get("rule_id", "")
            final_text = agent.explain_finding(finding_id=finding_id, tool_context=caller_context)
        elif action_name == "show_dashboard" or "dashboard" in lowered:
            final_text = agent.show_dashboard(tool_context=caller_context)
        elif not query or lowered in ["hi", "hello", "bonjour", "start", "help"]:
            final_text = agent.render_scan_form(tool_context=caller_context)
        else:
            # Pass to ADK Runner with Gemini model
            try:
                content = genai_types.Content(
                    role="user", parts=[genai_types.Part(text=effective_query)]
                )
                async for event in runner.run_async(
                    user_id=caller_id, session_id=session.id, new_message=content
                ):
                    if (
                        event.is_final_response()
                        and event.content
                        and event.content.parts
                        and event.content.parts[0].text
                    ):
                        final_text = "\n".join([p.text for p in event.content.parts if p.text])
            except Exception as e:
                logger.warning(f"LLM run failed (falling back to deterministic form): {e}")
                final_text = agent.render_scan_form(tool_context=caller_context)

    # Split text and A2UI payload
    conversational_text, ui_messages = split_a2ui_payload(final_text)

    response_parts: list[dict[str, Any]] = []
    if conversational_text:
        response_parts.append({"kind": "text", "text": conversational_text})

    for msg in ui_messages:
        response_parts.append(
            {
                "kind": "data",
                "data": msg,
                "metadata": {"mimeType": A2UI_MIME_TYPE},
            }
        )

    if not response_parts:
        response_parts.append({"kind": "text", "text": "Scan ready."})

    payload = {
        "jsonrpc": "2.0",
        "result": {
            "kind": "message",
            "messageId": f"msg-{uuid.uuid4().hex[:16]}",
            "contextId": session_id,
            "role": "agent",
            "parts": response_parts,
        },
        "id": request_id,
    }

    headers = {}
    activated = _activated_extensions(request)
    if activated:
        headers["X-A2A-Extensions"] = activated
    return JSONResponse(payload, headers=headers)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
