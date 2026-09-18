import subprocess
from collections.abc import Sequence

from vibe_guard.engine.gitleaks import _find_gitleaks_binary
from vibe_guard.engine.models import Finding
from vibe_guard.engine.semgrep import _find_semgrep_binary
from vibe_guard.report.masking import mask_secrets_in_text
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

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _get_semgrep_version() -> str | None:
    """Extract semgrep CLI version string."""
    try:
        bin_path = _find_semgrep_binary()
        res = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _get_gitleaks_version() -> str | None:
    """Extract gitleaks CLI version string."""
    try:
        bin_path = _find_gitleaks_binary()
        if bin_path:
            res = subprocess.run([bin_path, "version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return res.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def deduplicate_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Group redundant findings on the same rule, file, and contiguous lines (ADR-005b)."""
    if not findings:
        return []

    # Filter out tool errors from regular findings
    actionable = [f for f in findings if not f.is_tool_error]
    if not actionable:
        return []

    # Group by (rule_id, file_path) while preserving first occurrence order
    groups: dict[tuple[str, str], list[Finding]] = {}
    first_seen: dict[tuple[str, str], int] = {}

    for idx, f in enumerate(actionable):
        key = (f.rule_id, f.file_path)
        if key not in groups:
            groups[key] = []
            first_seen[key] = idx
        groups[key].append(f)

    # For each group, sort by line_number and merge contiguous lines (within 2 lines)
    ordered_results: list[tuple[int, Finding]] = []
    for key, group_findings in groups.items():
        sorted_group = sorted(group_findings, key=lambda f: f.line_number)
        merged: list[Finding] = []
        for f in sorted_group:
            if not merged:
                merged.append(f)
                continue
            prev = merged[-1]
            if abs(f.line_number - prev.line_number) <= 2:
                continue
            merged.append(f)

        base_idx = first_seen[key]
        for sub_idx, f in enumerate(merged):
            ordered_results.append((base_idx + sub_idx, f))

    ordered_results.sort(key=lambda item: item[0])
    return [item[1] for item in ordered_results]


def build_report(
    findings: Sequence[Finding],
    scan_id: str,
    timestamp: str,
    duration_seconds: float,
    caller_id: str,
    pack_version: str,
    target: str,
    llm_remediation_enabled: bool = False,
    contextual_advices: dict[str, str] | None = None,
) -> Report:
    """Construct a complete, sorted, and validated Report."""
    contextual_advices = contextual_advices or {}
    deduped = deduplicate_findings(findings)

    # Sort by severity, family, file_path, line_number
    sorted_findings = sorted(
        deduped,
        key=lambda f: (
            SEVERITY_ORDER.get(f.severity.lower(), 99),
            f.family,
            f.file_path,
            f.line_number,
        ),
    )

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_family = {"AUTH": 0, "SECRETS": 0, "LLM-GOV": 0, "NET-ISO": 0}

    # Check scanner errors to populate engine_status (SPEC-ENG-4, SPEC-REP-6)
    tool_errors = [f for f in findings if f.is_tool_error]
    semgrep_errors = [f for f in tool_errors if "SEMGREP" in f.rule_id.upper()]
    gitleaks_errors = [f for f in tool_errors if "GITLEAKS" in f.rule_id.upper()]

    if semgrep_errors:
        semgrep_status = ScannerStatus(
            status="error",
            error_message=semgrep_errors[0].message,
            covered_families=[],
            degraded_families=["AUTH", "LLM-GOV", "NET-ISO"],
        )
    else:
        semgrep_status = ScannerStatus(
            status="ok",
            version=_get_semgrep_version(),
            covered_families=["AUTH", "LLM-GOV", "NET-ISO"],
            degraded_families=[],
        )

    if gitleaks_errors:
        gitleaks_status = ScannerStatus(
            status="error",
            error_message=gitleaks_errors[0].message,
            covered_families=[],
            degraded_families=["SECRETS"],
        )
    else:
        gitleaks_status = ScannerStatus(
            status="ok",
            version=_get_gitleaks_version(),
            covered_families=["SECRETS"],
            degraded_families=[],
        )

    coverage_degraded = sorted(
        set(semgrep_status.degraded_families + gitleaks_status.degraded_families)
    )
    engine_status = EngineStatus(
        semgrep=semgrep_status,
        gitleaks=gitleaks_status,
        coverage_degraded=coverage_degraded,
    )

    report_findings: list[ReportFinding] = []
    for f in sorted_findings:
        sev_key = f.severity.lower()
        if sev_key in by_severity:
            by_severity[sev_key] += 1
        if f.family in by_family:
            by_family[f.family] += 1

        explicit = [f.detected_secret] if f.detected_secret else None

        snippet_model = None
        if f.snippet:
            masked_snippet_content = mask_secrets_in_text(
                f.snippet.content, explicit_secrets=explicit
            )
            snippet_model = ReportSnippet(
                start_line=f.snippet.start_line,
                end_line=f.snippet.end_line,
                highlight_line=f.snippet.highlight_line,
                content=masked_snippet_content,
            )

        masked_message = mask_secrets_in_text(f.message, explicit_secrets=explicit)

        # Contextual advice lookup by rule_id or unique finding key
        finding_key = f"{f.rule_id}:{f.file_path}:{f.line_number}"
        adv = contextual_advices.get(finding_key) or contextual_advices.get(f.rule_id)

        remediation_model = ReportRemediation(
            summary=f.remediation_summary or "Consulter la documentation de sécurité GCP.",
            gcp_service=f.remediation_gcp_service or "Google Cloud Platform",
            steps=f.remediation_steps
            or ["Appliquer les recommandations d'architecture sécurisée."],
            contextual_advice=adv,
        )

        report_findings.append(
            ReportFinding(
                rule_id=f.rule_id,
                family=f.family,
                severity=f.severity.lower(),
                title=f.title,
                message=masked_message,
                file_path=f.file_path,
                line_number=f.line_number,
                snippet=snippet_model,
                remediation=remediation_model,
            )
        )

    metadata = ReportMetadata(
        scan_id=scan_id,
        timestamp=timestamp,
        duration_seconds=round(duration_seconds, 3),
        caller_id=caller_id,
        pack_version=pack_version,
        target=target,
        llm_remediation_enabled=llm_remediation_enabled,
    )

    summary = ReportSummary(
        total_findings=len(report_findings),
        by_severity=by_severity,
        by_family=by_family,
    )

    return Report(
        metadata=metadata,
        summary=summary,
        engine_status=engine_status,
        findings=report_findings,
    )
