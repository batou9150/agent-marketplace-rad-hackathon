"""Report models, prioritization, JSON schema, and Markdown rendering."""

from vibe_guard.report.builder import build_report, deduplicate_findings
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
from vibe_guard.report.renderer import render_json, render_markdown

__all__ = [
    "EngineStatus",
    "Report",
    "ReportFinding",
    "ReportMetadata",
    "ReportRemediation",
    "ReportSnippet",
    "ReportSummary",
    "ScannerStatus",
    "build_report",
    "deduplicate_findings",
    "render_json",
    "render_markdown",
]
