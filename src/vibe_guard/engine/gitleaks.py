"""Gitleaks secret scanner executor and result normalizer for Vibe Guard."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from vibe_guard.engine.models import Finding
from vibe_guard.engine.snippet import extract_bounded_snippet
from vibe_guard.rules.loader import RulePack


def _find_gitleaks_binary() -> str | None:
    """Locate the gitleaks executable."""
    for candidate in ["/opt/homebrew/bin/gitleaks", "/usr/local/bin/gitleaks"]:
        if Path(candidate).is_file():
            return candidate
    return shutil.which("gitleaks")


def run_gitleaks(scan_dir: Path, rule_pack: RulePack) -> list[Finding]:
    """Execute Gitleaks detection on the scanned directory and normalize findings."""
    gitleaks_bin = _find_gitleaks_binary()
    if not gitleaks_bin:
        return [
            Finding.create_tool_error(
                "gitleaks",
                "Gitleaks executable not found on host or container PATH.",
            )
        ]

    # Map rule definitions from pack for SECRETS
    secrets_rules = rule_pack.by_family("SECRETS")
    default_secret_rule = rule_pack.get_rule("SECRETS-001") or (
        secrets_rules[0] if secrets_rules else None
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="gitleaks_report_",
        delete=False,
    ) as tmp_report:
        report_path = Path(tmp_report.name)

    try:
        cmd = [
            gitleaks_bin,
            "detect",
            "--source",
            str(scan_dir),
            "--no-git",
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--exit-code",
            "0",
            "--no-banner",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if result.returncode != 0:
            err_msg = result.stderr.strip() or f"Gitleaks exited with status {result.returncode}"
            return [Finding.create_tool_error("gitleaks", err_msg)]

        if not report_path.exists() or report_path.stat().st_size == 0:
            return []

        with open(report_path, encoding="utf-8") as f:
            raw_content = f.read().strip()
            if not raw_content:
                return []
            output_data: list[dict[str, Any]] = json.loads(raw_content)

        findings: list[Finding] = []
        for item in output_data:
            file_raw = item.get("File", "")
            raw_path = Path(file_raw)
            if raw_path.is_absolute():
                file_abs = raw_path.resolve()
            elif (scan_dir / raw_path).is_file():
                file_abs = (scan_dir / raw_path).resolve()
            elif raw_path.resolve().is_file():
                file_abs = raw_path.resolve()
            else:
                file_abs = (scan_dir / raw_path.name).resolve()

            try:
                rel_path = file_abs.relative_to(scan_dir.resolve()).as_posix()
            except ValueError:
                rel_path = file_abs.name

            line_num = int(item.get("StartLine", 1))
            snippet = extract_bounded_snippet(file_abs, line_num)

            # Match with rule definition
            rule_id = default_secret_rule.id if default_secret_rule else "SECRETS-001"
            title = default_secret_rule.title if default_secret_rule else "Secret leak detected"
            severity = default_secret_rule.severity.value if default_secret_rule else "critical"

            finding = Finding(
                rule_id=rule_id,
                family="SECRETS",
                severity=severity,
                title=title,
                message=item.get("Description") or f"Secret token detected ({item.get('RuleID')})",
                file_path=rel_path,
                line_number=line_num,
                snippet=snippet,
                is_tool_error=False,
                remediation_summary=default_secret_rule.remediation.summary
                if default_secret_rule
                else None,
                remediation_gcp_service=default_secret_rule.remediation.gcp_service
                if default_secret_rule
                else None,
                remediation_steps=default_secret_rule.remediation.steps
                if default_secret_rule
                else [],
            )
            findings.append(finding)

        return findings

    except subprocess.TimeoutExpired:
        return [Finding.create_tool_error("gitleaks", "Gitleaks detection timed out after 120s")]
    except json.JSONDecodeError as exc:
        return [Finding.create_tool_error("gitleaks", f"Invalid JSON report from Gitleaks: {exc}")]
    except Exception as exc:
        return [
            Finding.create_tool_error("gitleaks", f"Unexpected error executing Gitleaks: {exc}")
        ]
    finally:
        report_path.unlink(missing_ok=True)
