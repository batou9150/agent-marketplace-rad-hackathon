"""Custom A2A Agent Executor for Vibe Guard with A2UI v0.9 support.

Bridges ADK agents and A2A JSON-RPC 2.0 communication, extracts action contexts
from Gemini Enterprise, injects state into transcript, and packages A2UI payloads into DataParts.
"""

import contextlib
import json
import logging
from typing import Any

from google.adk import runners
from google.adk.artifacts import in_memory_artifact_service
from google.adk.memory import in_memory_memory_service
from google.adk.sessions import in_memory_session_service

from vibe_guard_a2ui.a2ui_presentation import A2UI_DELIMITER
from vibe_guard_a2ui.agent import root_agent

logger = logging.getLogger(__name__)


def extract_action_context(parts: list[Any]) -> tuple[str | None, dict[str, Any]]:
    """Extract action event context, hidden message intent, and form values from DataParts."""
    action_context: dict[str, Any] = {}
    action_query: str | None = None

    for part in parts:
        data = None
        # Handle dict parts or protobuf/Pydantic object parts
        if isinstance(part, dict):
            metadata = part.get("metadata", {})
            if metadata.get("mimeType") == "application/json+a2ui" or "data" in part:
                data = part.get("data")
        elif hasattr(part, "root") and hasattr(part.root, "data"):
            metadata = getattr(part.root, "metadata", None)
            mime = (
                metadata.get("mimeType")
                if isinstance(metadata, dict)
                else getattr(metadata, "mimeType", None)
            )
            if mime == "application/json+a2ui" or hasattr(part.root, "data"):
                data = part.root.data

        if not data:
            continue

        if isinstance(data, str):
            with contextlib.suppress(Exception):
                data = json.loads(data)

        if isinstance(data, dict):
            # Unwrap nested data wrapper if present
            if "data" in data and isinstance(data["data"], dict):
                data = data["data"]

            action_data = data.get("action") or data.get("userAction") or data.get("event")
            if isinstance(action_data, str):
                action_context["action"] = action_data
                action_context["event"] = action_data
                for k, v in data.items():
                    if k not in ("action", "userAction", "event"):
                        action_context[k] = v
            elif isinstance(action_data, dict):
                if "event" in action_data and isinstance(action_data["event"], dict):
                    action_data = action_data["event"]
                if "name" in action_data and isinstance(action_data["name"], str):
                    action_context["name"] = action_data["name"]

                ctx = action_data.get("context", {})
                if isinstance(ctx, list):
                    # Convert list of key/value pairs to dict
                    ctx_dict = {}
                    for item in ctx:
                        k = item.get("key")
                        val_obj = item.get("value", {})
                        if isinstance(val_obj, dict):
                            val = val_obj.get("literalString") or val_obj.get("path")
                        else:
                            val = val_obj
                        if k:
                            ctx_dict[k] = val
                    ctx = ctx_dict

                if isinstance(ctx, dict):
                    if "message" in ctx:
                        action_query = str(ctx["message"])
                    action_context.update(ctx)
            else:
                # Flat dictionary of context values
                for k, v in data.items():
                    action_context[k] = v

    return action_query, action_context


def split_a2ui_payload(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Split conversational text from the A2UI JSON payload."""
    if A2UI_DELIMITER not in text:
        return text.strip(), []

    text_part, json_str = text.split(A2UI_DELIMITER, 1)
    cleaned_json = json_str.strip()
    if cleaned_json.startswith("```json"):
        cleaned_json = cleaned_json[7:]
    elif cleaned_json.startswith("```"):
        cleaned_json = cleaned_json[3:]
    if cleaned_json.endswith("```"):
        cleaned_json = cleaned_json[:-3]
    cleaned_json = cleaned_json.strip()

    if not cleaned_json:
        return text_part.strip(), []

    try:
        parsed = json.loads(cleaned_json)
        if isinstance(parsed, list):
            return text_part.strip(), parsed
        if isinstance(parsed, dict):
            if "messages" in parsed and isinstance(parsed["messages"], list):
                return text_part.strip(), parsed["messages"]
            if "a2ui_messages" in parsed and isinstance(parsed["a2ui_messages"], list):
                return text_part.strip(), parsed["a2ui_messages"]
            return text_part.strip(), [parsed]
    except Exception as e:
        logger.error(f"Failed to parse A2UI JSON payload: {e}")

    return text_part.strip(), []


class AdkAgentToA2AExecutor:
    """Agent executor adapting Vibe Guard ADK agent for A2A and Gemini Enterprise."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args
        self._runner = kwargs.get("runner")
        if not self._runner:
            self._runner = runners.Runner(
                app_name="VibeGuardAgent",
                agent=root_agent,
                session_service=in_memory_session_service.InMemorySessionService(),
                artifact_service=in_memory_artifact_service.InMemoryArtifactService(),
                memory_service=in_memory_memory_service.InMemoryMemoryService(),
            )


async def a2ui_execute(self: Any, context: Any, event_queue: Any) -> None:
    """Monkey-patched execute method for A2aAgentExecutor in Cloud Run."""
    _ = (self, context, event_queue)
    logger.info("Executing A2UI agent turn with context")
    # Implemented when running inside adk api_server
