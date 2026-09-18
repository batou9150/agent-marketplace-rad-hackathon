"""A2UI v0.9 presentation builders for Vibe Guard in Gemini Enterprise.

Conforms to the Gemini Enterprise Composite Catalog:
https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json

A vendored copy of that catalog, of the A2UI v0.9 server-to-client message schema
and of the shared common types lives in `vibe_guard_a2ui/schemas/`; every surface
built here is validated against them by `tests/unit/test_a2ui_conformance.py`.
"""

import json
import uuid
from typing import Any

from vibe_guard.report.models import Report, ReportFinding

GE_CATALOG_ID = (
    "https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json"
)
A2UI_DELIMITER = "---a2ui_JSON---"
A2UI_VERSION = "v0.9"
PRIMARY_COLOR = "#1A73E8"

SEVERITY_BADGES = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

SEVERITY_COLORS = {
    "critical": "#B3261E",
    "high": "#C7601A",
    "medium": "#8A6100",
    "low": "#1A73E8",
}


def new_surface_id(prefix: str) -> str:
    """Mint a fresh surface id.

    Gemini Enterprise requires a new, unique `surfaceId` per response: re-sending
    `createSurface` for a live surface is an error in the A2UI v0.9 spec, and the
    Gemini Enterprise renderer misbehaves when an id is reused across responses.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def wrap_a2ui_payload(messages: list[dict[str, Any]]) -> str:
    """Wrap A2UI message envelopes in the standard delimiter."""
    return f"{A2UI_DELIMITER}\n{json.dumps({'messages': messages}, indent=2)}"


def _create_surface(surface_id: str) -> dict[str, Any]:
    """Build the `createSurface` envelope shared by every Vibe Guard surface."""
    return {
        "version": A2UI_VERSION,
        "createSurface": {
            "surfaceId": surface_id,
            "catalogId": GE_CATALOG_ID,
            "theme": {"primaryColor": PRIMARY_COLOR},
            "sendDataModel": True,
        },
    }


def _update_components(surface_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the `updateComponents` envelope for a surface."""
    return {
        "version": A2UI_VERSION,
        "updateComponents": {"surfaceId": surface_id, "components": components},
    }


def _update_data_model(surface_id: str, path: str, value: Any) -> dict[str, Any]:
    """Build the `updateDataModel` envelope for a surface."""
    return {
        "version": A2UI_VERSION,
        "updateDataModel": {"surfaceId": surface_id, "path": path, "value": value},
    }


def _action(name: str, prompt: str, **context: Any) -> dict[str, Any]:
    """Build an A2UI v0.9 server-side event action.

    `context.prompt` is what the Gemini Enterprise client replays as the user's
    chat message; the remaining entries are literals or `{"path": ...}` data
    bindings resolved against the surface data model.
    """
    return {"event": {"name": name, "context": {"prompt": prompt, **context}}}


def build_scan_form_surface(surface_id: str | None = None) -> dict[str, Any]:
    """Generate A2UI v0.9 surface for repository scan configuration."""
    surface_id = surface_id or new_surface_id("scan-form")
    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Canvas",
            "cardTitle": "Vibe Guard Audit",
            "cardDescription": "Security scanner for vibe-coded applications",
            "cardIcon": "security",
            "autoOpen": True,
            "children": ["main_card"],
        },
        {
            "id": "main_card",
            "component": "MaterialCard",
            "children": ["main_col"],
        },
        {
            "id": "main_col",
            "component": "MaterialColumn",
            "align": "stretch",
            "style": {"gap": "12px"},
            "children": [
                "title_text",
                "desc_text",
                "divider_1",
                "input_repo_url",
                "input_branch",
                "family_picker",
                "divider_2",
                "btn_submit",
            ],
        },
        {
            "id": "title_text",
            "component": "MaterialText",
            "text": "Scan a Repository for Security Risks",
            "usageHint": "h2",
        },
        {
            "id": "desc_text",
            "component": "MaterialText",
            "text": (
                "Detect non-conformities across AUTH, SECRETS, LLM-GOV, "
                "and NET-ISO with GCP-native remediations."
            ),
            "usageHint": "body",
        },
        {"id": "divider_1", "component": "MaterialDivider"},
        {
            "id": "input_repo_url",
            "component": "MaterialInput",
            "label": "Repository URL or Archive Path",
            "placeholder": "https://github.com/org/repo.git or /path/to/archive.zip",
            "type": "text",
            "value": {"path": "/repo_url"},
        },
        {
            "id": "input_branch",
            "component": "MaterialInput",
            "label": "Branch / Git Reference (optional)",
            "placeholder": "main",
            "type": "text",
            "value": {"path": "/branch"},
        },
        {
            "id": "family_picker",
            "component": "ChoicePicker",
            "label": "Inspection Families",
            "variant": "multipleSelection",
            "options": [
                {"value": "AUTH", "label": "Authentication & IAM (AUTH)"},
                {"value": "SECRETS", "label": "Hardcoded Secrets (SECRETS)"},
                {"value": "LLM-GOV", "label": "LLM Governance (LLM-GOV)"},
                {"value": "NET-ISO", "label": "Network Isolation (NET-ISO)"},
            ],
            "value": {"path": "/families"},
        },
        {"id": "divider_2", "component": "MaterialDivider"},
        {
            "id": "btn_submit",
            "component": "MaterialButton",
            "label": "Launch Security Audit",
            "appearance": "filled",
            "color": "primary",
            "action": _action(
                "submit_scan",
                "Scan the repository configured in the form",
                repo_url={"path": "/repo_url"},
                branch={"path": "/branch"},
                families={"path": "/families"},
            ),
        },
    ]

    return {
        "messages": [
            _create_surface(surface_id),
            _update_components(surface_id, components),
            _update_data_model(
                surface_id,
                "/",
                {
                    "repo_url": "",
                    "branch": "main",
                    "families": ["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"],
                },
            ),
        ]
    }


def build_dashboard_canvas_surface(report: Report, surface_id: str | None = None) -> dict[str, Any]:
    """Generate A2UI v0.9 interactive Canvas security report dashboard."""
    surface_id = surface_id or new_surface_id("dashboard")
    finding_card_ids = [f"finding_card_{idx}" for idx in range(len(report.findings))]

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Canvas",
            "cardTitle": f"Vibe Guard Audit ({report.metadata.target})",
            "cardDescription": (
                f"Scan {report.metadata.scan_id[:8]} • "
                f"{report.summary.total_findings} findings found"
            ),
            "cardIcon": "security",
            "autoOpen": True,
            "children": ["metrics_card", "findings_container"],
        },
        # Metrics Card
        {
            "id": "metrics_card",
            "component": "MaterialCard",
            "children": ["metrics_col"],
        },
        {
            "id": "metrics_col",
            "component": "MaterialColumn",
            "align": "stretch",
            "style": {"gap": "8px"},
            "children": [
                "metrics_title",
                "metrics_row",
                "engine_status_text",
            ],
        },
        {
            "id": "metrics_title",
            "component": "MaterialText",
            "text": "Security Posture Summary",
            "usageHint": "h2",
        },
        {
            "id": "metrics_row",
            "component": "MaterialRow",
            "justify": "spaceAround",
            "children": [
                "badge_crit",
                "badge_high",
                "badge_med",
                "badge_low",
            ],
        },
        {
            "id": "badge_crit",
            "component": "MaterialText",
            "text": f"🔴 Critical: {report.summary.by_severity.get('critical', 0)}",
            "usageHint": "h3",
        },
        {
            "id": "badge_high",
            "component": "MaterialText",
            "text": f"🟠 High: {report.summary.by_severity.get('high', 0)}",
            "usageHint": "h3",
        },
        {
            "id": "badge_med",
            "component": "MaterialText",
            "text": f"🟡 Medium: {report.summary.by_severity.get('medium', 0)}",
            "usageHint": "h3",
        },
        {
            "id": "badge_low",
            "component": "MaterialText",
            "text": f"🔵 Low: {report.summary.by_severity.get('low', 0)}",
            "usageHint": "h3",
        },
        {
            "id": "engine_status_text",
            "component": "MaterialText",
            "text": (
                f"Engines: Semgrep ({report.engine_status.semgrep.status}) • "
                f"Gitleaks ({report.engine_status.gitleaks.status}) • "
                f"Duration: {report.metadata.duration_seconds:.2f}s"
            ),
            "usageHint": "caption",
        },
        # Findings Container
        {
            "id": "findings_container",
            "component": "MaterialColumn",
            "align": "stretch",
            "style": {"gap": "12px"},
            "children": finding_card_ids,
        },
    ]

    for idx, finding in enumerate(report.findings):
        card_id = finding_card_ids[idx]
        col_id = f"finding_col_{idx}"
        title_id = f"finding_title_{idx}"
        meta_id = f"finding_meta_{idx}"
        msg_id = f"finding_msg_{idx}"
        btn_id = f"finding_btn_{idx}"

        severity = finding.severity.lower()
        sev_badge = SEVERITY_BADGES.get(severity, finding.severity.upper())

        components.extend(
            [
                {
                    "id": card_id,
                    "component": "MaterialCard",
                    "children": [col_id],
                },
                {
                    "id": col_id,
                    "component": "MaterialColumn",
                    "align": "stretch",
                    "style": {"gap": "4px"},
                    "children": [title_id, meta_id, msg_id, btn_id],
                },
                {
                    "id": title_id,
                    "component": "MaterialText",
                    "text": f"[{sev_badge}] {finding.title}",
                    "usageHint": "h3",
                    "style": {"color": SEVERITY_COLORS.get(severity, "#1F1F1F")},
                },
                {
                    "id": meta_id,
                    "component": "MaterialText",
                    "text": (
                        f"Rule: {finding.rule_id} • "
                        f"Family: {finding.family} • "
                        f"{finding.file_path}:{finding.line_number}"
                    ),
                    "usageHint": "caption",
                },
                {
                    "id": msg_id,
                    "component": "MaterialText",
                    "text": finding.message,
                    "usageHint": "body",
                },
                {
                    "id": btn_id,
                    "component": "MaterialButton",
                    "label": "Inspect & Remediate (GCP)",
                    "appearance": "outlined",
                    "action": _action(
                        "explain_finding",
                        f"Explain finding {finding.rule_id} in {finding.file_path}",
                        finding_id=finding.finding_id,
                        rule_id=finding.rule_id,
                    ),
                },
            ]
        )

    return {
        "messages": [
            _create_surface(surface_id),
            _update_components(surface_id, components),
            _update_data_model(
                surface_id,
                "/summary",
                {
                    "total": report.summary.total_findings,
                    "scan_id": report.metadata.scan_id,
                },
            ),
        ]
    }


def build_finding_detail_surface(
    finding: ReportFinding, surface_id: str | None = None
) -> dict[str, Any]:
    """Generate A2UI v0.9 surface for in-depth remediation details."""
    surface_id = surface_id or new_surface_id("detail")

    snippet_content = finding.snippet.content if finding.snippet else "Snippet not available."
    remediation_steps_text = "\n".join(
        f"{idx + 1}. {step}" for idx, step in enumerate(finding.remediation.steps)
    )

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Canvas",
            "cardTitle": f"Remediation: {finding.rule_id}",
            "cardDescription": finding.title,
            "cardIcon": "build",
            "autoOpen": True,
            "children": ["detail_card"],
        },
        {
            "id": "detail_card",
            "component": "MaterialCard",
            "children": ["detail_col"],
        },
        {
            "id": "detail_col",
            "component": "MaterialColumn",
            "align": "stretch",
            "style": {"gap": "8px"},
            "children": [
                "detail_title",
                "detail_loc",
                "divider_1",
                "snippet_heading",
                "snippet_code",
                "divider_2",
                "remed_heading",
                "remed_summary",
                "remed_steps",
                "remed_service",
                "divider_3",
                "btn_back",
            ],
        },
        {
            "id": "detail_title",
            "component": "MaterialText",
            "text": f"[{finding.severity.upper()}] {finding.title}",
            "usageHint": "h2",
            "style": {"color": SEVERITY_COLORS.get(finding.severity.lower(), "#1F1F1F")},
        },
        {
            "id": "detail_loc",
            "component": "MaterialText",
            "text": (
                f"Location: {finding.file_path}:{finding.line_number} • Rule: {finding.rule_id}"
            ),
            "usageHint": "caption",
        },
        {"id": "divider_1", "component": "MaterialDivider"},
        {
            "id": "snippet_heading",
            "component": "MaterialText",
            "text": "Code Context (Sanitized snippet):",
            "usageHint": "h3",
        },
        {
            "id": "snippet_code",
            "component": "MaterialText",
            "text": snippet_content,
            "usageHint": "body",
            "style": {
                "fontFamily": "monospace",
                "whiteSpace": "pre-wrap",
                "backgroundColor": "#F1F3F4",
                "borderRadius": "6px",
                "padding": "8px",
                "overflowX": "auto",
            },
        },
        {"id": "divider_2", "component": "MaterialDivider"},
        {
            "id": "remed_heading",
            "component": "MaterialText",
            "text": "GCP Remediation Guide:",
            "usageHint": "h3",
        },
        {
            "id": "remed_summary",
            "component": "MaterialText",
            "text": finding.remediation.summary,
            "usageHint": "body",
        },
        {
            "id": "remed_steps",
            "component": "MaterialText",
            "text": remediation_steps_text,
            "usageHint": "body",
            "style": {"whiteSpace": "pre-wrap"},
        },
        {
            "id": "remed_service",
            "component": "MaterialText",
            "text": f"Target GCP Service: {finding.remediation.gcp_service}",
            "usageHint": "caption",
        },
        {"id": "divider_3", "component": "MaterialDivider"},
        {
            "id": "btn_back",
            "component": "MaterialButton",
            "label": "← Back to Dashboard",
            "appearance": "outlined",
            "action": _action("show_dashboard", "Show the security scan dashboard"),
        },
    ]

    return {
        "messages": [
            _create_surface(surface_id),
            _update_components(surface_id, components),
        ]
    }
