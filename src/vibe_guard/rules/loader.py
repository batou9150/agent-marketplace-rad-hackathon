"""Rule pack loading, parsing, and strict schema validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vibe_guard.rules.models import Family, PackManifest, RuleDef


class RuleValidationError(Exception):
    """Raised when a rule pack or rule file fails schema validation."""

    def __init__(self, file_path: Path, errors: list[str]) -> None:
        self.file_path = file_path
        self.errors = errors
        formatted = "\n  - ".join(errors)
        super().__init__(f"Rule validation error in {file_path}:\n  - {formatted}")


class RulePack:
    """Loaded and validated rule pack containing manifest and all rule definitions."""

    def __init__(self, manifest: PackManifest, rules: list[RuleDef], directory: Path) -> None:
        self.manifest = manifest
        self.rules = rules
        self.directory = directory
        self._rules_by_id = {rule.id: rule for rule in rules}

    @property
    def version(self) -> str:
        return self.manifest.version

    def get_rule(self, rule_id: str) -> RuleDef | None:
        """Find a rule by its ID."""
        return self._rules_by_id.get(rule_id)

    def by_family(self, family: Family | str) -> list[RuleDef]:
        """Filter rules by family (accepts Family enum or string)."""
        target = family.value if isinstance(family, Family) else str(family)
        return [rule for rule in self.rules if rule.family.value == target]

    def get_semgrep_rules(self) -> list[dict[str, Any]]:
        """Extract all Semgrep rule definitions with embedded Vibe Guard metadata."""
        semgrep_rules: list[dict[str, Any]] = []
        for rule in self.rules:
            if rule.engine.type == "semgrep" and rule.engine.semgrep_rule:
                sem_rule = dict(rule.engine.semgrep_rule)
                # Ensure metadata contains Vibe Guard reference
                metadata = dict(sem_rule.get("metadata", {}))
                metadata["vibe_guard_rule_id"] = rule.id
                metadata["family"] = rule.family.value
                metadata["severity"] = rule.severity.value
                sem_rule["metadata"] = metadata
                semgrep_rules.append(sem_rule)
        return semgrep_rules

    def get_gitleaks_rules(self) -> list[dict[str, Any]]:
        """Extract all Gitleaks rule definitions."""
        gitleaks_rules: list[dict[str, Any]] = []
        for rule in self.rules:
            if rule.engine.type == "gitleaks" and rule.engine.gitleaks_rule:
                git_rule = dict(rule.engine.gitleaks_rule)
                git_rule["vibe_guard_rule_id"] = rule.id
                gitleaks_rules.append(git_rule)
        return gitleaks_rules


def load_rule_pack(rules_dir: Path | str) -> RulePack:
    """Load and validate all rules and manifest in a rule directory.

    Raises:
        RuleValidationError: if manifest or any rule file fails validation.
        FileNotFoundError: if rules_dir or manifest does not exist.
    """
    path = Path(rules_dir)
    if not path.is_dir():
        raise FileNotFoundError(f"Rules directory not found: {path}")

    manifest_path = path / "pack.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Rule pack manifest missing: {manifest_path}")

    # Load and validate manifest
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
        manifest = PackManifest.model_validate(manifest_data)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        raise RuleValidationError(manifest_path, errors) from exc
    except Exception as exc:
        raise RuleValidationError(manifest_path, [str(exc)]) from exc

    # Load all rule files
    rules: list[RuleDef] = []
    seen_ids: dict[str, Path] = {}

    for rule_file in sorted(path.rglob("*.yaml")):
        if rule_file.name == "pack.yaml":
            continue

        try:
            with open(rule_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data:
                continue

            rule = RuleDef.model_validate(data)

            if rule.id in seen_ids:
                raise RuleValidationError(
                    rule_file,
                    [f"Duplicate rule id '{rule.id}' already defined in {seen_ids[rule.id]}"],
                )

            seen_ids[rule.id] = rule_file
            rules.append(rule)

        except ValidationError as exc:
            errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
            ]
            raise RuleValidationError(rule_file, errors) from exc
        except RuleValidationError:
            raise
        except Exception as exc:
            raise RuleValidationError(rule_file, [str(exc)]) from exc

    return RulePack(manifest=manifest, rules=rules, directory=path)
