"""Verify integrity and schema of fixtures and their expected findings."""

from pathlib import Path
import pytest
import yaml


@pytest.mark.unit
def test_fixtures_structure() -> None:
    """Validate that all nonconform and conform fixtures have valid expected findings."""
    fixtures_dir = Path(__file__).parents[3] / "fixtures"

    nonconform_dirs = [d for d in (fixtures_dir / "nonconform").iterdir() if d.is_dir()]
    assert len(nonconform_dirs) >= 4, "Must have at least 4 nonconforming fixtures"

    conform_dirs = [d for d in (fixtures_dir / "conform").iterdir() if d.is_dir()]
    assert len(conform_dirs) >= 2, "Must have at least 2 conforming fixtures"

    # Validate nonconform fixtures
    for fixture in nonconform_dirs:
        expected_file = fixture / "findings.expected.yaml"
        assert expected_file.is_file(), f"Missing findings.expected.yaml in {fixture}"
        with open(expected_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "expected_findings" in data
        assert len(data["expected_findings"]) >= 1, (
            f"{fixture} should have at least 1 expected finding"
        )
        for finding in data["expected_findings"]:
            assert "rule_id" in finding
            assert "family" in finding
            assert "file" in finding
            assert "severity" in finding

    # Validate conform fixtures
    for fixture in conform_dirs:
        expected_file = fixture / "findings.expected.yaml"
        assert expected_file.is_file(), f"Missing findings.expected.yaml in {fixture}"
        with open(expected_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "expected_findings" in data
        assert len(data["expected_findings"]) == 0, f"{fixture} should have 0 expected findings"
