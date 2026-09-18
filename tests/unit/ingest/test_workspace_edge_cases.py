"""Unit tests covering edge cases and boundary limits for Ingestion EphemeralWorkspace."""

import subprocess
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe_guard.ingest.workspace import (
    EphemeralWorkspace,
    IngestionError,
    IngestLimits,
)


@pytest.mark.unit
def test_extract_archive_uninitialized_and_unsupported(tmp_path: Path) -> None:
    """extract_archive raises appropriate errors on uninitialized ws or bad archive."""
    ws = EphemeralWorkspace()
    # 1. Uninitialized workspace
    with pytest.raises(IngestionError, match="Ephemeral workspace is not initialized"):
        ws.extract_archive("dummy.zip")

    # 2. Non-existent file
    with ws, pytest.raises(IngestionError, match="Archive file not found"):
        ws.extract_archive(tmp_path / "does_not_exist.zip")

    # 3. Unsupported format
    unsupported_file = tmp_path / "app.rar"
    unsupported_file.write_text("dummy")
    with ws, pytest.raises(IngestionError, match="Unsupported archive format"):
        ws.extract_archive(unsupported_file)


@pytest.mark.unit
def test_extract_zip_file_and_byte_limits(tmp_path: Path) -> None:
    """Zip extraction enforces file count, single file size, and total uncompressed bytes."""
    limits = IngestLimits(max_files=2, max_file_bytes=100, max_total_bytes=150)
    ws = EphemeralWorkspace(limits=limits)

    # Max files exceeded
    zip_many = tmp_path / "many.zip"
    with zipfile.ZipFile(zip_many, "w") as zf:
        zf.writestr("f1.txt", "a")
        zf.writestr("f2.txt", "b")
        zf.writestr("f3.txt", "c")

    with ws, pytest.raises(IngestionError, match="Archive maximum file count exceeded"):
        ws.extract_archive(zip_many)

    # Single file size exceeded
    zip_big_file = tmp_path / "big_file.zip"
    with zipfile.ZipFile(zip_big_file, "w") as zf:
        zf.writestr("large.txt", "x" * 150)

    with ws, pytest.raises(IngestionError, match="Single file size exceeded limit"):
        ws.extract_archive(zip_big_file)

    # Total bytes exceeded
    zip_total_bytes = tmp_path / "total_bytes.zip"
    with zipfile.ZipFile(zip_total_bytes, "w") as zf:
        zf.writestr("f1.txt", "x" * 80)
        zf.writestr("f2.txt", "y" * 80)

    with ws, pytest.raises(IngestionError, match="Archive total uncompressed bytes exceeded limit"):
        ws.extract_archive(zip_total_bytes)

    # Corrupt zip file
    bad_zip = tmp_path / "corrupt.zip"
    bad_zip.write_bytes(b"not a valid zip file header")
    with ws, pytest.raises(IngestionError, match="Failed to extract zip archive"):
        ws.extract_archive(bad_zip)


@pytest.mark.unit
def test_extract_tar_limits_and_corrupt(tmp_path: Path) -> None:
    """Tar extraction enforces file count, total size, and handles corrupt archives."""
    limits = IngestLimits(max_files=2, max_file_bytes=200, max_total_bytes=100)
    ws = EphemeralWorkspace(limits=limits)

    # Max files exceeded
    tar_many = tmp_path / "many.tar"
    with tarfile.open(tar_many, "w") as tf:
        for name in ("a.txt", "b.txt", "c.txt"):
            data = b"content"
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            import io

            tf.addfile(ti, io.BytesIO(data))

    with ws, pytest.raises(IngestionError, match="Archive maximum file count exceeded"):
        ws.extract_archive(tar_many)

    # Total bytes exceeded
    tar_bytes = tmp_path / "bytes.tar"
    with tarfile.open(tar_bytes, "w") as tf:
        data = b"z" * 150
        ti = tarfile.TarInfo(name="big.txt")
        ti.size = len(data)
        import io

        tf.addfile(ti, io.BytesIO(data))

    with ws, pytest.raises(IngestionError, match="Archive maximum total bytes exceeded"):
        ws.extract_archive(tar_bytes)

    # Corrupt tar
    bad_tar = tmp_path / "corrupt.tar"
    bad_tar.write_bytes(b"corrupt tar bytes")
    with ws, pytest.raises(IngestionError, match="Failed to extract tar archive"):
        ws.extract_archive(bad_tar)


@pytest.mark.unit
def test_copy_directory_edge_cases(tmp_path: Path) -> None:
    """copy_directory enforces initialization, existence, and handles errors."""
    ws = EphemeralWorkspace()
    with pytest.raises(IngestionError, match="Ephemeral workspace is not initialized"):
        ws.copy_directory(tmp_path)

    with ws:
        # Non-existent source
        with pytest.raises(IngestionError, match="Source directory not found"):
            ws.copy_directory(tmp_path / "missing_dir")

        # Copy failure
        sample_src = tmp_path / "sample"
        sample_src.mkdir()
        (sample_src / "file.txt").write_text("hello")
        with (
            patch("shutil.copytree", side_effect=PermissionError("Denied")),
            pytest.raises(IngestionError, match="Failed to copy directory"),
        ):
            ws.copy_directory(sample_src)


@pytest.mark.unit
def test_enforce_directory_limits() -> None:
    """Directory limits enforce single file size, total bytes, and handle OSError during stat."""
    limits = IngestLimits(max_files=10, max_file_bytes=50, max_total_bytes=100)
    ws = EphemeralWorkspace(limits=limits)

    with ws:
        # Single file limit exceeded
        test_dir = ws.path / "test1"
        test_dir.mkdir()
        (test_dir / "large.bin").write_bytes(b"a" * 80)
        with pytest.raises(IngestionError, match="exceeds single file limit"):
            ws._enforce_directory_limits(test_dir)

        # Total size limit exceeded
        test_dir2 = ws.path / "test2"
        test_dir2.mkdir()
        (test_dir2 / "f1.bin").write_bytes(b"b" * 40)
        (test_dir2 / "f2.bin").write_bytes(b"b" * 40)
        (test_dir2 / "f3.bin").write_bytes(b"b" * 40)
        with pytest.raises(IngestionError, match="Workspace exceeds total size limit"):
            ws._enforce_directory_limits(test_dir2)

        # Max files exceeded
        limits_files = IngestLimits(max_files=2)
        ws_files = EphemeralWorkspace(limits=limits_files)
        with ws_files:
            test_dir3 = ws_files.path / "test3"
            test_dir3.mkdir()
            for i in range(3):
                (test_dir3 / f"f{i}.txt").write_text("x")
            with pytest.raises(IngestionError, match="Directory exceeds maximum file count limit"):
                ws_files._enforce_directory_limits(test_dir3)

        # OSError during stat should be ignored gracefully
        test_dir4 = ws.path / "test4"
        test_dir4.mkdir()
        (test_dir4 / "sample.txt").write_text("data")
        with patch("pathlib.Path.stat", side_effect=OSError("Disk error")):
            # Should not raise IngestionError
            ws._enforce_directory_limits(test_dir4)


@pytest.mark.unit
def test_clone_git_retry_fallback_and_timeouts() -> None:
    """clone_git handles branch retry fallback, timeouts, and execution errors."""
    ws = EphemeralWorkspace()
    with ws:
        # 1. Branch fallback success
        mock_run = MagicMock()
        first_call = MagicMock(returncode=128, stderr="Remote branch custom-branch not found")
        second_call = MagicMock(returncode=0, stderr="")
        mock_run.side_effect = [first_call, second_call]

        with (
            patch("subprocess.run", mock_run),
            patch("vibe_guard.ingest.workspace.EphemeralWorkspace._enforce_directory_limits"),
        ):
            dest = ws.clone_git(
                git_url="https://github.com/org/repo.git",
                branch="custom-branch",
            )
            assert dest == ws.path / "repo"
            assert mock_run.call_count == 2

        # 2. TimeoutExpired
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
            ),
            pytest.raises(IngestionError, match="Git clone timed out after"),
        ):
            ws.clone_git("https://github.com/org/repo.git")

        # 3. Generic Exception during git clone
        with (
            patch("subprocess.run", side_effect=RuntimeError("Subprocess failed")),
            pytest.raises(IngestionError, match="Error during git clone"),
        ):
            ws.clone_git("https://github.com/org/repo.git")
