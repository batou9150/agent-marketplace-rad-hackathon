"""Unit tests for rule pack loading and validation."""

from pathlib import Path

import pytest
import yaml

from vibe_guard.rules.loader import RuleValidationError, load_rule_pack
from vibe_guard.rules.models import EngineType, Family, Severity


@pytest.mark.unit
def test_manifest_missing(tmp_path: Path) -> None:
    """Loading a directory without pack.yaml should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Rule pack manifest missing"):
        load_rule_pack(tmp_path)


@pytest.mark.unit
def test_invalid_manifest(tmp_path: Path) -> None:
    """Invalid manifest should raise RuleValidationError with path and error details."""
    manifest_path = tmp_path / "pack.yaml"
    manifest_path.write_text("invalid_yaml: [}")

    with pytest.raises(RuleValidationError) as exc:
        load_rule_pack(tmp_path)

    assert str(manifest_path) in str(exc.value)


@pytest.mark.unit
def test_valid_pack_loading(tmp_path: Path) -> None:
    """Valid pack and rule definitions should load successfully."""
    manifest = {
        "version": "1.0.0",
        "name": "test-pack",
        "description": "Test pack for unit tests",
        "families": [
            {
                "id": "AUTH",
                "name": "Auth",
                "description": "Authentication checks",
            }
        ],
    }
    (tmp_path / "pack.yaml").write_text(yaml.dump(manifest))

    rule = {
        "id": "AUTH-001",
        "family": "AUTH",
        "severity": "high",
        "title": "Unauthenticated endpoint",
        "rationale": "Endpoints without auth can be accessed publicly by anyone.",
        "example": "@app.get('/admin')\ndef admin(): pass",
        "remediation": {
            "summary": "Enforce authentication",
            "gcp_service": "Cloud IAP",
            "steps": ["Enable Cloud IAP"],
            "reference_url": "https://cloud.google.com/iap",
        },
        "engine": {
            "type": "semgrep",
            "semgrep_rule": {
                "id": "auth-001",
                "message": "Missing auth",
                "languages": ["python"],
                "severity": "ERROR",
                "pattern": "@app.get('/admin')",
            },
        },
    }
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    (auth_dir / "auth_001.yaml").write_text(yaml.dump(rule))

    pack = load_rule_pack(tmp_path)
    assert pack.version == "1.0.0"
    assert len(pack.rules) == 1
    loaded_rule = pack.get_rule("AUTH-001")
    assert loaded_rule is not None
    assert loaded_rule.severity == Severity.HIGH
    assert loaded_rule.family == Family.AUTH
    assert loaded_rule.engine.type == EngineType.SEMGREP

    sem_rules = pack.get_semgrep_rules()
    assert len(sem_rules) == 1
    assert sem_rules[0]["metadata"]["vibe_guard_rule_id"] == "AUTH-001"


@pytest.mark.unit
def test_duplicate_rule_id(tmp_path: Path) -> None:
    """Duplicate rule IDs across files should raise RuleValidationError."""
    manifest = {
        "version": "1.0.0",
        "name": "test-pack",
        "description": "Test pack for unit tests",
        "families": [
            {
                "id": "AUTH",
                "name": "Auth",
                "description": "Authentication checks",
            }
        ],
    }
    (tmp_path / "pack.yaml").write_text(yaml.dump(manifest))

    rule1 = {
        "id": "AUTH-001",
        "family": "AUTH",
        "severity": "high",
        "title": "Unauthenticated endpoint 1",
        "rationale": "Endpoints without auth can be accessed publicly by anyone.",
        "example": "code 1",
        "remediation": {
            "summary": "Enforce authentication",
            "gcp_service": "Cloud IAP",
            "steps": ["Enable Cloud IAP"],
        },
        "engine": {
            "type": "semgrep",
            "semgrep_rule": {
                "id": "auth-001",
                "message": "Missing auth",
                "languages": ["python"],
                "severity": "ERROR",
                "pattern": "foo()",
            },
        },
    }
    rule2 = dict(rule1)
    rule2["title"] = "Duplicate ID rule"

    (tmp_path / "rule1.yaml").write_text(yaml.dump(rule1))
    (tmp_path / "rule2.yaml").write_text(yaml.dump(rule2))

    with pytest.raises(RuleValidationError, match="Duplicate rule id 'AUTH-001'"):
        load_rule_pack(tmp_path)


@pytest.mark.unit
def test_invalid_rule_schema(tmp_path: Path) -> None:
    """Missing mandatory fields should raise RuleValidationError."""
    manifest = {
        "version": "1.0.0",
        "name": "test-pack",
        "description": "Test pack",
        "families": [{"id": "AUTH", "name": "Auth", "description": "Authentication checks"}],
    }
    (tmp_path / "pack.yaml").write_text(yaml.dump(manifest))

    # Missing severity and remediation
    rule_invalid = {
        "id": "AUTH-002",
        "family": "AUTH",
        "title": "Missing fields",
    }
    (tmp_path / "rule_bad.yaml").write_text(yaml.dump(rule_invalid))

    with pytest.raises(RuleValidationError) as exc:
        load_rule_pack(tmp_path)

    assert "severity" in str(exc.value)
    assert "remediation" in str(exc.value)
