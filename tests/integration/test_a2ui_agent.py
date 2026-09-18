"""Integration tests for Vibe Guard A2UI agent and executor.

Verifies SPEC-AGT-1, SPEC-AGT-2, and SPEC-AGT-3.
"""

from pathlib import Path

from vibe_guard_a2ui.a2ui_presentation import A2UI_DELIMITER
from vibe_guard_a2ui.agent import (
    explain_finding,
    render_scan_form,
    root_agent,
    scan_repository,
    show_dashboard,
)
from vibe_guard_a2ui.agent_executor import extract_action_context, split_a2ui_payload


def test_agent_structure_and_tools():
    """Verify ADK root agent configuration and registered tools (SPEC-AGT-1)."""
    assert root_agent.name == "VibeGuardAgent"
    assert root_agent.model == "gemini-3.8-flash"
    tool_names = [t.__name__ for t in root_agent.tools]
    assert "scan_repository" in tool_names
    assert "explain_finding" in tool_names
    assert "render_scan_form" in tool_names
    assert "show_dashboard" in tool_names


def test_render_scan_form():
    """Verify render_scan_form returns welcome text and A2UI form envelope."""
    result = render_scan_form()
    assert "Welcome to **Vibe Guard**" in result
    assert A2UI_DELIMITER in result

    text, ui_messages = split_a2ui_payload(result)
    assert len(ui_messages) == 3
    assert ui_messages[0]["createSurface"]["surfaceId"] == "scan_form_surface"


def test_scan_and_explain_finding_flow():
    """Verify end-to-end scan and explain_finding flow without re-scan (SPEC-AGT-1, SPEC-AGT-3)."""
    fixture_dir = Path("fixtures/nonconform/app_llm_injection")
    if not fixture_dir.is_dir():
        # Fallback to tests fixture
        fixture_dir = Path("tests/fixtures/nonconform/app_llm_injection")

    # Step 1: Execute scan
    scan_result = scan_repository(source=str(fixture_dir), no_llm=True)
    assert "### Vibe Guard Security Audit Completed" in scan_result
    assert A2UI_DELIMITER in scan_result

    text, ui_messages = split_a2ui_payload(scan_result)
    assert len(ui_messages) == 3
    create_surface = ui_messages[0]["createSurface"]
    assert create_surface["surfaceId"] == "dashboard_canvas_surface"

    update_comps = ui_messages[1]["updateComponents"]
    comps = update_comps["components"]
    root_comp = next(c for c in comps if c["id"] == "root")
    assert root_comp["component"] == "Canvas"
    assert root_comp["autoOpen"] is True

    # Step 2: Show dashboard
    dash_result = show_dashboard()
    assert "Security audit dashboard restored" in dash_result

    # Step 3: Explain finding (SPEC-AGT-3: should succeed from cached session report)
    # Find one of the finding cards in components
    explain_btn = next(
        (c for c in comps if c.get("action", {}).get("event") == "explain_finding"),
        None,
    )
    assert explain_btn is not None, "Dashboard should contain explain_finding action buttons"

    btn_context = explain_btn["action"]["context"]
    rule_id_item = next(item for item in btn_context if item["key"] == "rule_id")
    target_rule_id = rule_id_item["value"]["literalString"]

    explain_result = explain_finding(finding_id=target_rule_id)
    assert f"Remediation Analysis: {target_rule_id}" in explain_result
    assert "GCP Remediation Guide:" in explain_result
    assert A2UI_DELIMITER in explain_result

    detail_text, detail_messages = split_a2ui_payload(explain_result)
    assert len(detail_messages) == 2
    assert detail_messages[0]["createSurface"]["surfaceId"].startswith("detail_")


def test_action_context_extraction():
    """Verify agent_executor extracts action events from Gemini Enterprise DataParts."""
    mock_part = {
        "metadata": {"mimeType": "application/json+a2ui"},
        "data": {
            "action": {
                "name": "submit_scan",
                "context": [
                    {
                        "key": "message",
                        "value": {"literalString": "Scan repository configured in form"},
                    },
                    {
                        "key": "repo_url",
                        "value": {"literalString": "https://github.com/vibe/app.git"},
                    },
                    {"key": "families", "value": {"literalString": "AUTH,SECRETS"}},
                ],
            }
        },
    }

    query, context = extract_action_context([mock_part])
    assert query == "Scan repository configured in form"
    assert context["repo_url"] == "https://github.com/vibe/app.git"
    assert context["families"] == "AUTH,SECRETS"


def test_spec_agt_4_deployed_mode_rejects_directory(monkeypatch):
    """SPEC-AGT-4: In deployed/production mode, direct directory paths must be rejected."""
    monkeypatch.setenv("VIBE_GUARD_ENV", "production")
    result = scan_repository(source="/some/local/dir", no_llm=True)
    assert "Error: In deployed mode" in result
    assert "prohibited" in result


def test_spec_agt_5_deployed_mode_rejects_unauthenticated_caller(monkeypatch):
    """SPEC-AGT-5: In deployed mode, unauthenticated callers must be rejected (401/403)."""
    monkeypatch.setenv("VIBE_GUARD_ENV", "production")
    result = scan_repository(source="https://github.com/vibe/clean_app.git", no_llm=True)
    assert "Error 401/403" in result
    assert "Unauthenticated caller" in result
