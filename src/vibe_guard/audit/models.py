"""Data models for audit trails and scan traceability (Constraint C6)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScanAuditRecord(BaseModel):
    """Immutable audit record generated for each repository scan execution.

    Never stores raw source code snippets to protect intellectual property
    and confidentiality (Constraint C2 & C6).
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
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

    @classmethod
    def from_scan(
        cls,
        scan_id: str,
        timestamp: str,
        duration_seconds: float,
        caller_id: str,
        pack_version: str,
        target: str,
        findings: list[Any] | None = None,
        rules_evaluated: list[str] | None = None,
    ) -> "ScanAuditRecord":
        """Construct a full audit record directly from scan results."""
        findings_list = findings or []
        rules_list = rules_evaluated or []
        sev_counts: dict[str, int] = {}
        fam_counts: dict[str, int] = {}
        tool_errors = 0

        for f in findings_list:
            if getattr(f, "is_tool_error", False):
                tool_errors += 1
                continue
            sev = str(getattr(f, "severity", "medium")).lower()
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
            fam = str(getattr(f, "family", "UNKNOWN"))
            fam_counts[fam] = fam_counts.get(fam, 0) + 1

        target_type = "directory"
        if target.startswith(("https://", "http://", "git@", "ssh://")):
            target_type = "git_url"
        elif any(target.endswith(e) for e in [".zip", ".tar.gz", ".tgz", ".tar"]):
            target_type = "archive"

        return cls(
            scan_id=scan_id,
            timestamp=timestamp,
            caller_id=caller_id,
            pack_version=pack_version,
            rules_evaluated=rules_list,
            rules_count=len(rules_list),
            duration_seconds=round(duration_seconds, 3),
            target_type=target_type,
            total_findings=len(findings_list) - tool_errors,
            findings_by_severity=sev_counts,
            findings_by_family=fam_counts,
            tool_errors_count=tool_errors,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary representation."""
        data = self.model_dump()
        data["findings_count"] = self.total_findings
        return data

    def to_log_payload(self) -> dict[str, Any]:
        """Convert to structured Cloud Logging JSON payload."""
        return self.to_dict()
