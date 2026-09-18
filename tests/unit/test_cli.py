"""Unit tests for Vibe Guard CLI (SPEC-ENG-4, SPEC-REP-1, Section 4.3)."""

from pathlib import Path
from unittest.mock import patch

from vibe_guard.cli import main
from vibe_guard.engine.models import Finding


def test_cli_rules_validate_success(capsys) -> None:
    """Rules validate should succeed on valid pack."""
    repo_root = Path(__file__).parents[2]
    rules_dir = repo_root / "rules"

    code = main(["rules", "validate", "--rules", str(rules_dir)])
    assert code == 0
    captured = capsys.readouterr()
    assert "valide" in captured.out.lower() or "valid" in captured.out.lower()


def test_cli_rules_validate_invalid(tmp_path, capsys) -> None:
    """Rules validate should return exit code 2 on invalid rules."""
    bad_pack = tmp_path / "bad_rules"
    bad_pack.mkdir()
    (bad_pack / "pack.yaml").write_text("invalid_manifest: true\n")

    code = main(["rules", "validate", "--rules", str(bad_pack)])
    assert code == 2
    captured = capsys.readouterr()
    assert "error" in captured.err.lower() or "erreur" in captured.err.lower()


def test_cli_rules_list(capsys) -> None:
    """Rules list should list all rules, or filtered by family."""
    repo_root = Path(__file__).parents[2]
    rules_dir = repo_root / "rules"

    # All rules
    code = main(["rules", "list", "--rules", str(rules_dir)])
    assert code == 0
    captured = capsys.readouterr()
    assert "AUTH-001" in captured.out
    assert "SECRETS-001" in captured.out
    assert "NET-ISO-001" in captured.out

    # Filtered by family
    code = main(["rules", "list", "--rules", str(rules_dir), "--family", "SECRETS"])
    assert code == 0
    captured = capsys.readouterr()
    assert "SECRETS-001" in captured.out
    assert "AUTH-001" not in captured.out


def test_cli_scan_clean_fixture(capsys) -> None:
    """Scanning a clean fixture must return exit code 0."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "conform" / "clean_python_app"
    rules_dir = repo_root / "rules"

    code = main(["scan", str(fixture_dir), "--rules", str(rules_dir), "--no-llm"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Rapport de non-conformité" in captured.out or "Synthèse globale" in captured.out


def test_cli_scan_nonconform_fixture(capsys) -> None:
    """Scanning a non-conforming fixture must return exit code 1."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_auth_fail"
    rules_dir = repo_root / "rules"

    code = main(["scan", str(fixture_dir), "--rules", str(rules_dir), "--no-llm"])
    assert code == 1
    captured = capsys.readouterr()
    assert "AUTH" in captured.out


def test_cli_scan_invalid_source(capsys) -> None:
    """Scanning a non-existent source must return exit code 2 (ingestion error)."""
    repo_root = Path(__file__).parents[2]
    rules_dir = repo_root / "rules"

    code = main(["scan", "/non/existent/path/for/sure", "--rules", str(rules_dir)])
    assert code == 2
    captured = capsys.readouterr()
    assert "error" in captured.err.lower() or "erreur" in captured.err.lower()


def test_cli_scan_engine_degraded_exit_code_3(capsys) -> None:
    """SPEC-ENG-4: Scan with degraded engine status must return exit code 3."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "conform" / "clean_python_app"
    rules_dir = repo_root / "rules"

    # Simulate gitleaks missing or producing a tool error
    with patch("vibe_guard.engine.scanner.run_gitleaks") as mock_git:
        mock_git.return_value = [
            Finding.create_tool_error("gitleaks", "Gitleaks binary missing on system")
        ]
        code = main(["scan", str(fixture_dir), "--rules", str(rules_dir), "--no-llm"])
        assert code == 3

    captured = capsys.readouterr()
    degraded_match = (
        "dégradée" in captured.out
        or "degraded" in captured.out.lower()
        or "SECRETS" in captured.out
    )
    assert degraded_match


def test_cli_scan_out_files(tmp_path) -> None:
    """Scan with --out and --format both generates both json and markdown files."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"
    rules_dir = repo_root / "rules"
    out_base = tmp_path / "security_report"

    code = main(
        [
            "scan",
            str(fixture_dir),
            "--rules",
            str(rules_dir),
            "--no-llm",
            "--format",
            "both",
            "--out",
            str(out_base),
        ]
    )
    assert code == 1

    json_file = tmp_path / "security_report.json"
    md_file = tmp_path / "security_report.md"
    assert json_file.is_file()
    assert md_file.is_file()

    json_content = json_file.read_text()
    md_content = md_file.read_text()

    # Secret masking verification (SPEC-REP-5)
    assert "sk-proj-abc1234567890abcdef1234567890abcdef" not in json_content
    assert "sk-proj-abc1234567890abcdef1234567890abcdef" not in md_content


def test_cli_scan_families_filter_and_aliases(tmp_path) -> None:
    """Scan with --families AUTH on secrets fixture returns 0 findings and supports aliases."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "nonconform" / "app_secrets_leak"
    rules_dir = repo_root / "rules"
    out_file = tmp_path / "custom_report.md"

    # Using --rules-pack, --out-file, and --families AUTH
    code = main(
        [
            "scan",
            str(fixture_dir),
            "--rules-pack",
            str(rules_dir),
            "--families",
            "AUTH",
            "--no-llm",
            "--out-file",
            str(out_file),
        ]
    )
    # Since only AUTH rules were evaluated, secrets fixture is clean of AUTH findings
    assert code == 0
    assert out_file.is_file()
    assert "Total de non-conformités identifiées : **0**" in out_file.read_text()


def test_cli_scan_invalid_family(capsys) -> None:
    """Scan with an unknown family name must exit with code 2."""
    repo_root = Path(__file__).parents[2]
    fixture_dir = repo_root / "fixtures" / "conform" / "clean_python_app"
    rules_dir = repo_root / "rules"

    code = main(
        [
            "scan",
            str(fixture_dir),
            "--rules",
            str(rules_dir),
            "--families",
            "UNKNOWN_FAMILY",
            "--no-llm",
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert "Famille inconnue" in captured.err
