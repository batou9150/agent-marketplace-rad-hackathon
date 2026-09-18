"""Audit module for Vibe Guard scan traceability (C6)."""

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder

__all__ = ["ScanAuditRecord", "AuditRecorder"]
