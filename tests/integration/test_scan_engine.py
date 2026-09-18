"""Integration test running ScanEngine on fixtures."""

from pathlib import Path

import pytest
import yaml

from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.rules.loader import load_rule_pack


@pytest.fixture(scope="module")
def engine() -> ScanEngine:
    repo_root = Path(__file__).parents[2]
    rule_pack = load_rule_pack(repo_root / "rules")
    return ScanEngine(rule_pack)


@pytest.mark.integration
def test_scan_all_nonconform_fixtures(engine: ScanEngine) -> None:
    """Scan each non-conforming fixture and verify expected rule IDs are detected."""
    repo_root = Path(__file__).parents[2]
    fixtures_dir = repo_root / "fixtures" / "nonconform"

    for fixture_dir in fixtures_dir.iterdir():
        if not fixture_dir.is_dir():
            continue

        expected_file = fixture_dir / "findings.expected.yaml"
        with open(expected_file, encoding="utf-8") as f:
            expected_data = yaml.safe_load(f)

        expected_rules = {ef["rule_id"] for ef in expected_data["expected_findings"]}

        findings = engine.scan(fixture_dir)
        detected_rules = {f.rule_id for f in findings if not f.is_tool_error}

        for expected_rule in expected_rules:
            assert expected_rule in detected_rules, (
                f"Fixture {fixture_dir.name} failed to detect expected rule {expected_rule}. "
                f"Detected: {detected_rules}"
            )


@pytest.mark.integration
def test_scan_all_conform_fixtures(engine: ScanEngine) -> None:
    """Scan conforming fixtures and verify zero non-tool findings are detected."""
    repo_root = Path(__file__).parents[2]
    fixtures_dir = repo_root / "fixtures" / "conform"

    for fixture_dir in fixtures_dir.iterdir():
        if not fixture_dir.is_dir():
            continue

        findings = engine.scan(fixture_dir)
        actionable_findings = [f for f in findings if not f.is_tool_error]
        assert len(actionable_findings) == 0, (
            f"Conform fixture {fixture_dir.name} produced unexpected findings: "
            f"{[f.rule_id for f in actionable_findings]}"
        )
