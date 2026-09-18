"""sitecustomize module to automatically patch ADK's A2aAgentExecutor on startup."""

import logging
import sys

logger = logging.getLogger(__name__)

try:
    import google.adk.a2a.executor.a2a_agent_executor as a2a_executor_mod

    try:
        from . import agent_executor
    except (ImportError, ValueError):
        import agent_executor

    if hasattr(a2a_executor_mod, "A2aAgentExecutor"):
        a2a_executor_mod.A2aAgentExecutor.execute = agent_executor.a2ui_execute
        print(
            "[A2UI-STARTUP] Successfully patched A2aAgentExecutor.execute on startup in sitecustomize.py",
            file=sys.stderr,
        )
except Exception as e:
    # Gracefully ignore if a2a dependencies are not active during local non-A2A tasks
    print(
        f"[A2UI-STARTUP] Notice: A2aAgentExecutor not patched (likely not in adk api_server mode): {e}",
        file=sys.stderr,
    )
