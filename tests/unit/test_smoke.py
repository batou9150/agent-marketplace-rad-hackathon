"""Smoke test to validate the bootstrap setup (Gate 0)."""

import pytest

import vibe_guard


@pytest.mark.unit
def test_package_version() -> None:
    """Verify that vibe_guard package version is exposed."""
    assert vibe_guard.__version__ == "0.1.0"
