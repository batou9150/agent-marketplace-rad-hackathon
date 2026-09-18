"""Semgrep OSS executor and result normalizer for Vibe Guard."""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from vibe_guard.engine.models import Finding
from vibe_guard.engine.snippet import extract_bounded_snippet
from vibe_guard.rules.loader import RulePack

logger = logging.getLogger(__name__)


def _find_semgrep_binary() -> str:
    """Find the semgrep executable in env, virtualenv or PATH (SPEC-ENG-7)."""
    env_bin = os.environ.get("VIBE_GUARD_SEMGREP_BIN")
    if env_bin and Path(env_bin).is_file():
        return env_bin
    # Beside the running interpreter: the pip-installed entry point lives next to
    # `python` in any virtualenv. Unlike the `.venv/bin/semgrep` probe below, this
    # holds wherever the process was started from, which is what a deployed
    # container needs: there the venv is not under the working directory.
    interpreter_bin = Path(sys.executable).parent / "semgrep"
    if interpreter_bin.is_file() and os_is_executable(interpreter_bin):
        return str(interpreter_bin)
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


def _tool_error(message: str, cmd: list[str] | None = None) -> list[Finding]:
    """Record a Semgrep failure as a finding and make it visible in the logs.

    A tool error is excluded from the finding counts, so without this the scan
    reports success while half the rule pack never ran. The command and working
    directory travel with it: Semgrep resolves paths against both, and its path
    errors name neither.
    """
    logger.error(
        "Semgrep execution failed (cwd=%s, cmd=%s): %s",
        os.getcwd(),
        cmd if cmd is None else " ".join(repr(arg) for arg in cmd),
        message,
    )
    return [Finding.create_tool_error("semgrep", message)]


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

    cmd: list[str] = []

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
            "--exclude",
            ".git",
            str(scan_dir),
        ]

        env = dict(os.environ)

        # semgrep-core reads several variables as filesystem paths and aborts the
        # whole scan with Invalid_argument("": invalid path) when one is present
        # but empty, which is how a managed runtime can hand them over. Which
        # variables it consults is not documented, and an empty value carries no
        # meaning for a subprocess, so every empty entry is dropped: unset is safe
        # where empty is fatal.
        dropped = sorted(var for var, value in env.items() if not value)
        for var in dropped:
            del env[var]
        if dropped:
            logger.info("Dropped empty environment variables for Semgrep: %s", ", ".join(dropped))

        env["HOME"] = str(config_path.parent)
        env["SEMGREP_SETTINGS_FILE"] = str(config_path.parent / ".semgrep_settings.yml")
        env["SEMGREP_VERSION_CACHE_PATH"] = str(config_path.parent / ".semgrep_version_cache")

        timeout = int(os.environ.get("VIBE_GUARD_SEMGREP_TIMEOUT", "180"))
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        # Semgrep returns 0 on clean, 1 on findings detected
        if result.returncode not in (0, 1):
            err_msg = result.stderr.strip() or f"Semgrep exited with code {result.returncode}"
            return _tool_error(err_msg, cmd)

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

            # SPEC-ING-8: Exclude findings from .git
            if rel_path.startswith(".git/") or rel_path == ".git":
                continue

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
        msg = f"Semgrep scan timed out after {timeout} seconds"
        return _tool_error(msg, cmd)
    except json.JSONDecodeError as exc:
        return _tool_error(f"Failed to parse Semgrep JSON output: {exc}", cmd)
    except Exception as exc:
        return _tool_error(f"Unexpected error executing Semgrep: {exc}", cmd)
    finally:
        config_path.unlink(missing_ok=True)
