"""A2A agent executor for Vibe Guard with A2UI v0.9 support.

Bridges the Vibe Guard ADK agent and the A2A protocol: extracts A2UI action
contexts emitted by Gemini Enterprise, runs the ADK agent, then splits the
conversational text from the A2UI envelope produced by the tools and packages
the envelope into `application/json+a2ui` DataParts.

`VibeGuardAgentExecutor` implements the `a2a.server.agent_execution.AgentExecutor`
contract, so it can be passed directly as `agent_executor_builder` to
`vertexai.preview.reasoning_engines.A2aAgent` (Vertex AI Agent Engine) or to any
A2A server built on the a2a-sdk.
"""

import contextlib
import json
import logging
import os
import uuid
from typing import Any

from a2a.server.agent_execution import AgentExecutor
from google.adk import runners
from google.adk.artifacts import in_memory_artifact_service
from google.adk.memory import in_memory_memory_service
from google.adk.sessions import in_memory_session_service
from google.genai import types as genai_types

from vibe_guard_a2ui import agent as agent_module
from vibe_guard_a2ui.a2ui_presentation import A2UI_DELIMITER
from vibe_guard_a2ui.agent import root_agent

logger = logging.getLogger(__name__)

A2UI_MIME_TYPE = "application/json+a2ui"
A2UI_EXTENSION_URI = "https://a2ui.org/a2a-extension/a2ui/v0.9"
A2UI_EXTENSION_BASE_URI = "https://a2ui.org/a2a-extension/a2ui"

# Event-context keys carrying the human-readable chat prompt rather than a form
# value; they must not be echoed back into the agent's session state.
_PROMPT_CONTEXT_KEYS = frozenset({"prompt", "message"})

# google-adk isolates every API that diverges between a2a-sdk 0.3.x and 1.x
# (pydantic models vs protobuf messages) behind this module.
try:
    from google.adk.a2a import _compat as a2a_compat
except ImportError:  # pragma: no cover - only on unexpected ADK layouts
    a2a_compat = None


def _make_text_part(text: str) -> Any:
    """Build an A2A text Part for the installed a2a-sdk version."""
    if a2a_compat:
        return a2a_compat.make_text_part(text)
    from a2a.types import Part, TextPart

    return Part(root=TextPart(text=text))


def _make_data_part(data: dict[str, Any], metadata: dict[str, Any]) -> Any:
    """Build an A2A data Part for the installed a2a-sdk version."""
    if a2a_compat:
        return a2a_compat.make_data_part(data=data, metadata=metadata)
    from a2a.types import DataPart, Part

    return Part(root=DataPart(data=data, metadata=metadata))


def _make_agent_message(parts: list[Any], context_id: str | None, task_id: str | None) -> Any:
    """Build an A2A agent Message for the installed a2a-sdk version."""
    message_id = str(uuid.uuid4())
    if a2a_compat:
        return a2a_compat.make_message(
            message_id=message_id,
            role="agent",
            parts=parts,
            context_id=context_id,
            task_id=task_id,
        )
    from a2a.types import Message, Role

    return Message(
        message_id=message_id,
        role=Role.agent,
        parts=parts,
        context_id=context_id,
        task_id=task_id,
    )


def _part_payload(part: Any) -> tuple[str | None, Any]:
    """Normalize a part (dict, a2a-sdk 0.3.x or 1.x) into (mimeType, data)."""
    if isinstance(part, dict):
        metadata = part.get("metadata") or {}
        return metadata.get("mimeType"), part.get("data")

    # a2a-sdk 0.3.x: Part wraps a discriminated union via `.root`.
    if hasattr(part, "root") and hasattr(part.root, "data"):
        metadata = getattr(part.root, "metadata", None)
        mime = (
            metadata.get("mimeType")
            if isinstance(metadata, dict)
            else getattr(metadata, "mimeType", None)
        )
        return mime, part.root.data

    # a2a-sdk 1.x: flat protobuf Part with a `data` oneof variant.
    if a2a_compat and a2a_compat.is_data_part(part):
        metadata = a2a_compat.part_metadata(part) or {}
        return metadata.get("mimeType"), a2a_compat.data_part_dict(part)

    return None, None


def _part_text(part: Any) -> str:
    """Extract text from a part (dict, a2a-sdk 0.3.x or 1.x), or '' if not textual."""
    if isinstance(part, dict):
        return str(part.get("text") or "")
    if hasattr(part, "root"):
        return str(getattr(part.root, "text", "") or "")
    if a2a_compat and a2a_compat.is_text_part(part):
        return a2a_compat.part_text(part)
    return ""


def _normalize_context(ctx: Any) -> dict[str, Any]:
    """Normalize an A2UI event context into a flat dict of literal values.

    A2UI v0.9 sends `context` as a JSON object whose values are literals or
    `{"path": ...}` data bindings already resolved by the client. Older clients
    sent a list of `{"key": ..., "value": {...}}` pairs; both are accepted.
    """
    if isinstance(ctx, dict):
        return dict(ctx)
    if not isinstance(ctx, list):
        return {}

    normalized: dict[str, Any] = {}
    for item in ctx:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key:
            continue
        value = item.get("value", {})
        if isinstance(value, dict):
            value = value.get("literalString", value.get("path"))
        normalized[key] = value
    return normalized


def extract_action_context(parts: list[Any]) -> tuple[str | None, str | None, dict[str, Any]]:
    """Extract the A2UI action from client DataParts.

    Returns `(event_name, chat_prompt, context)`. The Gemini Enterprise client
    sends `{"version": "v0.9", "action": {"name": ..., "context": {...}}}`, and
    replays `context.prompt` as the user's chat message. Legacy clients send an
    untagged DataPart whose `action` is a bare event name alongside flat form
    values, so both shapes are accepted.
    """
    action_context: dict[str, Any] = {}
    action_name: str | None = None
    action_query: str | None = None

    for part in parts:
        mime, data = _part_payload(part)
        # An untagged DataPart is still accepted; only a foreign mime type is not.
        if not data or (mime and mime != A2UI_MIME_TYPE):
            continue

        if isinstance(data, str):
            with contextlib.suppress(Exception):
                data = json.loads(data)

        if not isinstance(data, dict):
            continue

        # Unwrap nested data wrapper if present
        if "data" in data and isinstance(data["data"], dict):
            data = data["data"]

        action_data = data.get("action") or data.get("userAction") or data.get("event")

        if isinstance(action_data, str):
            # Legacy shape: bare event name with the form values alongside it.
            action_name = action_data
            ctx = {k: v for k, v in data.items() if k not in ("action", "userAction", "event")}
        elif isinstance(action_data, dict):
            # Tolerate an action still wrapped in its `event` envelope.
            if isinstance(action_data.get("event"), dict):
                action_data = action_data["event"]

            name = action_data.get("name")
            if isinstance(name, str) and name:
                action_name = name

            ctx = _normalize_context(action_data.get("context", {}))
        else:
            # Flat dictionary of context values, with no action envelope.
            ctx = {k: v for k, v in data.items() if k != "version"}

        # `prompt` is the A2UI v0.9 key; `message` is kept for older payloads.
        for prompt_key in ("prompt", "message"):
            if ctx.get(prompt_key):
                action_query = str(ctx[prompt_key])
                break
        action_context.update(ctx)

    return action_name, action_query, action_context


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


def build_response_parts(final_text: str) -> list[Any]:
    """Convert an agent answer into A2A parts: conversational text plus A2UI DataParts."""
    conversational_text, ui_messages = split_a2ui_payload(final_text)

    parts: list[Any] = []
    if conversational_text:
        parts.append(_make_text_part(conversational_text))
    for message in ui_messages:
        parts.append(_make_data_part(message, {"mimeType": A2UI_MIME_TYPE}))
    if not parts:
        parts.append(_make_text_part("No response was produced for this request."))
    return parts


def resolve_caller_identity(context: Any) -> str:
    """Resolve the authenticated caller from the A2A request context (SPEC-AUD-4).

    Gemini Enterprise and Agent Engine forward the end-user identity on the
    server call context; IAP-fronted deployments forward it as a header. Falls
    back to the deployment identity env vars, then to 'anonymous'.
    """
    call_context = getattr(context, "call_context", None)

    user = getattr(call_context, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        user_name = getattr(user, "user_name", "")
        if user_name:
            return str(user_name)

    state = getattr(call_context, "state", None)
    if isinstance(state, dict):
        headers = state.get("headers")
        if isinstance(headers, dict):
            lowered = {str(k).lower(): v for k, v in headers.items()}
            # IAP strips any client-supplied copy of the authenticated-user
            # header before forwarding, so it is the one header usable as an
            # identity as-is. The JWT assertion is a token, not an identity: it
            # only yields a caller once its signature and audience are verified.
            # Bearer tokens (x-serverless-authorization) are never identities.
            email = lowered.get("x-goog-authenticated-user-email")
            if email:
                return str(email)
            verified = agent_module._email_from_iap_assertion(
                lowered.get("x-goog-iap-jwt-assertion")
            )
            if verified:
                return verified

    for env_var in ("IAP_CALLER_IDENTITY", "AUTHENTICATED_USER_EMAIL", "CALLER_ID"):
        if os.environ.get(env_var):
            return os.environ[env_var]

    return "anonymous"


def activate_a2ui_extension(context: Any) -> str | None:
    """Activate the A2UI A2A extension when the client requested it.

    A2A extensions are opt-in: the client advertises the extension URIs it wants
    in the request, and the server must echo back the ones it activated (the
    `A2A-Extensions` response parameter) before the client will interpret A2UI
    DataParts. Without this handshake Gemini Enterprise ignores the UI payload.
    """
    requested: list[str] = []
    for source in (
        getattr(context, "requested_extensions", None),
        getattr(getattr(context, "message", None), "extensions", None),
    ):
        if source:
            requested.extend(uri for uri in source if isinstance(uri, str))

    matched = [uri for uri in requested if uri.startswith(A2UI_EXTENSION_BASE_URI)]
    if not matched:
        return None

    # Vibe Guard emits v0.9 envelopes, so only v0.9 is honoured.
    selected = A2UI_EXTENSION_URI if A2UI_EXTENSION_URI in matched else None
    if not selected:
        logger.warning("Client requested unsupported A2UI versions: %s", matched)
        return None

    activate = getattr(context, "add_activated_extension", None)
    if callable(activate):
        activate(selected)
    else:  # pragma: no cover - older a2a-sdk without the helper
        logger.debug("RequestContext has no add_activated_extension; skipping echo")
    return selected


def build_runner(app_name: str = "VibeGuardAgent") -> runners.Runner:
    """Build the ADK runner backing the executor."""
    return runners.Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=in_memory_session_service.InMemorySessionService(),
        artifact_service=in_memory_artifact_service.InMemoryArtifactService(),
        memory_service=in_memory_memory_service.InMemoryMemoryService(),
    )


class VibeGuardAgentExecutor(AgentExecutor):
    """Runs the Vibe Guard ADK agent behind the A2A protocol with A2UI DataParts."""

    def __init__(self, runner: runners.Runner | None = None) -> None:
        self._runner = runner or build_runner()

    async def _ensure_session(self, user_id: str, session_id: str) -> Any:
        session_service = self._runner.session_service
        session = await session_service.get_session(
            app_name=self._runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if not session:
            session = await session_service.create_session(
                app_name=self._runner.app_name,
                user_id=user_id,
                state={},
                session_id=session_id,
            )
        return session

    async def _run_agent(self, user_id: str, session_id: str, query: str) -> str:
        content = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])
        final_text = ""
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                texts = [p.text for p in event.content.parts if p.text]
                if texts:
                    final_text = "\n".join(texts)
        return final_text

    async def execute(self, context: Any, event_queue: Any) -> None:
        """Run one Vibe Guard turn and enqueue the A2A response message."""
        message = getattr(context, "message", None)
        parts = list(getattr(message, "parts", []) or []) if message is not None else []

        query = ""
        with contextlib.suppress(Exception):
            query = context.get_user_input()
        if not query:
            query = " ".join(filter(None, (_part_text(p) for p in parts))).strip()

        activate_a2ui_extension(context)

        action_name, action_query, action_context = extract_action_context(parts)
        if action_query:
            query = action_query
        elif action_name:
            query = f"The user triggered the '{action_name}' action."

        caller_id = resolve_caller_identity(context)
        session_id = getattr(context, "context_id", None) or str(uuid.uuid4())
        session = await self._ensure_session(caller_id, session_id)

        # A2UI form values arrive out of band; persist them and surface them to
        # the model so it can call the right tool with the right arguments.
        state = dict(session.state or {})
        for key, value in action_context.items():
            if key not in _PROMPT_CONTEXT_KEYS:
                state[key] = value
        if action_name:
            state["last_action"] = action_name
        session.state = state

        state_hint = " ".join(f"[State: {k}={v}]" for k, v in state.items())
        effective_query = f"{query} {state_hint}".strip() if state_hint else query.strip()
        if not effective_query:
            effective_query = "hello"

        logger.info(
            "Vibe Guard A2A turn: caller=%s session=%s action=%s query=%s",
            caller_id,
            session_id,
            action_name,
            effective_query[:200],
        )

        try:
            # Scope the cached report to this conversation so one replica never
            # serves another caller's findings.
            with agent_module.session_scope(session_id):
                final_text = await self._run_agent(caller_id, session_id, effective_query)
        except Exception as exc:
            logger.exception("Vibe Guard agent run failed")
            final_text = f"Vibe Guard could not complete this request: {exc}"

        response = _make_agent_message(
            parts=build_response_parts(final_text),
            context_id=getattr(context, "context_id", None),
            task_id=getattr(context, "task_id", None),
        )
        await event_queue.enqueue_event(response)

    async def cancel(self, context: Any, event_queue: Any) -> None:
        """Cancellation is not supported: scans are bounded and run to completion."""
        raise NotImplementedError("Vibe Guard does not support task cancellation")


# Backwards-compatible alias for earlier deployment scripts.
AdkAgentToA2AExecutor = VibeGuardAgentExecutor
