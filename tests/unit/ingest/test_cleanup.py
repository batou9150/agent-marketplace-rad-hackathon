"""Tests for ephemeral workspace lifecycle and guaranteed purge (Constraint C2)."""

from pathlib import Path

import pytest

from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError, IngestLimits


@pytest.mark.unit
def test_workspace_purged_on_normal_exit(tmp_path: Path) -> None:
    """Workspace directory must not exist after context manager normal exit."""
    workspace_path: Path | None = None
    with EphemeralWorkspace(base_dir=tmp_path) as ws:
        workspace_path = ws.path
        assert workspace_path.is_dir()
        (workspace_path / "dummy.txt").write_text("sensible code")
        assert (workspace_path / "dummy.txt").is_file()

    assert workspace_path is not None
    assert not workspace_path.exists(), "Ephemeral directory must be purged on exit"


@pytest.mark.unit
def test_workspace_purged_on_exception(tmp_path: Path) -> None:
    """Workspace directory must be purged even if an unhandled exception occurs."""
    workspace_path: Path | None = None
    with (
        pytest.raises(RuntimeError, match="Scan crashed"),
        EphemeralWorkspace(base_dir=tmp_path) as ws,
    ):
        workspace_path = ws.path
        assert workspace_path.is_dir()
        (workspace_path / "leaked.txt").write_text("confidential")
        raise RuntimeError("Scan crashed")

    assert workspace_path is not None
    assert not workspace_path.exists(), "Ephemeral directory must be purged even on exception"


@pytest.mark.unit
def test_archive_extraction_limits_exceeded(tmp_path: Path) -> None:
    """Exceeding file count or byte limits must raise IngestionError and clean up."""
    import zipfile

    archive_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for i in range(10):
            zf.writestr(f"file_{i}.txt", "x" * 1024)

    # Restrict limit to 5 files maximum
    strict_limits = IngestLimits(max_files=5, max_total_bytes=100_000)
    with (
        pytest.raises(IngestionError, match="maximum file count exceeded"),
        EphemeralWorkspace(base_dir=tmp_path, limits=strict_limits) as ws,
    ):
        ws.extract_archive(archive_path)


@pytest.mark.unit
def test_zip_slip_protection(tmp_path: Path) -> None:
    """Archive attempting to extract files outside target directory must be rejected."""
    import zipfile

    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../evil.txt", "exploit")

    with (
        pytest.raises(IngestionError, match="Path traversal detected"),
        EphemeralWorkspace(base_dir=tmp_path) as ws,
    ):
        ws.extract_archive(malicious_zip)
