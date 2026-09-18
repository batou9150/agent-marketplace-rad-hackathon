from dataclasses import dataclass, field

from vibe_guard.rules.models import Severity as Severity

__all__ = ["Finding", "Severity", "Snippet"]


@dataclass(frozen=True)
class Snippet:
    """Bounded snippet of code surrounding a finding (Constraint C2)."""

    start_line: int
    end_line: int
    highlight_line: int
    content: str


@dataclass
class Finding:
    """Normalized security finding resulting from a static analysis scan."""

    rule_id: str
    family: str
    severity: str
    title: str
    message: str
    file_path: str
    line_number: int
    snippet: Snippet | None = None
    is_tool_error: bool = False
    detected_secret: str | None = None
    remediation_summary: str | None = None
    remediation_gcp_service: str | None = None
    remediation_steps: list[str] = field(default_factory=list)

    @classmethod
    def create_tool_error(cls, tool_name: str, error_message: str) -> "Finding":
        """Factory for errors originating from underlying tools (semgrep, gitleaks)."""
        normalized_tool = tool_name.upper()
        return cls(
            rule_id=f"TOOL-ERR-{normalized_tool}",
            family="ENGINE",
            severity="high",
            title=f"Scanner execution failure ({tool_name})",
            message=error_message,
            file_path="",
            line_number=0,
            is_tool_error=True,
            remediation_summary=f"Verify configuration and permissions for {tool_name} binary.",
            remediation_gcp_service="Scan Engine Runtime",
            remediation_steps=["Check environment dependencies and memory allocation."],
        )
