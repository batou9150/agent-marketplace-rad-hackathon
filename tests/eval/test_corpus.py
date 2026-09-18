"""Evaluation gate tests for corpus recall, precision, and ephemeral cleanup (Gate 2)."""

from pathlib import Path

import pytest
import yaml

from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.ingest.workspace import EphemeralWorkspace
from vibe_guard.rules.loader import load_rule_pack


@pytest.fixture(scope="module")
def engine() -> ScanEngine:
    repo_root = Path(__file__).parents[2]
    rule_pack = load_rule_pack(repo_root / "rules")
    return ScanEngine(rule_pack)


@pytest.mark.eval
def test_gate2_corpus_recall_is_one(engine: ScanEngine) -> None:
    """Gate 2 metric: 100% of expected findings in non-conforming fixtures
    are detected (recall = 1.0).
    """
    repo_root = Path(__file__).parents[2]
    fixtures_dir = repo_root / "fixtures" / "nonconform"

    total_expected = 0
    total_detected = 0

    for fixture_dir in sorted(fixtures_dir.iterdir()):
        if not fixture_dir.is_dir():
            continue

        expected_file = fixture_dir / "findings.expected.yaml"
        assert expected_file.is_file(), f"Missing findings.expected.yaml in {fixture_dir}"
        with open(expected_file, encoding="utf-8") as f:
            expected_data = yaml.safe_load(f)

        expected_rules = [ef["rule_id"] for ef in expected_data["expected_findings"]]
        total_expected += len(expected_rules)

        findings = engine.scan(fixture_dir)
        detected_rule_ids = {f.rule_id for f in findings if not f.is_tool_error}

        for rule_id in expected_rules:
            if rule_id in detected_rule_ids:
                total_detected += 1
            else:
                pytest.fail(
                    f"Recall failure in fixture '{fixture_dir.name}': "
                    f"rule '{rule_id}' was expected but not detected. "
                    f"Detected: {detected_rule_ids}"
                )

    recall = total_detected / total_expected if total_expected > 0 else 0.0
    assert recall == 1.0, f"Corpus recall must be exactly 1.0, got {recall:.2f}"


@pytest.mark.eval
def test_spec_rul_7_all_rules_covered_by_nonconform_fixtures(engine: ScanEngine) -> None:
    """SPEC-RUL-7: Every defined rule must have at least one non-conforming
    fixture triggering it.
    """
    repo_root = Path(__file__).parents[2]
    fixtures_dir = repo_root / "fixtures" / "nonconform"

    covered_rules: set[str] = set()
    for fixture_dir in fixtures_dir.iterdir():
        expected_file = fixture_dir / "findings.expected.yaml"
        if expected_file.is_file():
            with open(expected_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            for ef in data.get("expected_findings", []):
                covered_rules.add(ef["rule_id"])

    pack_rule_ids = {r.id for r in engine.rule_pack.rules}
    uncovered = pack_rule_ids - covered_rules
    assert not uncovered, f"SPEC-RUL-7 violation: rules without non-conforming fixture: {uncovered}"


@pytest.mark.eval
def test_gate2_corpus_precision_is_one(engine: ScanEngine) -> None:
    """Gate 2 metric: 0 unexpected findings in conforming fixtures (precision = 1.0)."""
    repo_root = Path(__file__).parents[2]
    fixtures_dir = repo_root / "fixtures" / "conform"

    conforming_count = 0
    for fixture_dir in sorted(fixtures_dir.iterdir()):
        if not fixture_dir.is_dir():
            continue

        conforming_count += 1
        findings = engine.scan(fixture_dir)
        non_tool_findings = [f for f in findings if not f.is_tool_error]

        assert len(non_tool_findings) == 0, (
            f"Precision failure in conforming fixture '{fixture_dir.name}': "
            f"expected 0 findings, got {[f.rule_id for f in non_tool_findings]}"
        )

    assert conforming_count >= 2, "Must evaluate at least 2 conforming fixtures"


@pytest.mark.eval
def test_gate2_ephemeral_workspace_purged_on_normal_and_exception(tmp_path: Path) -> None:
    """Gate 2 constraint C2: Scan workspace directory is purged on normal and failure paths."""
    ws_path1: Path | None = None
    with EphemeralWorkspace(base_dir=tmp_path) as ws:
        ws_path1 = ws.path
        assert ws_path1.is_dir()
        (ws_path1 / "dummy.txt").write_text("sensible code")

    assert ws_path1 is not None
    assert not ws_path1.exists(), "Workspace not deleted after normal completion"

    ws_path2: Path | None = None
    with (
        pytest.raises(RuntimeError, match="Simulation error"),
        EphemeralWorkspace(base_dir=tmp_path) as ws,
    ):
        ws_path2 = ws.path
        assert ws_path2.is_dir()
        (ws_path2 / "secret.key").write_text("topsecret")
        raise RuntimeError("Simulation error")

    assert ws_path2 is not None
    assert not ws_path2.exists(), "Workspace not deleted after unhandled exception"
