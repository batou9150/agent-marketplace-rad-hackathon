import json
import os
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder
from vibe_guard.engine.gitleaks import _find_gitleaks_binary, run_gitleaks
from vibe_guard.engine.models import Finding
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.engine.semgrep import _find_semgrep_binary, run_semgrep
from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError
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


@pytest.mark.integration
def test_spec_ing_1_accepts_all_three_source_types(scan_engine: ScanEngine, tmp_path: Path) -> None:
    """SPEC-ING-1: The scanner must accept Git repository, archive, and local directory."""
    # 1. Local directory source
    local_dir = tmp_path / "local_app"
    local_dir.mkdir()
    (local_dir / "app.py").write_text("print('hello')\n")
    with EphemeralWorkspace() as ws:
        extracted = ws.copy_directory(local_dir)
        findings = scan_engine.scan(extracted)
        assert isinstance(findings, list)

    # 2. Archive source (.zip)
    zip_path = tmp_path / "app.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("main.py", "x = 1\n")
    with EphemeralWorkspace() as ws:
        extracted = ws.extract_archive(zip_path)
        findings = scan_engine.scan(extracted)
        assert isinstance(findings, list)

    # 3. Git repo source
    with EphemeralWorkspace() as ws, patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        repo_dest = ws.path / "repo"
        repo_dest.mkdir()
        (repo_dest / "index.py").write_text("pass\n")
        cloned = ws.clone_git("https://github.com/example/repo.git")
        findings = scan_engine.scan(cloned)
        assert isinstance(findings, list)


@pytest.mark.integration
def test_spec_ing_8_semgrep_excludes_git_directory(rule_pack, tmp_path: Path) -> None:
    """SPEC-ING-8: .git directory must be excluded from semgrep analysis and findings."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    # Write a file with an insecure pattern inside .git/
    (git_dir / "insecure.py").write_text(
        "import openai\nopenai.api_key = 'sk-proj-abc1234567890abcdef1234567890abcdef'\n"
    )
    # Write a clean file outside .git/
    (tmp_path / "main.py").write_text("x = 42\n")

    findings = run_semgrep(tmp_path, rule_pack)
    git_findings = [f for f in findings if f.file_path.startswith(".git")]
    assert len(git_findings) == 0, f"Findings reported inside .git: {git_findings}"


@pytest.mark.integration
def test_spec_eng_8_configurable_timeouts(rule_pack, tmp_path: Path) -> None:
    """SPEC-ENG-8: Explicit configurable timeouts for Semgrep, Gitleaks, and Git clone."""
    # Test Semgrep timeout handling
    with (
        patch("vibe_guard.engine.semgrep._find_semgrep_binary", return_value="/bin/semgrep"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["semgrep"], timeout=180),
        ),
    ):
        findings = run_semgrep(tmp_path, rule_pack)
        assert len(findings) == 1
        assert findings[0].is_tool_error
        assert "timed out" in findings[0].message

    # Test Gitleaks timeout handling
    with (
        patch("vibe_guard.engine.gitleaks._find_gitleaks_binary", return_value="/bin/gitleaks"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["gitleaks"], timeout=120),
        ),
    ):
        findings = run_gitleaks(tmp_path, rule_pack)
        assert len(findings) == 1
        assert findings[0].is_tool_error
        assert "timed out" in findings[0].message

    # Test Git clone timeout handling
    with (
        EphemeralWorkspace() as ws,
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=120),
        ),
        pytest.raises(IngestionError, match="timed out"),
    ):
        ws.clone_git("https://github.com/example/repo.git")


@pytest.mark.integration
def test_spec_rem_5_prompt_version_exposed_in_report(rule_pack) -> None:
    """SPEC-REM-5: Report metadata includes prompt_version when llm_remediation_enabled is True."""
    report_with_llm = build_report(
        findings=[],
        scan_id="rem-5-scan-1",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.1,
        caller_id="test",
        pack_version=rule_pack.version,
        target="target",
        llm_remediation_enabled=True,
    )
    assert report_with_llm.metadata.llm_remediation_enabled is True
    assert report_with_llm.metadata.prompt_version == "v1"

    report_without_llm = build_report(
        findings=[],
        scan_id="rem-5-scan-2",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.1,
        caller_id="test",
        pack_version=rule_pack.version,
        target="target",
        llm_remediation_enabled=False,
    )
    assert report_without_llm.metadata.llm_remediation_enabled is False
    assert report_without_llm.metadata.prompt_version is None


@pytest.mark.integration
def test_spec_rul_4_dynamic_yaml_rule_evaluation(tmp_path: Path) -> None:
    """SPEC-RUL-4: Adding a rule via YAML file requires zero Python code changes."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    pack_manifest = """version: "1.0.0"
name: "custom-test-pack"
description: "Test pack for dynamic evaluation"
families:
  - id: AUTH
    name: "Authentication"
    description: "Auth checks"
"""
    (rules_dir / "pack.yaml").write_text(pack_manifest)
    custom_rule = """id: AUTH-099
family: AUTH
severity: high
title: "Disallowed eval usage"
rationale: "Eval allows arbitrary code execution"
example: |
  eval("malicious")
remediation:
  summary: "Do not use eval"
  gcp_service: "Cloud Run"
  steps:
    - "Replace eval with safe parsing"
engine:
  type: semgrep
  semgrep_rule:
    id: dynamic-eval-check
    languages: [python]
    severity: ERROR
    message: "Avoid eval"
    pattern: eval(...)
"""
    (rules_dir / "custom-rule.yaml").write_text(custom_rule)

    target_dir = tmp_path / "app"
    target_dir.mkdir()
    (target_dir / "vuln.py").write_text("eval('print(1)')\n")

    custom_pack = load_rule_pack(rules_dir)
    engine = ScanEngine(custom_pack)
    findings = engine.scan(target_dir)

    assert any(f.rule_id == "AUTH-099" for f in findings)


@pytest.mark.integration
def test_spec_rep_3_and_rep_7_report_summary_and_relative_paths(
    scan_engine: ScanEngine, rule_pack
) -> None:
    """SPEC-REP-3 & SPEC-REP-7: Report summary invariants and relative file paths only."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"

    findings = scan_engine.scan(fixture_dir)
    report = build_report(
        findings=findings,
        scan_id="rep-invariants-scan",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.5,
        caller_id="tester",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
    )

    # SPEC-REP-3: Summary consistency
    assert report.summary.total_findings == len(report.findings)
    assert sum(report.summary.by_severity.values()) == report.summary.total_findings

    # SPEC-REP-7: No absolute paths, relative only
    for finding in report.findings:
        assert not finding.file_path.startswith("/"), f"Absolute path found: {finding.file_path}"
        assert ".." not in finding.file_path, f"Path traversal found: {finding.file_path}"


@pytest.mark.integration
def test_spec_aud_2_and_3_audit_record_no_code_and_cloud_logging_format(tmp_path: Path) -> None:
    """SPEC-AUD-2 & SPEC-AUD-3: Audit record has no code/secrets, in JSONL format."""
    log_file = tmp_path / "audit.jsonl"
    recorder = AuditRecorder(sink_file=log_file)

    record = ScanAuditRecord.create(
        caller_id="user@example.com",
        pack_version="0.1.0",
        rules_evaluated=["AUTH-001", "SECRETS-001"],
        duration_seconds=1.23,
        findings_count=2,
        findings_by_severity={"critical": 1, "high": 1},
        target_source_type="https://github.com/example/repo.git",
    )
    recorder.record(record)

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    raw_json = lines[0]

    # SPEC-AUD-3: Valid single-line JSON format for Cloud Logging
    parsed = json.loads(raw_json)
    assert parsed["caller_id"] == "user@example.com"
    assert parsed["pack_version"] == "0.1.0"

    # SPEC-AUD-2: No snippet, code, or secret content
    assert "snippet" not in parsed
    assert "content" not in parsed
    assert "code" not in parsed
    assert "secret" not in parsed


@pytest.mark.integration
def test_spec_ing_3_limits_enforced_before_scanners_start(tmp_path: Path) -> None:
    """SPEC-ING-3: Limits §3.2 enforced during extraction, failing before any scanner starts."""
    zip_path = tmp_path / "oversized_files.zip"
    # Create an archive with 6,000 files (exceeding default IngestLimits.max_files = 5,000)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(5005):
            zf.writestr(f"file_{i}.txt", "x")

    with (
        EphemeralWorkspace(base_dir=tmp_path) as ws,
        pytest.raises(IngestionError, match="maximum file count exceeded"),
    ):
        ws.extract_archive(zip_path)


@pytest.mark.integration
def test_spec_rep_1_and_rep_4_schema_documentation_and_markdown_parity(
    scan_engine: ScanEngine, rule_pack
) -> None:
    """SPEC-REP-1 & SPEC-REP-4: Report schema doc coherence and parity with Markdown."""
    repo_root = Path(__file__).parents[2]
    schema_doc = (repo_root / "docs" / "report-schema.md").read_text(encoding="utf-8")

    # SPEC-REP-1: Verify that every field of Report models is documented in docs/report-schema.md
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

    models_to_check = [
        Report,
        ReportMetadata,
        ReportSummary,
        ReportFinding,
        ReportSnippet,
        ReportRemediation,
        ScannerStatus,
        EngineStatus,
    ]
    for model in models_to_check:
        for field_name in model.model_fields:
            if field_name == "schema_uri":
                field_name = "$schema"
            assert f"`{field_name}`" in schema_doc, (
                f"Field {field_name} from {model.__name__} not documented in docs/report-schema.md"
            )

    # SPEC-REP-4: Parity between Report and Markdown rendering
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"
    findings = scan_engine.scan(fixture_dir)
    report = build_report(
        findings=findings,
        scan_id="parity-scan-12345",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.75,
        caller_id="tester@example.com",
        pack_version=rule_pack.version,
        target="fixtures/nonconform/app_secrets_leak",
        llm_remediation_enabled=False,
    )

    md_str = report.to_markdown()

    # Every key metadata field present in Markdown
    assert report.metadata.scan_id in md_str
    assert report.metadata.caller_id in md_str
    assert report.metadata.pack_version in md_str
    assert str(report.summary.total_findings) in md_str

    # Every finding data present in Markdown
    for finding in report.findings:
        assert finding.rule_id in md_str
        assert finding.finding_id in md_str
        assert finding.file_path in md_str
        assert str(finding.line_number) in md_str
        assert finding.remediation.gcp_service in md_str
        assert finding.remediation.summary in md_str
        for step in finding.remediation.steps:
            assert step in md_str


def test_spec_aud_4_caller_id_resolution_deployed_and_local(monkeypatch, tmp_path):
    """SPEC-AUD-4: caller_id must originate from IAM/IAP identity in deployment,
    and anonymous in local.
    """
    from vibe_guard.cli import main
    from vibe_guard_a2ui.agent import _retrieve_report, scan_repository

    repo_root = Path(__file__).parents[2]
    clean_target = repo_root / "fixtures" / "conform" / "clean_python_app"

    # 1. Local execution without explicit caller_id -> "anonymous"
    monkeypatch.delenv("VIBE_GUARD_ENV", raising=False)
    local_res = scan_repository(source=str(clean_target), no_llm=True)
    assert "Vibe Guard Security Audit Completed" in local_res
    local_report = _retrieve_report(None)
    assert local_report is not None
    assert local_report.metadata.caller_id == "anonymous"

    # 2. Local CLI scan without --caller-id -> "anonymous"
    out_json = tmp_path / "cli_report.json"
    cli_code = main(
        [
            "scan",
            str(clean_target),
            "--rules",
            str(repo_root / "rules"),
            "--no-llm",
            "--format",
            "json",
            "--out",
            str(out_json),
        ]
    )
    assert cli_code == 0
    saved_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved_data["metadata"]["caller_id"] == "anonymous"

    # 3. Deployed mode (production) without authenticated caller -> rejected
    monkeypatch.setenv("VIBE_GUARD_ENV", "production")
    monkeypatch.delenv("IAP_CALLER_IDENTITY", raising=False)
    monkeypatch.delenv("AUTHENTICATED_USER_EMAIL", raising=False)
    monkeypatch.delenv("CALLER_ID", raising=False)
    unauth_res = scan_repository(source=f"file://{clean_target}.tar.gz", no_llm=True)
    assert "Error 401/403: Unauthenticated caller" in unauth_res

    # 4. Deployed mode with authenticated IAP/IAM identity
    monkeypatch.setenv("IAP_CALLER_IDENTITY", "alice@enterprise.example.com")
    sample_zip = tmp_path / "app.zip"
    with zipfile.ZipFile(sample_zip, "w") as zf:
        zf.writestr("app.py", "print('hello')\n")

    auth_res = scan_repository(source=str(sample_zip), no_llm=True)
    assert "Vibe Guard Security Audit Completed" in auth_res
    deployed_report = _retrieve_report(None)
    assert deployed_report is not None
    assert deployed_report.metadata.caller_id == "alice@enterprise.example.com"


def test_spec_ops_6_no_fabricated_metrics():
    """SPEC-OPS-6 & C7: No unmeasured benchmark claims or fabricated metrics in repo."""
    repo_root = Path(__file__).parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    agent_card = (repo_root / "vibe_guard_a2ui" / ".well-known" / "agent.json").read_text(
        encoding="utf-8"
    )

    forbidden_patterns = [
        "99.",
        "98.",
        "100x",
        "10x",
        "5x faster",
        "state of the art",
        "benchmark score",
        "surpasses human",
        "hallucination free",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in readme.lower(), (
            f"Unmeasured marketing claim '{pattern}' found in README.md"
        )
        assert pattern not in agent_card.lower(), (
            f"Unmeasured marketing claim '{pattern}' found in agent.json"
        )
