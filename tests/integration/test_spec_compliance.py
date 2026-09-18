"""Integration tests verifying normative specification compliance (SPEC-*)."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe_guard.engine.gitleaks import _find_gitleaks_binary
from vibe_guard.engine.models import Finding
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.engine.semgrep import _find_semgrep_binary
from vibe_guard.report.builder import build_report
from vibe_guard.report.renderer import render_markdown
from vibe_guard.rules.loader import load_rule_pack


@pytest.fixture(scope="module")
def rule_pack():
    repo_root = Path(__file__).parents[2]
    return load_rule_pack(repo_root / "rules")


@pytest.fixture(scope="module")
def scan_engine(rule_pack):
    return ScanEngine(rule_pack)


@pytest.mark.integration
def test_spec_rep_5_secrets_redacted_in_json_and_markdown(
    scan_engine: ScanEngine, rule_pack
) -> None:
    """SPEC-REP-5: Scanned secrets must NEVER appear in cleartext in JSON or Markdown reports.

    Tested on the fixture app_secrets_leak.
    """
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"

    findings = scan_engine.scan(fixture_dir)
    assert len(findings) > 0, "Scan must produce findings on app_secrets_leak"

    report = build_report(
        findings=findings,
        scan_id="spec-rep-5-scan",
        timestamp="2026-09-18T12:00:00Z",
        duration_seconds=1.2,
        caller_id="tester",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
    )

    json_str = report.to_json()
    md_str = render_markdown(report)

    # Specific secret tokens from main.py and Dockerfile in app_secrets_leak
    leaked_openai_key = "sk-proj-abc1234567890abcdef1234567890abcdef"
    leaked_token = "super-secret-token-12345"

    assert leaked_openai_key not in json_str, "Cleartext OpenAI key leaked in JSON report!"
    assert leaked_openai_key not in md_str, "Cleartext OpenAI key leaked in Markdown report!"
    assert leaked_token not in json_str, "Cleartext env secret token leaked in JSON report!"
    assert leaked_token not in md_str, "Cleartext env secret token leaked in Markdown report!"

    # Verify masked fingerprints are present instead
    assert "[MASQUÉ]" in json_str
    assert "[MASQUÉ]" in md_str


@pytest.mark.integration
def test_spec_eng_4_and_rep_6_tool_error_engine_status(rule_pack) -> None:
    """SPEC-ENG-4 & SPEC-REP-6: Scanner tool errors must be reported in engine_status

    with degraded families and cannot be interpreted as conforming.
    """
    tool_error_finding = Finding.create_tool_error(
        tool_name="gitleaks",
        error_message="Gitleaks executable not found in PATH",
    )

    report = build_report(
        findings=[tool_error_finding],
        scan_id="spec-eng-4-scan",
        timestamp="2026-09-18T12:00:00Z",
        duration_seconds=0.5,
        caller_id="tester",
        pack_version=rule_pack.version,
        target="/tmp/test",
    )

    # 1. Total findings must NOT treat tool errors as application vulnerabilities
    assert report.summary.total_findings == 0
    assert len(report.findings) == 0

    # 2. engine_status must accurately capture gitleaks failure and degraded family
    assert report.engine_status.gitleaks.status == "error"
    assert "not found" in (report.engine_status.gitleaks.error_message or "")
    assert report.engine_status.gitleaks.degraded_families == ["SECRETS"]
    assert report.engine_status.semgrep.status == "ok"
    assert report.engine_status.coverage_degraded == ["SECRETS"]

    # 3. Markdown rendering must explicitly state that coverage is degraded and NOT conforming
    md = render_markdown(report)
    assert "ATTENTION : Couverture de détection dégradée" in md
    assert "ne peut pas être interprété comme conforme" in md
    assert "SECRETS" in md
    assert "L'application respecte les règles Vibe Guard" not in md


@pytest.mark.integration
def test_spec_eng_7_binary_env_override(tmp_path: Path) -> None:
    """SPEC-ENG-7: Tool subprocess paths must come from VIBE_GUARD_<TOOL>_BIN or PATH."""
    fake_gitleaks = tmp_path / "custom_gitleaks"
    fake_gitleaks.write_text("#!/bin/sh\necho 8.18.0\n")
    fake_gitleaks.chmod(0o755)

    with patch.dict(os.environ, {"VIBE_GUARD_GITLEAKS_BIN": str(fake_gitleaks)}):
        resolved = _find_gitleaks_binary()
        assert resolved == str(fake_gitleaks)

    fake_semgrep = tmp_path / "custom_semgrep"
    fake_semgrep.write_text("#!/bin/sh\necho 1.70.0\n")
    fake_semgrep.chmod(0o755)

    with patch.dict(os.environ, {"VIBE_GUARD_SEMGREP_BIN": str(fake_semgrep)}):
        resolved_semgrep = _find_semgrep_binary()
        assert resolved_semgrep == str(fake_semgrep)


@pytest.mark.integration
def test_spec_ops_4_self_scan_zero_net_iso_and_secrets(scan_engine: ScanEngine) -> None:
    """SPEC-OPS-4: Vibe Guard scanned by itself must produce 0 NET-ISO and 0 SECRETS findings."""
    repo_root = Path(__file__).parents[2]
    target_dirs = [repo_root / "src", repo_root / "deploy", repo_root / "vibe_guard_a2ui"]

    all_findings = []
    for d in target_dirs:
        if d.is_dir():
            findings = scan_engine.scan(d)
            all_findings.extend(findings)

    bad_findings = [
        f for f in all_findings if f.family in ("NET-ISO", "SECRETS") and f.rule_id != "TOOL-ERROR"
    ]
    assert len(bad_findings) == 0, f"SPEC-OPS-4 failed: unexpected findings: {bad_findings}"
