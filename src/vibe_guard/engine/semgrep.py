"""Semgrep OSS executor and result normalizer for Vibe Guard."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from vibe_guard.engine.models import Finding
from vibe_guard.engine.snippet import extract_bounded_snippet
from vibe_guard.rules.loader import RulePack


def _find_semgrep_binary() -> str:
    """Find the semgrep executable in virtualenv or PATH."""
    venv_semgrep = Path(".venv/bin/semgrep").resolve()
    if venv_semgrep.is_file() and os_is_executable(venv_semgrep):
        return str(venv_semgrep)
    which_bin = shutil.which("semgrep")
    if which_bin:
        return which_bin
    return "semgrep"


def os_is_executable(path: Path) -> bool:
    import os

    return os.access(path, os.X_OK)


def run_semgrep(scan_dir: Path, rule_pack: RulePack) -> list[Finding]:
    """Execute Semgrep with compiled rule definitions and return normalized findings."""
    semgrep_rules = rule_pack.get_semgrep_rules()
    if not semgrep_rules:
        return []

    semgrep_bin = _find_semgrep_binary()

    # Create temporary semgrep rules configuration
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="semgrep_rules_",
        delete=False,
    ) as tmp_config:
        yaml.dump({"rules": semgrep_rules}, tmp_config)
        config_path = Path(tmp_config.name)

    try:
        cmd = [
            semgrep_bin,
            "scan",
            "--config",
            str(config_path),
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            str(scan_dir),
        ]

        env = dict(os.environ)
        env["HOME"] = str(config_path.parent)
        env["SEMGREP_SETTINGS_FILE"] = str(config_path.parent / ".semgrep_settings.yml")

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        # Semgrep returns 0 on clean, 1 on findings detected
        if result.returncode not in (0, 1):
            err_msg = result.stderr.strip() or f"Semgrep exited with code {result.returncode}"
            return [Finding.create_tool_error("semgrep", err_msg)]

        output_data: dict[str, Any] = json.loads(result.stdout)
        findings: list[Finding] = []

        for item in output_data.get("results", []):
            extra = item.get("extra", {})
            metadata = extra.get("metadata", {})
            rule_id = metadata.get("vibe_guard_rule_id") or item.get("check_id")

            rule_def = rule_pack.get_rule(rule_id)
            file_abs_path = Path(item.get("path", "")).resolve()

            try:
                rel_path = file_abs_path.relative_to(scan_dir.resolve()).as_posix()
            except ValueError:
                rel_path = file_abs_path.name

            line_num = item.get("start", {}).get("line", 1)
            snippet = extract_bounded_snippet(file_abs_path, line_num)

            finding = Finding(
                rule_id=rule_id,
                family=rule_def.family.value if rule_def else "CODE",
                severity=rule_def.severity.value if rule_def else "medium",
                title=rule_def.title if rule_def else rule_id,
                message=extra.get("message", ""),
                file_path=rel_path,
                line_number=line_num,
                snippet=snippet,
                is_tool_error=False,
                remediation_summary=rule_def.remediation.summary if rule_def else None,
                remediation_gcp_service=rule_def.remediation.gcp_service if rule_def else None,
                remediation_steps=rule_def.remediation.steps if rule_def else [],
            )
            findings.append(finding)

        return findings

    except subprocess.TimeoutExpired:
        return [Finding.create_tool_error("semgrep", "Semgrep scan timed out after 180 seconds")]
    except json.JSONDecodeError as exc:
        return [Finding.create_tool_error("semgrep", f"Failed to parse Semgrep JSON output: {exc}")]
    except Exception as exc:
        return [Finding.create_tool_error("semgrep", f"Unexpected error executing Semgrep: {exc}")]
    finally:
        config_path.unlink(missing_ok=True)
