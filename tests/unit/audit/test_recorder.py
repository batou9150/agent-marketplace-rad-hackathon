"""Additional unit tests for audit records and logger sinks (Constraint C6)."""

import json
from pathlib import Path

import pytest

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder


@pytest.mark.unit
def test_audit_record_payload_fields() -> None:
    """Verify to_log_payload and to_dict produce identical structured output without code."""
    record = ScanAuditRecord.create(
        caller_id="system-agent",
        pack_version="0.1.0",
        rules_evaluated=["AUTH-001", "NET-ISO-001"],
        duration_seconds=0.456,
        findings_count=1,
        findings_by_severity={"high": 1},
        target_source_type="git_url",
    )

    payload = record.to_log_payload()
    dict_repr = record.to_dict()

    assert payload["caller_id"] == "system-agent"
    assert payload["pack_version"] == "0.1.0"
    assert payload["total_findings"] == 1
    assert dict_repr["findings_count"] == 1
    assert payload["rules_evaluated"] == ["AUTH-001", "NET-ISO-001"]
    assert "code" not in payload
    assert "snippet" not in payload


@pytest.mark.unit
def test_audit_recorder_appends_multiple_records(tmp_path: Path) -> None:
    """AuditRecorder must append subsequent scan records to the JSONL log file."""
    sink = tmp_path / "scans.jsonl"
    recorder = AuditRecorder(sink_file=sink)

    for i in range(3):
        rec = ScanAuditRecord.create(
            caller_id=f"user-{i}",
            pack_version="0.1.0",
            rules_evaluated=["AUTH-001"],
            duration_seconds=0.1 * (i + 1),
            findings_count=i,
            findings_by_severity={},
            target_source_type="directory",
        )
        recorder.record(rec)

    assert sink.is_file()
    lines = sink.read_text().strip().split("\n")
    assert len(lines) == 3
    for i, line in enumerate(lines):
        item = json.loads(line)
        assert item["caller_id"] == f"user-{i}"
        assert item["findings_count"] == i
