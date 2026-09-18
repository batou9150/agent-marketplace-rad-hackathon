"""Unit tests for ephemeral workspace cleanup and bounds enforcement (Gate 2 / Constraint C2)."""

import zipfile
from pathlib import Path

import pytest

from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError, IngestLimits


@pytest.mark.unit
def test_workspace_purged_on_normal_exit(tmp_path: Path) -> None:
    """The ephemeral directory must not exist after context manager normal exit."""
    recorded_path: Path | None = None
    with EphemeralWorkspace(base_dir=tmp_path) as ws:
        assert ws.path is not None
        assert ws.path.is_dir()
        recorded_path = ws.path
        # Write a dummy file to simulate scan files
        (ws.path / "temp_file.py").write_text("print('sensitive code')")

    assert recorded_path is not None
    assert not recorded_path.exists(), "Ephemeral directory must be completely removed on exit"


@pytest.mark.unit
def test_workspace_purged_on_exception(tmp_path: Path) -> None:
    """The ephemeral directory must be guaranteed purged even if an exception occurs."""
    recorded_path: Path | None = None
    with (
        pytest.raises(RuntimeError, match="Simulated scan crash"),
        EphemeralWorkspace(base_dir=tmp_path) as ws,
    ):
        assert ws.path is not None
        assert ws.path.is_dir()
        recorded_path = ws.path
        (ws.path / "sensitive.txt").write_text("proprietary code")
        raise RuntimeError("Simulated scan crash")

    assert recorded_path is not None
    assert not recorded_path.exists(), "Ephemeral directory must be purged on exception in finally"


@pytest.mark.unit
def test_zip_slip_prevention(tmp_path: Path) -> None:
    """Archives with path traversal elements must be rejected before extraction."""
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:")

    with (
        pytest.raises(IngestionError, match="Path traversal detected"),
        EphemeralWorkspace(base_dir=tmp_path) as ws,
    ):
        ws.extract_archive(zip_path)


@pytest.mark.unit
def test_archive_size_limit_enforced(tmp_path: Path) -> None:
    """Archives exceeding maximum file size bounds must be rejected."""
    zip_path = tmp_path / "large.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("large_file.txt", "A" * 10_000)

    # Limit to 5 KB
    limits = IngestLimits(max_file_bytes=5_000)
    with (
        pytest.raises(IngestionError, match="Single file size exceeded"),
        EphemeralWorkspace(base_dir=tmp_path, limits=limits) as ws,
    ):
        ws.extract_archive(zip_path)
