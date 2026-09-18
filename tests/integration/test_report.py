"""Integration tests for Report generation, schemas, LLM remediation, and determinism (Gate 3)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe_guard.engine.models import Finding, Snippet
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.remediation.generator import RemediationGenerator
from vibe_guard.report.builder import build_report, deduplicate_findings
from vibe_guard.report.models import Report
from vibe_guard.report.renderer import render_json, render_markdown
from vibe_guard.rules.loader import load_rule_pack


@pytest.fixture(scope="module")
def rule_pack():
    repo_root = Path(__file__).parents[2]
    return load_rule_pack(repo_root / "rules")


@pytest.fixture(scope="module")
def scan_engine(rule_pack):
    return ScanEngine(rule_pack)


@pytest.mark.integration
def test_report_schema_valid_for_all_fixtures(scan_engine: ScanEngine, rule_pack) -> None:
    """Every fixture must produce a report strictly validating against the schema."""
    repo_root = Path(__file__).parents[2]
    all_fixtures = list((repo_root / "fixtures" / "nonconform").iterdir()) + list(
        (repo_root / "fixtures" / "conform").iterdir()
    )

    for fixture_dir in all_fixtures:
        if not fixture_dir.is_dir():
            continue

        findings = scan_engine.scan(fixture_dir)
        report = build_report(
            findings=findings,
            scan_id="test-scan-uuid",
            timestamp="2026-09-18T10:00:00Z",
            duration_seconds=1.23,
            caller_id="test-suite",
            pack_version=rule_pack.version,
            target=str(fixture_dir.name),
            llm_remediation_enabled=False,
        )

        # Ensure JSON rendering is valid and conforms to Report schema
        json_output = render_json(report)
        assert json_output is not None
        re_parsed = Report.model_validate_json(json_output)
        assert re_parsed.version == "1.0.0"
        assert re_parsed.metadata.target == str(fixture_dir.name)

        # Ensure Markdown rendering succeeds
        md_output = render_markdown(report)
        assert "# 🛡️ Rapport de non-conformité — Vibe Guard" in md_output
        assert "Synthèse globale" in md_output


@pytest.mark.integration
def test_no_llm_mode_produces_complete_and_useful_report(
    scan_engine: ScanEngine, rule_pack
) -> None:
    """In --no-llm mode, static GCP remediation steps must be fully populated."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_auth_fail"

    findings = scan_engine.scan(fixture_dir)
    report = build_report(
        findings=findings,
        scan_id="no-llm-scan",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.5,
        caller_id="cli_user",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
        llm_remediation_enabled=False,
    )

    assert report.metadata.llm_remediation_enabled is False
    assert len(report.findings) >= 2
    for finding in report.findings:
        assert finding.remediation.contextual_advice is None
        assert len(finding.remediation.summary) >= 5
        assert len(finding.remediation.gcp_service) >= 2
        assert len(finding.remediation.steps) >= 1


@pytest.mark.integration
def test_gate3_remediation_generator_bounded_context_constraint_c2(rule_pack) -> None:
    """Remediation generator must never send unbounded file contents to Gemini (Constraint C2)."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Remédiation contextuelle générée par mock Gemini."
    mock_client.models.generate_content.return_value = mock_response

    generator = RemediationGenerator(
        client=mock_client,
        model="gemini-3.8-flash",
        max_snippet_chars=200,
        enabled=True,
    )

    oversized_content = "X" * 1000
    finding = Finding(
        rule_id="AUTH-001",
        family="AUTH",
        severity="high",
        title="Test rule",
        message="Test message",
        file_path="app.py",
        line_number=10,
        snippet=Snippet(start_line=1, end_line=50, highlight_line=10, content=oversized_content),
        remediation_summary="Fix route",
        remediation_gcp_service="IAP",
        remediation_steps=["Enable IAP"],
    )

    advice = generator.generate_advice(finding, rule_pack=rule_pack)
    assert advice == "Remédiation contextuelle générée par mock Gemini."

    # Check the prompt sent to mock_client
    call_args = mock_client.models.generate_content.call_args
    sent_prompt = call_args.kwargs["contents"]

    # Verify that the full oversized content was NOT sent verbatim and was strictly truncated
    assert oversized_content not in sent_prompt
    assert "... [tronqué C2]" in sent_prompt


@pytest.mark.integration
def test_gate3_scan_and_report_determinism(scan_engine: ScanEngine, rule_pack) -> None:
    """Scanning a fixture twice yields identical findings and deterministic report outputs."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_llm_injection"

    # Run 1
    findings_1 = scan_engine.scan(fixture_dir)
    report_1 = build_report(
        findings=findings_1,
        scan_id="fixed-scan-id",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=1.0,
        caller_id="user1",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
    )

    # Run 2
    findings_2 = scan_engine.scan(fixture_dir)
    report_2 = build_report(
        findings=findings_2,
        scan_id="fixed-scan-id",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=1.0,
        caller_id="user1",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
    )

    # Findings must match completely
    assert [f.rule_id for f in findings_1] == [f.rule_id for f in findings_2]
    assert [f.line_number for f in findings_1] == [f.line_number for f in findings_2]

    # Rendered JSON reports must be byte-for-byte identical (ignoring generated finding_id)
    r1_dict = report_1.model_dump()
    r2_dict = report_2.model_dump()
    for f in r1_dict["findings"]:
        f["finding_id"] = "fixed"
    for f in r2_dict["findings"]:
        f["finding_id"] = "fixed"

    assert r1_dict == r2_dict


@pytest.mark.integration
def test_contiguous_deduplication() -> None:
    """Contiguous findings on same rule and same file must be merged (ADR-005b)."""
    findings = [
        Finding(
            rule_id="NET-ISO-003",
            family="NET-ISO",
            severity="high",
            title="Root user",
            message="Line 6",
            file_path="Dockerfile",
            line_number=6,
        ),
        Finding(
            rule_id="NET-ISO-003",
            family="NET-ISO",
            severity="high",
            title="Expose debug",
            message="Line 7",
            file_path="Dockerfile",
            line_number=7,
        ),
        Finding(
            rule_id="NET-ISO-001",
            family="NET-ISO",
            severity="medium",
            title="Ingress all",
            message="Line 12",
            file_path="main.tf",
            line_number=12,
        ),
    ]

    deduped = deduplicate_findings(findings)
    assert len(deduped) == 2
    rule_ids = {d.rule_id for d in deduped}
    assert rule_ids == {"NET-ISO-001", "NET-ISO-003"}
    net_003 = [d for d in deduped if d.rule_id == "NET-ISO-003"]
    assert len(net_003) == 1
    assert net_003[0].line_number == 6


@pytest.mark.integration
def test_markdown_rendering(scan_engine: ScanEngine, rule_pack) -> None:
    """Markdown rendering should contain French product text and remediation steps."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"

    findings = scan_engine.scan(fixture_dir)
    report = build_report(
        findings=findings,
        scan_id="md-test-id",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.75,
        caller_id="doc_writer",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
        llm_remediation_enabled=False,
    )

    md = render_markdown(report)
    assert "# 🛡️ Rapport de non-conformité — Vibe Guard" in md
    assert "## 1. Synthèse globale" in md
    assert "## 2. Détail des constatations et remédiations GCP-natives" in md
    assert "SECRETS" in md
    assert "Service cible" in md
    assert "Étapes de correction :" in md


@pytest.mark.integration
def test_engine_status_and_tool_error_degradation(rule_pack) -> None:
    """SPEC-ENG-4 & SPEC-REP-6: Tool error populates engine_status and marks degraded."""
    tool_err = Finding.create_tool_error(
        "gitleaks",
        "Gitleaks executable not found on host or container PATH.",
    )
    report = build_report(
        findings=[tool_err],
        scan_id="degraded-scan",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.05,
        caller_id="tester",
        pack_version=rule_pack.version,
        target="dummy_target",
    )

    # engine_status assertions
    assert report.engine_status.gitleaks.status == "error"
    assert report.engine_status.gitleaks.error_message is not None
    assert "SECRETS" in report.engine_status.coverage_degraded
    assert "SECRETS" in report.engine_status.gitleaks.degraded_families
    assert report.engine_status.semgrep.status == "ok"
    assert "AUTH" in report.engine_status.semgrep.covered_families

    # Tool error must NOT be in findings or count as a non-conformance finding
    assert len(report.findings) == 0
    assert report.summary.total_findings == 0

    # JSON export includes engine_status
    json_str = report.to_json()
    assert "engine_status" in json_str
    assert "SECRETS" in json_str

    # Markdown rendering shows warning banner and engine status table
    md_str = report.to_markdown()
    assert "Couverture de détection dégradée" in md_str
    assert "ne peut pas être interprété comme conforme" in md_str
    assert "❌ Erreur" in md_str


@pytest.mark.integration
def test_spec_rep_5_secrets_masked_in_report(scan_engine: ScanEngine, rule_pack) -> None:
    """SPEC-REP-5: No secret values appear in JSON or Markdown renderings for app_secrets_leak."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"

    findings = scan_engine.scan(fixture_dir)
    assert len(findings) >= 2

    report = build_report(
        findings=findings,
        scan_id="secret-mask-scan",
        timestamp="2026-09-18T10:00:00Z",
        duration_seconds=0.5,
        caller_id="test",
        pack_version=rule_pack.version,
        target=str(fixture_dir),
    )

    json_str = report.to_json()
    md_str = report.to_markdown()

    # Raw secrets from fixture must NOT appear in JSON or Markdown
    assert "sk-proj-abc1234567890abcdef1234567890abcdef" not in json_str
    assert "sk-proj-abc1234567890abcdef1234567890abcdef" not in md_str
    assert "super-secret-token-12345" not in json_str
    assert "super-secret-token-12345" not in md_str

    # Truncated fingerprints should be present
    assert "sk-p...[MASQUÉ]" in json_str or "sk-pr...[MASQUÉ]" in json_str or "[MASQUÉ]" in json_str
    assert "supe...[MASQUÉ]" in json_str or "[MASQUÉ]" in json_str
