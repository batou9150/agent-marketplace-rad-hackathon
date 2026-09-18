"""Validate the official production rule pack (Gate 1 requirements)."""

from pathlib import Path

import pytest

from vibe_guard.rules.loader import load_rule_pack
from vibe_guard.rules.models import Family


@pytest.mark.unit
def test_production_pack_loads_successfully() -> None:
    """The production rule pack must load without errors and meet Phase 1 minimums."""
    rules_dir = Path(__file__).parents[3] / "rules"
    pack = load_rule_pack(rules_dir)

    assert pack.version == "0.1.0"
    assert len(pack.rules) >= 12, "Production pack must have at least 12 rules"

    # Minimum 3 rules per family
    for family in Family:
        family_rules = pack.by_family(family)
        assert len(family_rules) >= 3, (
            f"Family {family.value} must have at least 3 rules, got {len(family_rules)}"
        )

    # Every rule must satisfy the 6 metadata fields + remediation + engine
    for rule in pack.rules:
        assert len(rule.id) > 0
        assert rule.severity in ["critical", "high", "medium", "low"]
        assert len(rule.title) >= 5
        assert len(rule.rationale) >= 10
        assert len(rule.example) >= 5
        assert len(rule.remediation.summary) >= 5
        assert len(rule.remediation.gcp_service) >= 2
        assert len(rule.remediation.steps) >= 1
