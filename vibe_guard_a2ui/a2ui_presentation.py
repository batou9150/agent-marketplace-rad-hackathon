"""A2UI v0.9 presentation builders for Vibe Guard in Gemini Enterprise.

Conforms to the Gemini Enterprise Composite Catalog:
https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json
"""

import json
from typing import Any

from vibe_guard.report.models import Report, ReportFinding

GE_CATALOG_ID = (
    "https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json"
)
A2UI_DELIMITER = "---a2ui_JSON---"

SEVERITY_BADGES = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}


def wrap_a2ui_payload(messages: list[dict[str, Any]]) -> str:
    """Wrap A2UI message envelopes in the standard delimiter."""
    return f"{A2UI_DELIMITER}\n{json.dumps({'messages': messages}, indent=2)}"


def build_scan_form_surface(surface_id: str = "scan_form_surface") -> dict[str, Any]:
    """Generate A2UI v0.9 surface for repository scan configuration."""
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_CATALOG_ID,
                "theme": {"primaryColor": "#1A73E8"},
                "sendDataModel": True,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
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
                        "child": "main_col",
                    },
                    {
                        "id": "main_col",
                        "component": "MaterialColumn",
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
                        "child": "btn_text",
                        "variant": "filled",
                        "action": {
                            "event": "submit_scan",
                            "context": [
                                {
                                    "key": "message",
                                    "value": {
                                        "literalString": "Scan repository configured in form"
                                    },
                                },
                                {"key": "repo_url", "value": {"path": "/repo_url"}},
                                {"key": "branch", "value": {"path": "/branch"}},
                                {"key": "families", "value": {"path": "/families"}},
                            ],
                        },
                    },
                    {
                        "id": "btn_text",
                        "component": "MaterialText",
                        "text": "Launch Security Audit",
                        "usageHint": "body",
                    },
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": {
                    "repo_url": "",
                    "branch": "main",
                    "families": ["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"],
                },
            },
        },
    ]
    return {"messages": messages}


def build_dashboard_canvas_surface(
    report: Report, surface_id: str = "dashboard_canvas_surface"
) -> dict[str, Any]:
    """Generate A2UI v0.9 interactive Canvas security report dashboard."""
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
            "child": "metrics_col",
        },
        {
            "id": "metrics_col",
            "component": "MaterialColumn",
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
            "distribution": "spaceAround",
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
            "children": [],
        },
    ]

    finding_card_ids: list[str] = []

    for idx, finding in enumerate(report.findings):
        card_id = f"finding_card_{idx}"
        col_id = f"finding_col_{idx}"
        title_id = f"finding_title_{idx}"
        meta_id = f"finding_meta_{idx}"
        msg_id = f"finding_msg_{idx}"
        btn_id = f"finding_btn_{idx}"
        btn_text_id = f"finding_btn_txt_{idx}"

        finding_card_ids.append(card_id)

        sev_badge = SEVERITY_BADGES.get(finding.severity.lower(), finding.severity.upper())

        components.extend(
            [
                {
                    "id": card_id,
                    "component": "MaterialCard",
                    "child": col_id,
                },
                {
                    "id": col_id,
                    "component": "MaterialColumn",
                    "children": [title_id, meta_id, msg_id, btn_id],
                },
                {
                    "id": title_id,
                    "component": "MaterialText",
                    "text": f"[{sev_badge}] {finding.title}",
                    "usageHint": "h3",
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
                    "child": btn_text_id,
                    "variant": "outlined",
                    "action": {
                        "event": "explain_finding",
                        "context": [
                            {
                                "key": "message",
                                "value": {
                                    "literalString": (
                                        f"Explain finding {finding.rule_id} in {finding.file_path}"
                                    )
                                },
                            },
                            {
                                "key": "finding_id",
                                "value": {"literalString": finding.finding_id},
                            },
                            {
                                "key": "rule_id",
                                "value": {"literalString": finding.rule_id},
                            },
                        ],
                    },
                },
                {
                    "id": btn_text_id,
                    "component": "MaterialText",
                    "text": "Inspect & Remediate (GCP)",
                    "usageHint": "body",
                },
            ]
        )

    # Attach finding card IDs to the findings container
    for comp in components:
        if comp["id"] == "findings_container":
            comp["children"] = finding_card_ids
            break

    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_CATALOG_ID,
                "theme": {"primaryColor": "#1A73E8"},
                "sendDataModel": True,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/summary",
                "value": {
                    "total": report.summary.total_findings,
                    "scan_id": report.metadata.scan_id,
                },
            },
        },
    ]

    return {"messages": messages}


def build_finding_detail_surface(
    finding: ReportFinding, surface_id: str | None = None
) -> dict[str, Any]:
    """Generate A2UI v0.9 surface for in-depth remediation details."""
    if surface_id is None:
        surface_id = f"detail_{finding.finding_id[:8]}"

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
            "child": "detail_col",
        },
        {
            "id": "detail_col",
            "component": "MaterialColumn",
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
            "child": "btn_back_txt",
            "variant": "outlined",
            "action": {
                "event": "show_dashboard",
                "context": [
                    {
                        "key": "message",
                        "value": {"literalString": "Show security scan dashboard"},
                    }
                ],
            },
        },
        {
            "id": "btn_back_txt",
            "component": "MaterialText",
            "text": "← Back to Dashboard",
            "usageHint": "body",
        },
    ]

    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": GE_CATALOG_ID,
                "theme": {"primaryColor": "#1A73E8"},
                "sendDataModel": True,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": components,
            },
        },
    ]

    return {"messages": messages}
