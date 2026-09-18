"""ADK Root Agent for Vibe Guard with A2UI v0.9 support for Gemini Enterprise.

Conforms to SPEC-AGT-1, SPEC-AGT-2, and SPEC-AGT-3.
"""

import contextlib
import json
import logging
import os
import time
import uuid
from pathlib import Path

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder
from vibe_guard.engine.models import Finding
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError
from vibe_guard.report.builder import build_report
from vibe_guard.report.models import Report, ReportFinding
from vibe_guard.rules.loader import RulePack, load_rule_pack
from vibe_guard.rules.models import Family
from vibe_guard_a2ui.a2ui_presentation import (
    A2UI_DELIMITER,
    build_dashboard_canvas_surface,
    build_finding_detail_surface,
    build_scan_form_surface,
    wrap_a2ui_payload,
)

logger = logging.getLogger(__name__)

# Fallback session cache for environments where ToolContext.state is ephemeral
_SESSION_REPORTS: dict[str, Report] = {}


def _find_rules_directory() -> Path:
    """Resolve rules directory relative to workspace or package."""
    candidates = [
        Path.cwd() / "rules",
        Path(__file__).resolve().parent.parent / "rules",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "pack.yaml").is_file():
            return candidate
    raise FileNotFoundError("Could not locate Vibe Guard rules directory with pack.yaml")


def _get_session_id(tool_context: ToolContext | None) -> str:
    """Extract or generate a session ID."""
    if tool_context and tool_context.session:
        return getattr(tool_context.session, "id", "default_session")
    return "default_session"


def _store_report(report: Report, tool_context: ToolContext | None) -> None:
    """Store report in session state and in-memory cache."""
    session_id = _get_session_id(tool_context)
    _SESSION_REPORTS[session_id] = report
    if tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        tool_context.state["latest_report"] = report.model_dump_json()


def _retrieve_report(tool_context: ToolContext | None) -> Report | None:
    """Retrieve report from session state or in-memory cache."""
    session_id = _get_session_id(tool_context)
    if tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        raw_json = tool_context.state.get("latest_report")
        if raw_json:
            try:
                data = json.loads(raw_json)
                return Report.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to deserialized report from session state: {e}")
    return _SESSION_REPORTS.get(session_id)


def render_scan_form(tool_context: ToolContext | None = None) -> str:
    """Display the interactive scan configuration form in Gemini Enterprise.

    Returns:
        Greeting text with A2UI v0.9 envelope containing the repository form.
    """
    _ = tool_context
    greeting = (
        "Welcome to **Vibe Guard**! I am your autonomous AI security auditor for "
        "vibe-coded applications on Google Cloud Platform.\n\n"
        "Configure your repository scan below or enter a Git HTTPS URL directly."
    )
    ui_envelope = build_scan_form_surface()
    return f"{greeting}\n\n{wrap_a2ui_payload(ui_envelope['messages'])}"


def scan_repository(
    source: str,
    branch: str = "main",
    families: list[str] | None = None,
    no_llm: bool = True,
    tool_context: ToolContext | None = None,
) -> str:
    """Perform a static security audit of a repository or archive.

    SPEC-AGT-1 & SPEC-AGT-4 compliant:
    Clones or extracts the target into an ephemeral workspace, runs Semgrep and Gitleaks,
    and returns an executive dashboard in Gemini Enterprise.

    Args:
        source: Git repository HTTPS URL or path to a zip/tar archive.
        branch: Optional Git branch or commit ref.
        families: Optional list of inspection families ('AUTH', 'SECRETS', 'LLM-GOV', 'NET-ISO').
        no_llm: If True, skips LLM-based contextual remediation enrichment for faster scans.
        tool_context: ADK ToolContext for session state.

    Returns:
        Summary text and the A2UI Canvas dashboard envelope.
    """
    # SPEC-AGT-4: In deployed/production mode, raw directory paths are rejected
    is_deployed = os.environ.get("VIBE_GUARD_ENV", "development").lower() == "production"
    source_clean = source.strip()

    if is_deployed and not (
        source_clean.startswith(("http://", "https://"))
        or source_clean.endswith((".zip", ".tar.gz", ".tgz", ".tar"))
    ):
        return (
            "Error: In deployed mode, only Git repository URLs or archive uploads are permitted. "
            f"Direct local paths are prohibited. Received: {source}"
        )

    # SPEC-AGT-5: Require authenticated caller in deployed mode
    caller_id = None
    if tool_context and hasattr(tool_context, "user_id") and tool_context.user_id:
        caller_id = tool_context.user_id
    elif not is_deployed:
        caller_id = "gemini_enterprise_user"

    unauth = ("anonymous", "unauthenticated", "none")
    if is_deployed and (not caller_id or caller_id.lower() in unauth):
        return (
            "Error 401/403: Unauthenticated caller. "
            "Scans cannot be executed without an authenticated caller identity."
        )

    scan_id = str(uuid.uuid4())
    start_time = time.time()

    # Load and filter rule pack
    rules_dir = _find_rules_directory()
    rule_pack = load_rule_pack(rules_dir)

    if families:
        valid_family_enums = set()
        for f in families:
            with contextlib.suppress(ValueError):
                valid_family_enums.add(Family(f.strip()))
        if valid_family_enums:
            filtered_rules = [r for r in rule_pack.rules if r.family in valid_family_enums]
            rule_pack = RulePack(
                manifest=rule_pack.manifest,
                rules=filtered_rules,
                directory=rule_pack.directory,
            )

    findings: list[Finding] = []

    try:
        # Check if local directory path (allowed in test/development mode)
        target_path = Path(source_clean)
        if not is_deployed and target_path.is_dir():
            engine = ScanEngine(rule_pack)
            findings = engine.scan(target_path)
        else:
            with EphemeralWorkspace() as workspace:
                if source_clean.startswith(("http://", "https://")):
                    scan_dir = workspace.clone_git(source_clean, branch=branch)
                elif source_clean.endswith((".zip", ".tar.gz", ".tgz", ".tar")):
                    scan_dir = workspace.extract_archive(source_clean)
                else:
                    raise IngestionError(f"Unsupported source format: {source_clean}")

                engine = ScanEngine(rule_pack)
                findings = engine.scan(scan_dir)

    except IngestionError as exc:
        logger.error(f"Ingestion failed: {exc}")
        return f"Scan failed during source ingestion: {exc}"
    except Exception as exc:
        logger.error(f"Scan failed: {exc}", exc_info=True)
        return f"Internal scan error: {exc}"

    duration_seconds = time.time() - start_time

    # Build validated report
    report = build_report(
        findings=findings,
        scan_id=scan_id,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        duration_seconds=duration_seconds,
        caller_id=caller_id,
        pack_version=rule_pack.version,
        target=source_clean,
        llm_remediation_enabled=not no_llm,
    )

    # Record Audit (C6, SPEC-AUD-1, SPEC-AUD-2)
    try:
        recorder = AuditRecorder()
        audit_record = ScanAuditRecord.from_scan(
            scan_id=scan_id,
            timestamp=report.timestamp,
            duration_seconds=duration_seconds,
            caller_id=caller_id,
            pack_version=rule_pack.version,
            target=source_clean,
            findings=findings,
            rules_evaluated=[r.id for r in rule_pack.rules],
        )
        recorder.record(audit_record)
    except Exception as exc:
        logger.warning(f"Failed to persist audit log: {exc}")

    # Cache report in session for follow-up questions / explain_finding
    _store_report(report, tool_context)

    # Format text response
    crit_count = report.summary.by_severity.get("critical", 0)
    high_count = report.summary.by_severity.get("high", 0)
    total = report.summary.total_findings

    summary_msg = (
        f"### Vibe Guard Security Audit Completed\n\n"
        f"**Target**: `{source_clean}`\n"
        f"**Duration**: {duration_seconds:.2f}s | **Findings**: {total} total "
        f"(🔴 {crit_count} Critical, 🟠 {high_count} High)\n\n"
        "The interactive security audit dashboard has been opened in your Canvas side-panel. "
        "Click on any finding card to inspect the code snippet and GCP-native "
        "remediation instructions."
    )

    canvas_envelope = build_dashboard_canvas_surface(report)
    return f"{summary_msg}\n\n{wrap_a2ui_payload(canvas_envelope['messages'])}"


def explain_finding(
    finding_id: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Explain a specific security finding from the current session report.

    SPEC-AGT-3 compliant:
    Strictly answers from the cached report in the active session without triggering a new scan.

    Args:
        finding_id: The finding ID or rule ID to explain.
        tool_context: ADK ToolContext for session state.

    Returns:
        Explanation text with A2UI finding detail Canvas envelope.
    """
    report = _retrieve_report(tool_context)
    if not report:
        return (
            "No active security report was found in this session. "
            "Please run a repository scan first using `scan_repository`."
        )

    # Search by finding_id or rule_id
    target_finding: ReportFinding | None = None
    for f in report.findings:
        if f.finding_id == finding_id or f.rule_id == finding_id:
            target_finding = f
            break

    if not target_finding:
        available_ids = [f"{f.rule_id} ({f.finding_id[:8]})" for f in report.findings[:5]]
        ids_str = ", ".join(available_ids)
        return (
            f"Finding `{finding_id}` was not found in the current report.\n"
            f"Available findings include: {ids_str}"
        )

    detail_envelope = build_finding_detail_surface(target_finding)

    explanation_msg = (
        f"### Remediation Analysis: {target_finding.rule_id} - {target_finding.title}\n\n"
        f"- **Severity**: {target_finding.severity.upper()}\n"
        f"- **Location**: `{target_finding.file_path}:{target_finding.line_number}`\n"
        f"- **Target GCP Service**: {target_finding.remediation.gcp_service}\n\n"
        f"**Remediation Steps**:\n"
        + "\n".join(f"{i+1}. {step}" for i, step in enumerate(target_finding.remediation.steps))
        + "\n\n"
        "Detailed code snippet and remediation guidance loaded in the Canvas side-panel."
    )

    return f"{explanation_msg}\n\n{wrap_a2ui_payload(detail_envelope['messages'])}"


def show_dashboard(tool_context: ToolContext | None = None) -> str:
    """Restore the executive security dashboard Canvas for the current session."""
    report = _retrieve_report(tool_context)
    if not report:
        return render_scan_form(tool_context)

    canvas_envelope = build_dashboard_canvas_surface(report)
    msg = "Security audit dashboard restored to Canvas side-panel."
    return f"{msg}\n\n{wrap_a2ui_payload(canvas_envelope['messages'])}"


SYSTEM_INSTRUCTION = (
    "You are Vibe Guard, an autonomous security auditor for vibe-coded applications on GCP.\n"
    "You help engineers identify and remediate security vulnerabilities across "
    "AUTH, SECRETS, LLM-GOV, and NET-ISO.\n\n"
    "A2UI & GEMINI ENTERPRISE INTERFACE RULES:\n"
    "1. When greeted or when the user wants to scan a project, invoke `render_scan_form`.\n"
    "2. When the user submits the form or provides a repository URL, invoke `scan_repository`.\n"
    "3. When the user asks to explain a finding, invoke `explain_finding`.\n"
    "4. When the user wants to return to the dashboard, invoke `show_dashboard`.\n"
    "5. NEVER fabricate scan metrics or vulnerability counts. "
    "All reports must come from `scan_repository`.\n"
    f"6. Whenever a tool returns an A2UI payload containing `{A2UI_DELIMITER}`, "
    "preserve the entire payload unaltered in your response.\n"
    "7. Be concise, actionable, and focus on GCP-native security best practices "
    "(Secret Manager, Identity-Aware Proxy, VPC Service Controls, Cloud Run ingress).\n"
)

root_agent = LlmAgent(
    name="VibeGuardAgent",
    model=os.getenv("ADK_MODEL", os.getenv("VG_LLM_MODEL", "gemini-3.8-flash")),
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        render_scan_form,
        scan_repository,
        explain_finding,
        show_dashboard,
    ],
)
