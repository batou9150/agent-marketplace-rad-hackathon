"""Audit record creation and logging sink management."""

import json
import logging
from pathlib import Path

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.engine.models import Finding
from vibe_guard.rules.loader import RulePack

logger = logging.getLogger("vibe_guard.audit")


class AuditRecorder:
    """Manages audit logging for scan executions."""

    def __init__(
        self,
        log_file: Path | str | None = None,
        sink_file: Path | str | None = None,
    ) -> None:
        target = sink_file or log_file
        self.sink_file = Path(target) if target else None
        self.log_file = self.sink_file

    def record(self, record: ScanAuditRecord) -> None:
        """Directly emit and persist a ScanAuditRecord."""
        logger.info(
            "Scan audit record generated",
            extra={"audit_record": record.to_log_payload()},
        )

        if self.sink_file:
            self.sink_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sink_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")

    def record_scan(
        self,
        caller_id: str,
        rule_pack: RulePack,
        findings: list[Finding],
        duration_seconds: float,
        target_type: str = "directory",
    ) -> ScanAuditRecord:
        """Create and emit an audit record summarizing the scan without leaking code."""
        rules_evaluated = [rule.id for rule in rule_pack.rules]
        findings_by_sev: dict[str, int] = {}
        findings_by_fam: dict[str, int] = {}
        tool_errors = 0

        for f in findings:
            if f.is_tool_error:
                tool_errors += 1
                continue
            sev = f.severity.lower()
            findings_by_sev[sev] = findings_by_sev.get(sev, 0) + 1
            findings_by_fam[f.family] = findings_by_fam.get(f.family, 0) + 1

        record = ScanAuditRecord(
            caller_id=caller_id,
            pack_version=rule_pack.version,
            rules_evaluated=rules_evaluated,
            rules_count=len(rules_evaluated),
            duration_seconds=round(duration_seconds, 3),
            target_type=target_type,
            total_findings=len(findings) - tool_errors,
            findings_by_severity=findings_by_sev,
            findings_by_family=findings_by_fam,
            tool_errors_count=tool_errors,
        )

        self.record(record)
        return record
