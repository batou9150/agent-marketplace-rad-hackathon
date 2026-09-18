"""Domain and schema models for Vibe Guard reports (Phase 3)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReportMetadata(BaseModel):
    """Metadata regarding scan execution and environment."""

    model_config = ConfigDict(extra="forbid")

    scan_id: str
    timestamp: str
    duration_seconds: float
    caller_id: str
    pack_version: str
    target: str
    llm_remediation_enabled: bool = False


class ReportSummary(BaseModel):
    """Aggregated statistics across findings."""

    model_config = ConfigDict(extra="forbid")

    total_findings: int
    by_severity: dict[str, int]
    by_family: dict[str, int]


class ReportSnippet(BaseModel):
    """Bounded snippet of code surrounding a finding (Constraint C2)."""

    model_config = ConfigDict(extra="forbid")

    start_line: int
    end_line: int
    highlight_line: int
    content: str = Field(..., max_length=1600)


class ReportRemediation(BaseModel):
    """GCP-native remediation guidance, optionally enriched by Gemini."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    gcp_service: str
    steps: list[str]
    reference_url: str | None = None
    contextual_advice: str | None = None


class ReportFinding(BaseModel):
    """Actionable finding in report."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    family: str
    severity: str
    title: str
    message: str
    file_path: str
    line_number: int
    snippet: ReportSnippet | None = None
    remediation: ReportRemediation


class ScannerStatus(BaseModel):
    """Execution status and coverage state for a single scanner tool."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"  # "ok", "error", "skipped"
    version: str | None = None
    error_message: str | None = None
    covered_families: list[str] = Field(default_factory=list)
    degraded_families: list[str] = Field(default_factory=list)


class EngineStatus(BaseModel):
    """Aggregate engine status across all detection scanners (SPEC-REP-6)."""

    model_config = ConfigDict(extra="forbid")

    semgrep: ScannerStatus
    gitleaks: ScannerStatus
    coverage_degraded: list[str] = Field(default_factory=list)


class Report(BaseModel):
    """Complete Vibe Guard security and compliance report."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_uri: str = Field(
        default="https://vibe-guard.dev/schemas/v1/report.json",
        alias="$schema",
    )
    version: str = "1.0.0"
    metadata: ReportMetadata
    summary: ReportSummary
    engine_status: EngineStatus
    findings: list[ReportFinding]

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to validated JSON string."""
        from vibe_guard.report.renderer import render_json

        return render_json(self, indent=indent)

    def to_markdown(self) -> str:
        """Render report as human-readable Markdown in French."""
        from vibe_guard.report.renderer import render_markdown

        return render_markdown(self)
