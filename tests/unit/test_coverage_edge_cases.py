"""Unit tests targeting edge cases and full branch coverage across vibe_guard modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder
from vibe_guard.cli import get_default_rules_dir, main
from vibe_guard.engine.models import Finding
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.engine.snippet import extract_bounded_snippet
from vibe_guard.remediation.generator import RemediationGenerator
from vibe_guard.remediation.prompts import (
    PROMPT_VERSION,
    REMEDIATION_SYSTEM_INSTRUCTION,
    REMEDIATION_USER_PROMPT_TEMPLATE,
)
from vibe_guard.report.builder import build_report, deduplicate_findings
from vibe_guard.report.masking import mask_secret_value, mask_secrets_in_text
from vibe_guard.report.renderer import render_markdown
from vibe_guard.rules.loader import RuleValidationError, load_rule_pack
from vibe_guard.rules.models import EngineDef


@pytest.fixture
def prod_pack():
    repo_root = Path(__file__).parents[2]
    return load_rule_pack(repo_root / "rules")


@pytest.mark.unit
def test_audit_record_compat_fields_and_properties() -> None:
    """ScanAuditRecord model_validator handles backward-compatible field names."""
    data = {
        "caller_id": "test-caller",
        "pack_version": "1.0.0",
        "rules_evaluated": ["AUTH-001", "SECRETS-001"],
        "duration_seconds": 1.25,
        "findings_count": 5,
        "target_source_type": "git_url",
    }
    record = ScanAuditRecord.model_validate(data)
    assert record.rules_count == 2
    assert record.total_findings == 5
    assert record.target_type == "git_url"
    assert record.findings_count == 5


@pytest.mark.unit
def test_audit_record_from_scan() -> None:
    """ScanAuditRecord.from_scan factory constructs complete record across all target types."""
    findings = [
        Finding(
            rule_id="AUTH-001",
            family="AUTH",
            severity="high",
            title="Missing Auth",
            file_path="app.py",
            line_number=10,
            message="No auth configured",
        ),
        Finding.create_tool_error("semgrep", "Semgrep timeout"),
    ]
    # Target type git_url
    rec1 = ScanAuditRecord.from_scan(
        scan_id="scan-1",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=1.5,
        caller_id="tester",
        pack_version="1.0.0",
        target="https://github.com/org/repo.git",
        findings=findings,
        rules_evaluated=["AUTH-001"],
    )
    assert rec1.target_type == "git_url"
    assert rec1.total_findings == 1
    assert rec1.tool_errors_count == 1
    assert rec1.findings_by_severity == {"high": 1}
    assert rec1.findings_by_family == {"AUTH": 1}

    # Target type archive
    rec2 = ScanAuditRecord.from_scan(
        scan_id="scan-2",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.8,
        caller_id="tester",
        pack_version="1.0.0",
        target="app.tar.gz",
        findings=[],
        rules_evaluated=[],
    )
    assert rec2.target_type == "archive"
    assert rec2.total_findings == 0


@pytest.mark.unit
def test_audit_recorder_record_scan(tmp_path: Path, prod_pack) -> None:
    """AuditRecorder.record_scan correctly summarizes rule pack, findings, and tool errors."""
    sink = tmp_path / "scans.jsonl"
    recorder = AuditRecorder(sink_file=sink)

    findings = [
        Finding(
            rule_id="AUTH-001",
            family="AUTH",
            severity="high",
            title="Missing Auth",
            file_path="app.py",
            line_number=10,
            message="No auth configured",
        ),
        Finding.create_tool_error("gitleaks", "Gitleaks crashed"),
    ]

    record = recorder.record_scan(
        caller_id="tester@domain.com",
        rule_pack=prod_pack,
        findings=findings,
        duration_seconds=0.789,
        target_type="zip",
    )

    assert record.caller_id == "tester@domain.com"
    assert record.pack_version == prod_pack.version
    assert record.rules_count == len(prod_pack.rules)
    assert record.total_findings == 1
    assert record.tool_errors_count == 1
    assert record.findings_by_severity == {"high": 1}
    assert record.findings_by_family == {"AUTH": 1}
    assert sink.is_file()


@pytest.mark.unit
def test_snippet_extraction_edge_cases(tmp_path: Path) -> None:
    """Test snippet extraction bounds, line overflow, truncation, and unreadable files."""
    test_file = tmp_path / "code.py"
    test_file.write_text("line1\nline2\nline3\n", encoding="utf-8")

    # Line beyond file length
    assert extract_bounded_snippet(test_file, line=100) is None

    # Invalid file or non-positive line
    assert extract_bounded_snippet(tmp_path / "nonexistent.py", line=1) is None
    assert extract_bounded_snippet(test_file, line=0) is None

    # Max characters truncation
    long_content = "\n".join([f"line_{i} = 'x' * 200" for i in range(20)])
    long_file = tmp_path / "long.py"
    long_file.write_text(long_content, encoding="utf-8")
    snippet = extract_bounded_snippet(long_file, line=5, context_lines=4, max_chars=100)
    assert snippet is not None
    assert "... [truncated]" in snippet.content

    # Exception during file reading returns None
    with patch("builtins.open", side_effect=OSError("Read error")):
        assert extract_bounded_snippet(test_file, line=2) is None


@pytest.mark.unit
def test_scanner_non_directory(tmp_path: Path, prod_pack) -> None:
    """ScanEngine.scan must raise FileNotFoundError if target_dir is not a directory."""
    engine = ScanEngine(prod_pack)
    with pytest.raises(FileNotFoundError):
        engine.scan(tmp_path / "missing_directory")


@pytest.mark.unit
def test_rules_models_engine_def_validation() -> None:
    """EngineDef raises ValueError when required engine definition payload is absent."""
    with pytest.raises(ValueError, match="semgrep_rule must be provided"):
        EngineDef.model_validate({"type": "semgrep", "semgrep_rule": None})

    with pytest.raises(ValueError, match="gitleaks_rule must be provided"):
        EngineDef.model_validate({"type": "gitleaks", "gitleaks_rule": None})


@pytest.mark.unit
def test_rule_pack_get_gitleaks_rules_and_loader_errors(tmp_path: Path, prod_pack) -> None:
    """RulePack.get_gitleaks_rules and load_rule_pack edge cases."""
    git_rules = prod_pack.get_gitleaks_rules()
    assert len(git_rules) >= 1
    for r in git_rules:
        assert "vibe_guard_rule_id" in r

    # load_rule_pack on non-existent directory
    with pytest.raises(FileNotFoundError):
        load_rule_pack(tmp_path / "no_such_dir")

    # load_rule_pack with empty yaml file (skipped)
    pack_dir = tmp_path / "custom_pack"
    pack_dir.mkdir()
    manifest_yaml = (
        "name: custom\n"
        "version: '1.0.0'\n"
        "description: 'Custom pack'\n"
        "families:\n"
        "  - id: AUTH\n"
        "    name: Auth\n"
        "    description: Authentication\n"
    )
    (pack_dir / "pack.yaml").write_text(manifest_yaml)
    (pack_dir / "empty.yaml").write_text("")
    loaded = load_rule_pack(pack_dir)
    assert len(loaded.rules) == 0

    # load_rule_pack with malformed yaml file raises RuleValidationError
    (pack_dir / "broken.yaml").write_text("id: 123\nfamily: [invalid\n")
    with pytest.raises(RuleValidationError):
        load_rule_pack(pack_dir)


@pytest.mark.unit
def test_masking_short_values_and_empty_text() -> None:
    """mask_secret_value masks values <= 6 chars; mask_secrets_in_text returns empty string."""
    assert mask_secret_value("short") == "***[MASQUÉ]***"
    assert mask_secret_value("123456") == "***[MASQUÉ]***"
    assert mask_secret_value("1234567") == "1234...[MASQUÉ]"
    assert mask_secrets_in_text("") == ""


@pytest.mark.unit
def test_build_report_with_semgrep_tool_error() -> None:
    """build_report correctly marks semgrep status as error when semgrep fails."""
    findings = [
        Finding.create_tool_error("semgrep", "Semgrep binary crashed with signal 9"),
    ]
    report = build_report(
        findings=findings,
        scan_id="scan-err-test",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.5,
        caller_id="tester",
        pack_version="1.0.0",
        target="some_target",
    )
    assert report.engine_status.semgrep.status == "error"
    assert "crashed" in report.engine_status.semgrep.error_message
    assert "AUTH" in report.engine_status.semgrep.degraded_families
    assert "AUTH" in report.engine_status.coverage_degraded


@pytest.mark.unit
def test_render_markdown_prompt_version_and_contextual_advice() -> None:
    """render_markdown displays prompt_version, reference URLs, and Gemini contextual advice."""
    finding = Finding(
        rule_id="AUTH-001",
        family="AUTH",
        severity="high",
        title="No Auth",
        file_path="main.py",
        line_number=15,
        message="Endpoint unprotected",
    )
    report = build_report(
        findings=[finding],
        scan_id="scan-md-test",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=1.2,
        caller_id="architect@corp.com",
        pack_version="1.0.0",
        target="app.zip",
        llm_remediation_enabled=True,
        prompt_version="1.0.0",
        contextual_advices={
            "AUTH-001": "Activer Google Cloud Identity-Aware Proxy (IAP) devant le service."
        },
    )
    md = render_markdown(report)
    assert "Version du prompt" in md
    assert "1.0.0" in md
    assert "Conseil d'architecture IA (Gemini)" in md
    assert "Activer Google Cloud Identity-Aware Proxy" in md


@pytest.mark.unit
def test_prompts_constants_defined() -> None:
    """Verify remediation prompt constants are populated."""
    assert PROMPT_VERSION == "1.0.0"
    assert "Vibe Guard" in REMEDIATION_SYSTEM_INSTRUCTION
    assert len(REMEDIATION_USER_PROMPT_TEMPLATE) > 10


@pytest.mark.unit
def test_cli_get_default_rules_dir_env(tmp_path: Path, monkeypatch) -> None:
    """get_default_rules_dir honors VIBE_GUARD_RULES_DIR when set and valid."""
    fake_rules = tmp_path / "env_rules"
    fake_rules.mkdir()
    monkeypatch.setenv("VIBE_GUARD_RULES_DIR", str(fake_rules))
    resolved = get_default_rules_dir()
    assert resolved == fake_rules


@pytest.mark.unit
def test_cli_rules_list_invalid_family() -> None:
    """rules list --family INVALID exits with code 2."""
    with pytest.raises(SystemExit) as exc:
        main(["rules", "list", "--family", "DOES_NOT_EXIST"])
    assert exc.value.code == 2


@pytest.mark.unit
def test_remediation_generator_disabled_and_error_handling() -> None:
    """RemediationGenerator returns empty dict when disabled or on API exception."""
    gen = RemediationGenerator(enabled=False)
    assert gen.enrich_findings([]) == {}

    mock_client = patch("vibe_guard.remediation.generator.RemediationGenerator._get_client")
    gen_enabled = RemediationGenerator(enabled=True)

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = RuntimeError("Vertex timeout")

    with mock_client as mock_c:
        mock_c.return_value = fake_client
        finding = Finding(
            rule_id="AUTH-001",
            family="AUTH",
            severity="high",
            title="No Auth",
            file_path="src/main.py",
            line_number=10,
            message="No auth",
        )
        advices = gen_enabled.enrich_findings([finding])
        assert advices == {}

        # When Gemini succeeds
        fake_client.models.generate_content.side_effect = None
        fake_client.models.generate_content.return_value = MagicMock(text="Activer Cloud IAP")
        success_advices = gen_enabled.enrich_findings([finding])
        assert "AUTH-001:src/main.py:10" in success_advices
        assert success_advices["AUTH-001:src/main.py:10"] == "Activer Cloud IAP"


@pytest.mark.unit
def test_deduplicate_findings_empty_and_contiguous() -> None:
    """deduplicate_findings returns empty list on empty inputs and merges contiguous lines."""
    assert deduplicate_findings([]) == []
    tool_err = Finding.create_tool_error("engine", "error")
    assert deduplicate_findings([tool_err]) == []

    f1 = Finding(
        rule_id="SECRETS-001",
        family="SECRETS",
        severity="critical",
        title="Leaked Secret",
        file_path="cfg.py",
        line_number=10,
        message="Leak line 10",
    )
    f2 = Finding(
        rule_id="SECRETS-001",
        family="SECRETS",
        severity="critical",
        title="Leaked Secret",
        file_path="cfg.py",
        line_number=11,
        message="Leak line 11",
    )
    f3 = Finding(
        rule_id="SECRETS-001",
        family="SECRETS",
        severity="critical",
        title="Leaked Secret",
        file_path="cfg.py",
        line_number=25,
        message="Leak line 25",
    )
    deduped = deduplicate_findings([f1, f2, f3])
    assert len(deduped) == 2
    assert deduped[0].line_number == 10
    assert deduped[1].line_number == 25
