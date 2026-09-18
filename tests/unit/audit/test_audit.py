"""Unit tests for audit logging and scan traceability (Constraint C6)."""

import json
from pathlib import Path

import pytest

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder


@pytest.mark.unit
def test_scan_audit_record_creation() -> None:
    """Audit record must record pack version, evaluated rules, duration, and caller ID."""
    record = ScanAuditRecord.create(
        caller_id="user_123",
        pack_version="0.1.0",
        rules_evaluated=["AUTH-001", "SECRETS-001"],
        duration_seconds=1.42,
        findings_count=3,
        findings_by_severity={"critical": 1, "high": 2},
        target_source_type="git_url",
    )
    assert record.caller_id == "user_123"
    assert record.pack_version == "0.1.0"
    assert len(record.rules_evaluated) == 2
    assert record.duration_seconds == 1.42
    assert record.scan_id is not None
    assert record.timestamp is not None

    data = record.to_dict()
    # Ensure no code snippets or raw contents are logged (C2/C6)
    assert "code" not in data
    assert "snippet" not in data
    assert "raw_content" not in data


@pytest.mark.unit
def test_audit_recorder_persists_json(tmp_path: Path) -> None:
    """AuditRecorder should serialize records to structured JSON file or stream."""
    log_file = tmp_path / "scans.jsonl"
    recorder = AuditRecorder(sink_file=log_file)

    record = ScanAuditRecord.create(
        caller_id="service_account@project.iam.gserviceaccount.com",
        pack_version="0.1.0",
        rules_evaluated=["AUTH-001"],
        duration_seconds=0.85,
        findings_count=0,
        findings_by_severity={},
        target_source_type="archive",
    )
    recorder.record(record)

    assert log_file.is_file()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    logged_obj = json.loads(lines[0])
    assert logged_obj["caller_id"] == "service_account@project.iam.gserviceaccount.com"
    assert logged_obj["pack_version"] == "0.1.0"
