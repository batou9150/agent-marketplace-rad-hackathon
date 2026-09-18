"""Orchestrator combining Semgrep and Gitleaks scanning engines."""

from pathlib import Path
from vibe_guard.engine.gitleaks import run_gitleaks
from vibe_guard.engine.models import Finding
from vibe_guard.engine.semgrep import run_semgrep
from vibe_guard.rules.loader import RulePack

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ScanEngine:
    """Core static analysis engine orchestrating Semgrep OSS and Gitleaks."""

    def __init__(self, rule_pack: RulePack) -> None:
        self.rule_pack = rule_pack

    def scan(self, target_dir: Path) -> list[Finding]:
        """Perform a complete static analysis scan over the specified directory."""
        if not target_dir.is_dir():
            raise FileNotFoundError(f"Target scan directory not found: {target_dir}")

        findings: list[Finding] = []

        # 1. Run Semgrep for AST and syntax code rules
        semgrep_findings = run_semgrep(target_dir, self.rule_pack)
        findings.extend(semgrep_findings)

        # 2. Run Gitleaks for secrets and tokens
        gitleaks_findings = run_gitleaks(target_dir, self.rule_pack)
        findings.extend(gitleaks_findings)

        # 3. Deduplicate findings (same rule, same file, same line)
        unique_findings: list[Finding] = []
        seen_keys: set[tuple[str, str, int]] = set()

        for finding in findings:
            if finding.is_tool_error:
                unique_findings.append(finding)
                continue

            key = (finding.rule_id, finding.file_path, finding.line_number)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_findings.append(finding)

        # 4. Sort by severity then by family and file
        unique_findings.sort(
            key=lambda f: (
                SEVERITY_ORDER.get(f.severity.lower(), 99),
                f.family,
                f.file_path,
                f.line_number,
            )
        )

        return unique_findings
