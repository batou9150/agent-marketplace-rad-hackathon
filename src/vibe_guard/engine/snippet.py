"""Bounded context snippet extraction for findings (Constraint C2)."""

from pathlib import Path

from vibe_guard.engine.models import Snippet


def extract_bounded_snippet(
    file_path: Path,
    line: int,
    context_lines: int = 4,
    max_chars: int = 1500,
) -> Snippet | None:
    """Extract a small bounded window around a finding line without reading
    the entire file into memory.
    """
    if not file_path.is_file() or line < 1:
        return None

    try:
        start_line = max(1, line - context_lines)
        end_line = line + context_lines

        selected_lines: list[str] = []
        with open(file_path, encoding="utf-8", errors="replace") as f:
            for current_line_num, current_line in enumerate(f, start=1):
                if current_line_num > end_line:
                    break
                if current_line_num >= start_line:
                    selected_lines.append(current_line)

        if not selected_lines:
            return None

        content = "".join(selected_lines)
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... [truncated]"

        return Snippet(
            start_line=start_line,
            end_line=start_line + len(selected_lines) - 1,
            highlight_line=line,
            content=content,
        )
    except Exception:
        return None
