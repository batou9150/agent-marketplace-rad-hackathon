"""Tests for snippet extraction and bounding (Constraint C2)."""

from pathlib import Path

import pytest

from vibe_guard.engine.models import Finding
from vibe_guard.engine.snippet import extract_bounded_snippet


@pytest.mark.unit
def test_extract_snippet_bounds(tmp_path: Path) -> None:
    """Snippet should only include lines within window and respect max_chars."""
    test_file = tmp_path / "long_code.py"
    lines = [f"# Line {i}: " + ("x" * 50) for i in range(1, 101)]
    test_file.write_text("\n".join(lines))

    snippet = extract_bounded_snippet(test_file, line=50, context_lines=3, max_chars=1000)
    assert snippet is not None
    assert snippet.highlight_line == 50
    assert snippet.start_line == 47
    assert snippet.end_line == 53
    assert len(snippet.content) <= 1000
    assert "Line 50:" in snippet.content
    assert "Line 1:" not in snippet.content
    assert "Line 100:" not in snippet.content


@pytest.mark.unit
def test_extract_snippet_missing_file(tmp_path: Path) -> None:
    """Non-existent file should gracefully return None without crashing."""
    snippet = extract_bounded_snippet(tmp_path / "missing.py", line=10)
    assert snippet is None


@pytest.mark.unit
def test_tool_error_finding() -> None:
    """Tool error finding should be identifiable and have proper defaults."""
    finding = Finding.create_tool_error(
        tool_name="semgrep",
        error_message="Semgrep binary crashed with status 139",
    )
    assert finding.is_tool_error
    assert finding.rule_id == "TOOL-ERR-SEMGREP"
    assert finding.severity == "high"
    assert "Semgrep binary crashed" in finding.message
