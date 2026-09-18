"""Unit tests for workspace ingestion security (SPEC-ING-4, SPEC-ING-5, SPEC-ING-6, SPEC-ING-7)."""

import stat
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError


@pytest.mark.unit
def test_spec_ing_4_path_traversal_sibling_rejected(tmp_path: Path) -> None:
    """SPEC-ING-4: Path traversal must be checked with Path.is_relative_to,

    rejecting tricky prefixes like /tmp/ws-evil against /tmp/ws.
    """
    with EphemeralWorkspace(base_dir=tmp_path) as ws:
        # Create a malicious zip targeting a sibling directory
        sibling_zip = tmp_path / "sibling_attack.zip"
        with zipfile.ZipFile(sibling_zip, "w") as zf:
            # Entry named "../ws_sibling/pwn.txt"
            zf.writestr("../ws_sibling/pwn.txt", "malicious payload")

        with pytest.raises(IngestionError, match="Path traversal detected"):
            ws.extract_archive(sibling_zip)


@pytest.mark.unit
def test_spec_ing_5_zip_symlink_rejected(tmp_path: Path) -> None:
    """SPEC-ING-5: Zip archives containing symlinks must be rejected."""
    zip_path = tmp_path / "symlink.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zip_info = zipfile.ZipInfo("symlink_entry")
        # Set Unix symlink attribute
        zip_info.create_system = 3  # Unix
        zip_info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(zip_info, "/etc/passwd")

    with (
        EphemeralWorkspace(base_dir=tmp_path) as ws,
        pytest.raises(IngestionError, match="Disallowed archive entry"),
    ):
        ws.extract_archive(zip_path)


@pytest.mark.unit
def test_spec_ing_5_tar_symlink_rejected(tmp_path: Path) -> None:
    """SPEC-ING-5: Tar archives containing symlinks or hardlinks must be rejected."""
    tar_path = tmp_path / "symlink.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo("symlink_entry")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/passwd"
        tf.addfile(ti)

    with (
        EphemeralWorkspace(base_dir=tmp_path) as ws,
        pytest.raises(IngestionError, match="Disallowed archive entry"),
    ):
        ws.extract_archive(tar_path)


@pytest.mark.unit
def test_spec_ing_5_tar_hardlink_rejected(tmp_path: Path) -> None:
    """SPEC-ING-5: Tar archives containing hardlinks must be rejected."""
    tar_path = tmp_path / "hardlink.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo("hardlink_entry")
        ti.type = tarfile.LNKTYPE
        ti.linkname = "target_file"
        tf.addfile(ti)

    with (
        EphemeralWorkspace(base_dir=tmp_path) as ws,
        pytest.raises(IngestionError, match="Disallowed archive entry"),
    ):
        ws.extract_archive(tar_path)


@pytest.mark.unit
def test_spec_ing_7_git_clone_token_not_in_argv_or_url(tmp_path: Path) -> None:
    """SPEC-ING-7: Access token must NEVER appear in argv, git URL, or error messages."""
    token = "ghp_secret_access_token_123456789"
    repo_url = "https://github.com/example-org/sample-repo.git"

    with EphemeralWorkspace(base_dir=tmp_path) as ws, patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        ws.clone_git(repo_url, token=token)

        assert mock_run.called
        called_cmd = mock_run.call_args[0][0]

        # Token must NOT be in any argument
        for arg in called_cmd:
            assert token not in arg, f"Token leaked in argv argument: {arg}"

        # Remote URL in argv must be the clean repo_url
        assert repo_url in called_cmd


@pytest.mark.unit
def test_spec_ing_7_git_clone_error_masks_token(tmp_path: Path) -> None:
    """SPEC-ING-7: Errors during git clone must mask any token in stderr/error."""
    token = "ghp_secret_access_token_987654321"
    repo_url = "https://github.com/example-org/sample-repo.git"

    with EphemeralWorkspace(base_dir=tmp_path) as ws, patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout="",
            stderr=f"fatal: Authentication failed for 'https://{token}@github.com'",
        )

        with pytest.raises(IngestionError) as exc_info:
            ws.clone_git(repo_url, token=token)

        err_msg = str(exc_info.value)
        assert token not in err_msg
        assert "***" in err_msg


@pytest.mark.unit
def test_spec_ing_6_git_clone_hardened_flags(tmp_path: Path) -> None:
    """SPEC-ING-6: Git clone must enforce non-interactive & non-recursive execution."""
    repo_url = "https://github.com/example-org/sample-repo.git"

    with EphemeralWorkspace(base_dir=tmp_path) as ws, patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        ws.clone_git(repo_url)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        env = mock_run.call_args[1].get("env", {})

        assert "--no-recurse-submodules" in cmd
        assert "-c" in cmd
        assert "core.hooksPath=" in cmd
        assert "protocol.allow=never" in cmd
        assert "protocol.https.allow=always" in cmd
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
