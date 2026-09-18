"""Data models for Vibe Guard rule pack definitions."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(StrEnum):
    """Rule severity level."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Family(StrEnum):
    """Rule security and governance family."""

    AUTH = "AUTH"
    SECRETS = "SECRETS"
    LLM_GOV = "LLM-GOV"
    NET_ISO = "NET-ISO"


class EngineType(StrEnum):
    """Underlying scanner engine type."""

    SEMGREP = "semgrep"
    GITLEAKS = "gitleaks"


class RemediationDef(BaseModel):
    """GCP-native remediation recommendation."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=5, description="Executive summary of remediation")
    gcp_service: str = Field(..., min_length=2, description="Target GCP service or component")
    steps: list[str] = Field(..., min_length=1, description="Concrete implementation steps")
    reference_url: str | None = Field(default=None, description="Official documentation link")


class EngineDef(BaseModel):
    """Underlying engine execution configuration."""

    model_config = ConfigDict(extra="forbid")

    type: EngineType = Field(..., description="Engine type: semgrep or gitleaks")
    semgrep_rule: dict[str, Any] | None = Field(default=None, description="Semgrep rule definition")
    gitleaks_rule: dict[str, Any] | None = Field(
        default=None, description="Gitleaks rule definition"
    )

    @model_validator(mode="after")
    def validate_engine_payload(self) -> "EngineDef":
        """Ensure the appropriate payload is supplied for the engine type."""
        if self.type == EngineType.SEMGREP and not self.semgrep_rule:
            raise ValueError("semgrep_rule must be provided when engine type is 'semgrep'")
        if self.type == EngineType.GITLEAKS and not self.gitleaks_rule:
            raise ValueError("gitleaks_rule must be provided when engine type is 'gitleaks'")
        return self


class RuleDef(BaseModel):
    """Single declarative rule definition."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Z0-9_-]+$", description="Unique rule identifier")
    family: Family = Field(..., description="Security family")
    severity: Severity = Field(..., description="Rule severity")
    title: str = Field(..., min_length=5, description="Rule title")
    rationale: str = Field(..., min_length=10, description="Risk explanation")
    example: str = Field(..., min_length=5, description="Code example showing the vulnerability")
    remediation: RemediationDef = Field(..., description="GCP-native remediation")
    engine: EngineDef = Field(..., description="Scanning engine configuration")


class RuleFamilyDef(BaseModel):
    """Rule family description in manifest."""

    model_config = ConfigDict(extra="forbid")

    id: Family = Field(..., description="Family ID")
    name: str = Field(..., min_length=2, description="Family human-readable name")
    description: str = Field(..., min_length=5, description="Family scope description")


class PackManifest(BaseModel):
    """Rule pack manifest declaration."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., description="Pack semver version")
    name: str = Field(..., min_length=2, description="Pack name")
    description: str = Field(..., min_length=5, description="Pack description")
    families: list[RuleFamilyDef] = Field(..., min_length=1, description="Registered families")
