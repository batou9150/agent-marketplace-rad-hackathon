"""Unit tests for A2UI v0.9 presentation builders."""

import json

from vibe_guard.report.models import (
    EngineStatus,
    Report,
    ReportFinding,
    ReportMetadata,
    ReportRemediation,
    ReportSnippet,
    ReportSummary,
    ScannerStatus,
)
from vibe_guard_a2ui.a2ui_presentation import (
    A2UI_DELIMITER,
    GE_CATALOG_ID,
    build_dashboard_canvas_surface,
    build_finding_detail_surface,
    build_scan_form_surface,
    wrap_a2ui_payload,
)


def _make_dummy_report() -> Report:
    finding = ReportFinding(
        finding_id="f-12345678",
        rule_id="AUTH-001",
        family="AUTH",
        severity="critical",
        title="Hardcoded API Key in Client Code",
        message="Found hardcoded GCP API key.",
        file_path="src/config.py",
        line_number=42,
        snippet=ReportSnippet(
            start_line=38,
            end_line=46,
            highlight_line=42,
            content="API_KEY = 'AIzaSyD...'",
        ),
        remediation=ReportRemediation(
            summary="Migrate secret to Secret Manager",
            gcp_service="Secret Manager",
            steps=[
                "Create secret in GCP Secret Manager",
                "Grant Secret Accessor to Cloud Run Service Account",
            ],
        ),
    )
    return Report(
        metadata=ReportMetadata(
            scan_id="scan-abc-123",
            timestamp="2026-09-18T10:00:00Z",
            duration_seconds=3.14,
            caller_id="test_user",
            pack_version="1.0.0",
            target="https://github.com/example/vibe-app.git",
        ),
        summary=ReportSummary(
            total_findings=1,
            by_severity={"critical": 1, "high": 0, "medium": 0, "low": 0},
            by_family={"AUTH": 1},
        ),
        engine_status=EngineStatus(
            semgrep=ScannerStatus(status="ok"),
            gitleaks=ScannerStatus(status="ok"),
        ),
        findings=[finding],
    )


def test_build_scan_form_surface():
    result = build_scan_form_surface("test_scan_form")
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 3

    create_msg = messages[0]["createSurface"]
    assert create_msg["surfaceId"] == "test_scan_form"
    assert create_msg["catalogId"] == GE_CATALOG_ID
    assert create_msg["sendDataModel"] is True

    update_msg = messages[1]["updateComponents"]
    assert update_msg["surfaceId"] == "test_scan_form"
    components = update_msg["components"]

    root = next(c for c in components if c["id"] == "root")
    assert root["component"] == "Canvas"
    assert root["autoOpen"] is True
    assert "main_card" in root["children"]

    # Verify MaterialInput exists (and NOT TextField)
    input_repo = next(c for c in components if c["id"] == "input_repo_url")
    assert input_repo["component"] == "MaterialInput"


def test_build_dashboard_canvas_surface():
    report = _make_dummy_report()
    result = build_dashboard_canvas_surface(report, "test_dashboard")
    assert "messages" in result
    messages = result["messages"]

    update_msg = messages[1]["updateComponents"]
    components = update_msg["components"]

    root = next(c for c in components if c["id"] == "root")
    assert root["component"] == "Canvas"
    assert root["autoOpen"] is True
    assert "metrics_card" in root["children"]
    assert "findings_container" in root["children"]

    # Check finding card rendered
    finding_card = next(c for c in components if c["id"] == "finding_card_0")
    assert finding_card["component"] == "MaterialCard"

    # Check action event is explain_finding
    btn = next(c for c in components if c["id"] == "finding_btn_0")
    assert btn["action"]["event"] == "explain_finding"


def test_build_finding_detail_surface():
    report = _make_dummy_report()
    finding = report.findings[0]
    result = build_finding_detail_surface(finding, "test_detail")
    messages = result["messages"]

    update_msg = messages[1]["updateComponents"]
    components = update_msg["components"]

    root = next(c for c in components if c["id"] == "root")
    assert root["component"] == "Canvas"
    assert "detail_card" in root["children"]

    snippet_comp = next(c for c in components if c["id"] == "snippet_code")
    assert "API_KEY" in snippet_comp["text"]


def test_wrap_a2ui_payload():
    payload = wrap_a2ui_payload([{"version": "v0.9"}])
    assert payload.startswith(A2UI_DELIMITER)
    parsed = json.loads(payload.split(A2UI_DELIMITER)[1].strip())
    assert "messages" in parsed
