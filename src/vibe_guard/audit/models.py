"""Data models for audit trails and scan traceability (Constraint C6)."""

from datetime import datetime, timezone
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScanAuditRecord(BaseModel):
    """Immutable audit record generated for each repository scan execution.

    Never stores raw source code snippets to protect intellectual property and confidentiality (Constraint C2 & C6).
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    caller_id: str = Field(default="anonymous", description="Authenticated caller identifier")
    pack_version: str = Field(..., description="Vibe Guard rule pack version")
    rules_evaluated: list[str] = Field(..., description="List of evaluated rule IDs")
    rules_count: int = Field(default=0, description="Number of rules evaluated")
    duration_seconds: float = Field(..., description="Scan duration in seconds")
    target_type: str = Field(
        default="directory", description="Source format: directory, git, archive, git_url"
    )
    total_findings: int = Field(default=0, description="Total non-conformities identified")
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_family: dict[str, int] = Field(default_factory=dict)
    tool_errors_count: int = Field(default=0)

    @model_validator(mode="before")
    @classmethod
    def handle_compat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rules_count" not in data and "rules_evaluated" in data:
                data["rules_count"] = len(data["rules_evaluated"])
            if "total_findings" not in data and "findings_count" in data:
                data["total_findings"] = data.pop("findings_count")
            if "target_type" not in data and "target_source_type" in data:
                data["target_type"] = data.pop("target_source_type")
        return data

    @property
    def findings_count(self) -> int:
        return self.total_findings

    @classmethod
    def create(
        cls,
        caller_id: str,
        pack_version: str,
        rules_evaluated: list[str],
        duration_seconds: float,
        findings_count: int = 0,
        findings_by_severity: dict[str, int] | None = None,
        target_source_type: str = "directory",
    ) -> "ScanAuditRecord":
        """Factory method to construct an audit record."""
        return cls(
            caller_id=caller_id,
            pack_version=pack_version,
            rules_evaluated=rules_evaluated,
            rules_count=len(rules_evaluated),
            duration_seconds=duration_seconds,
            target_type=target_source_type,
            total_findings=findings_count,
            findings_by_severity=findings_by_severity or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary representation."""
        data = self.model_dump()
        data["findings_count"] = self.total_findings
        return data

    def to_log_payload(self) -> dict[str, Any]:
        """Convert to structured Cloud Logging JSON payload."""
        return self.to_dict()
