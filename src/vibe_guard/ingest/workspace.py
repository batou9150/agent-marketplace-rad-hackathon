"""Ephemeral workspace management, archive extraction, and Git cloning with C2 bounds."""

import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class IngestLimits:
    """Security and resource limits for scanned repositories."""

    max_files: int = 5_000
    max_total_bytes: int = 50 * 1024 * 1024  # 50 MB
    max_file_bytes: int = 5 * 1024 * 1024  # 5 MB


class IngestionError(Exception):
    """Raised when repository cloning or archive extraction fails or exceeds bounds."""


class EphemeralWorkspace:
    """Context manager creating a temporary scan workspace strictly purged on exit."""

    def __init__(
        self,
        base_dir: Path | str | None = None,
        limits: IngestLimits | None = None,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else None
        self.limits = limits or IngestLimits()
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self.path: Path | None = None

    def __enter__(self) -> Self:
        self._temp_dir = tempfile.TemporaryDirectory(
            prefix="vibeguard_scan_",
            dir=self.base_dir,
        )
        self.path = Path(self._temp_dir.name).resolve()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Guaranteed purge in finally block according to Constraint C2."""
        try:
            if self._temp_dir:
                self._temp_dir.cleanup()
        except Exception:
            pass
        finally:
            if self.path and self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)

    def extract_archive(self, archive_path: Path | str) -> Path:
        """Extract a .zip or tarball into the ephemeral workspace with zip-slip and size checks."""
        if not self.path or not self.path.is_dir():
            raise IngestionError("Ephemeral workspace is not initialized")

        archive = Path(archive_path)
        if not archive.is_file():
            raise IngestionError(f"Archive file not found: {archive}")

        if archive.name.endswith((".zip", ".ZIP")):
            self._extract_zip(archive)
        elif archive.name.endswith((".tar.gz", ".tgz", ".tar")):
            self._extract_tar(archive)
        else:
            raise IngestionError(f"Unsupported archive format: {archive.name}")

        self._enforce_directory_limits(self.path)
        return self.path

    def _extract_zip(self, archive: Path) -> None:
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                total_bytes = 0
                for file_count, info in enumerate(zf.infolist(), start=1):
                    if file_count > self.limits.max_files:
                        raise IngestionError(
                            f"Archive maximum file count exceeded ({self.limits.max_files})"
                        )
                    total_bytes += info.file_size
                    if total_bytes > self.limits.max_total_bytes:
                        limit_mb = self.limits.max_total_bytes // (1024 * 1024)
                        raise IngestionError(
                            f"Archive total uncompressed bytes exceeded limit ({limit_mb} MB)"
                        )
                    if info.file_size > self.limits.max_file_bytes:
                        raise IngestionError(f"Single file size exceeded limit for {info.filename}")

                    # SPEC-ING-4: Zip-Slip path traversal check using Path.is_relative_to
                    target_file = (self.path / info.filename).resolve()
                    if not target_file.is_relative_to(self.path):
                        raise IngestionError(f"Path traversal detected in archive: {info.filename}")

                    # SPEC-ING-5: Reject symlinks and non-regular files
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise IngestionError(
                            f"Disallowed archive entry (symbolic link): {info.filename}"
                        )
                    if mode != 0 and not (info.is_dir() or stat.S_ISREG(mode)):
                        raise IngestionError(
                            f"Disallowed archive entry (unsupported type): {info.filename}"
                        )

                zf.extractall(self.path)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"Failed to extract zip archive: {exc}") from exc

    def _extract_tar(self, archive: Path) -> None:
        try:
            with tarfile.open(archive, "r:*") as tf:
                total_bytes = 0
                for file_count, member in enumerate(tf.getmembers(), start=1):
                    if file_count > self.limits.max_files:
                        raise IngestionError("Archive maximum file count exceeded")
                    total_bytes += member.size
                    if total_bytes > self.limits.max_total_bytes:
                        raise IngestionError("Archive maximum total bytes exceeded")

                    # SPEC-ING-4: Path traversal check using Path.is_relative_to
                    target_file = (self.path / member.name).resolve()
                    if not target_file.is_relative_to(self.path):
                        raise IngestionError(
                            f"Path traversal detected in tar archive: {member.name}"
                        )

                    # SPEC-ING-5: Reject links, devices, and fifos
                    if member.issym() or member.islnk():
                        raise IngestionError(f"Disallowed archive entry (link): {member.name}")
                    if member.ischr() or member.isblk() or member.isfifo():
                        raise IngestionError(
                            f"Disallowed archive entry (device/fifo): {member.name}"
                        )
                    if not (member.isfile() or member.isdir()):
                        raise IngestionError(
                            f"Disallowed archive entry (unsupported type): {member.name}"
                        )

                if hasattr(tarfile, "data_filter"):
                    tf.extractall(self.path, filter="data")
                else:
                    tf.extractall(self.path)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"Failed to extract tar archive: {exc}") from exc

    def clone_git(
        self,
        git_url: str,
        branch: str | None = None,
        token: str | None = None,
    ) -> Path:
        """Shallow clone a remote git repository into the ephemeral directory."""
        if not self.path or not self.path.is_dir():
            raise IngestionError("Ephemeral workspace is not initialized")

        # SPEC-ING-6 & SPEC-ING-7: Hardened non-interactive, non-recursive Git clone
        git_bin = os.environ.get("VIBE_GUARD_GIT_BIN") or shutil.which("git") or "git"
        cmd = [
            git_bin,
            "-c",
            "core.hooksPath=",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "clone",
            "--depth",
            "1",
            "--no-recurse-submodules",
        ]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([git_url, str(self.path / "repo")])

        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        askpass_script: Path | None = None
        if token:
            askpass_script = self.path / ".askpass.sh"
            askpass_script.write_text(f'#!/bin/sh\necho "{token}"\n')
            askpass_script.chmod(0o700)
            env["GIT_ASKPASS"] = str(askpass_script)

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                # Mask token in error message
                err_msg = result.stderr.replace(token, "***") if token else result.stderr
                raise IngestionError(f"Git clone failed: {err_msg.strip()}")
        except subprocess.TimeoutExpired as exc:
            raise IngestionError("Git clone timed out after 120s") from exc
        except Exception as exc:
            raise IngestionError(f"Error during git clone: {exc}") from exc
        finally:
            if askpass_script:
                askpass_script.unlink(missing_ok=True)

        clone_dest = self.path / "repo"
        self._enforce_directory_limits(clone_dest)
        return clone_dest

    def _enforce_directory_limits(self, directory: Path) -> None:
        """Verify file count and total size within the directory."""
        file_count = 0
        total_bytes = 0

        for root, _, files in os.walk(directory):
            for file_name in files:
                file_count += 1
                if file_count > self.limits.max_files:
                    raise IngestionError(
                        f"Directory exceeds maximum file count limit ({self.limits.max_files})"
                    )

                file_path = Path(root) / file_name
                try:
                    size = file_path.stat().st_size
                    total_bytes += size
                    if size > self.limits.max_file_bytes:
                        limit_mb = self.limits.max_file_bytes // (1024 * 1024)
                        raise IngestionError(
                            f"File {file_name} exceeds single file limit ({limit_mb} MB)"
                        )
                    if total_bytes > self.limits.max_total_bytes:
                        total_limit_mb = self.limits.max_total_bytes // (1024 * 1024)
                        raise IngestionError(
                            f"Workspace exceeds total size limit ({total_limit_mb} MB)"
                        )
                except OSError:
                    continue
