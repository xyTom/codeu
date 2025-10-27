from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import re

# LangChain's tool decorator (preferred). If unavailable, provide a no-op fallback.
try:
    from langchain.tools import tool  # type: ignore
except Exception:  # pragma: no cover
    def tool(name: str, parse_docstring: bool = False):
        def _decorator(fn):
            return fn
        return _decorator

_PROJECT_ROOT: Optional[Path] = None


def _get_project_root() -> Path:
    """Detect project root by locating `pyproject.toml` upwards from this file.

    Fallback to the current working directory if not found.
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            _PROJECT_ROOT = parent
            return _PROJECT_ROOT

    _PROJECT_ROOT = Path.cwd()
    return _PROJECT_ROOT


def _resolve_path(file_path: str) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve a user-provided path to an absolute path within the project root.

    Returns (path, error). If error is not None, the path is invalid.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return None, "Error: file_path must be a non-empty string."

    root = _get_project_root()
    p = Path(file_path)
    abs_path = (root / p).resolve() if not p.is_absolute() else p.resolve()

    # Restrict edits to within project root for safety
    try:
        abs_path.relative_to(root)
    except Exception:
        return None, f"Error: file_path '{abs_path}' is outside the project root '{root}'."

    if not abs_path.exists():
        return None, f"Error: file not found: {abs_path}"
    if not abs_path.is_file():
        return None, f"Error: not a file: {abs_path}"

    return abs_path, None


def _is_probably_binary(path: Path) -> bool:
    """Heuristic: consider a file binary if its initial bytes contain NUL."""
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        # If the file can't be read as bytes, treat it as text and let open() raise
        return False


@tool("text_view", parse_docstring=False)
def text_view(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    max_characters: Optional[int] = None,
    encoding: str = "utf-8",
):
    """
    View text content of a file with optional line range and character truncation.

    Use this tool to:
    - Inspect a file's contents for debugging and code review
    - Read a specific line range (1-based inclusive)
    - Limit the returned content length via `max_characters`

    Args:
        file_path: Absolute or project-root-relative path to the file.
        start_line: Optional 1-based line number to start reading from.
        end_line: Optional 1-based line number to end reading at (inclusive).
        max_characters: Optional maximum number of characters to return; if exceeded, content is truncated.
        encoding: Text encoding, default "utf-8".
    """
    path, err = _resolve_path(file_path)
    if err:
        return err
    assert path is not None

    if _is_probably_binary(path):
        return f"Error: file appears to be binary and cannot be viewed as text: {path}"

    # Validate line range
    if start_line is not None and start_line <= 0:
        return "Error: start_line must be a positive integer if provided."
    if end_line is not None and end_line <= 0:
        return "Error: end_line must be a positive integer if provided."
    if start_line is not None and end_line is not None and end_line < start_line:
        return "Error: end_line must be greater than or equal to start_line."

    try:
        with path.open("r", encoding=encoding) as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return f"Error: unable to decode file with encoding '{encoding}': {path}"
    except OSError as e:
        return f"Error: failed to read file: {path}\n{e}"

    total_lines = len(lines)
    s = start_line if start_line is not None else 1
    e = end_line if end_line is not None else total_lines
    s = max(1, s)
    e = min(total_lines, e)

    # Extract selected range
    selected = "".join(lines[s - 1 : e])

    # Apply truncation if needed
    truncated = False
    if isinstance(max_characters, int) and max_characters >= 0:
        if len(selected) > max_characters:
            selected = selected[:max_characters]
            truncated = True

    header = [
        f"Path: {path}",
        f"Lines: {s}-{e} (total {total_lines})",
    ]
    if truncated:
        header.append("Note: content truncated due to max_characters limit.")

    return "\n".join(header + ["", selected])


@tool("str_replace_edit", parse_docstring=False)
def str_replace_edit(
    file_path: str,
    old_str: str,
    new_str: str,
    occurrence_index: int = 0,
    encoding: str = "utf-8",
):
    """
    Perform a single string-replace edit inside a text file and save.

    This is a search/replace edit that:
    - Searches for the exact `old_str` in the file content
    - Replaces only one occurrence: the `occurrence_index`-th (0-based)
    - Writes the modified content back to disk

    Safety & constraints:
    - Only operates on files within the project root
    - Refuses to edit binary files
    - If `old_str` is empty: allowed only when the target file is empty; in that case the function writes `new_str` as the entire content
    - If `old_str` is not found, returns an error and does not modify the file

    Args:
        file_path: Absolute or project-root-relative path to the file.
        old_str: The exact contiguous text to search for.
        new_str: The replacement text; can be empty to delete the segment.
        occurrence_index: 0-based index of which occurrence to replace (default first occurrence).
        encoding: Text encoding, default "utf-8".
    """
    # Validate inputs
    if not isinstance(old_str, str):
        return "Error: old_str must be a string."
    if not isinstance(new_str, str):
        return "Error: new_str must be a string."
    if not isinstance(occurrence_index, int) or occurrence_index < 0:
        return "Error: occurrence_index must be a non-negative integer."

    path, err = _resolve_path(file_path)
    if err:
        return err
    assert path is not None

    if _is_probably_binary(path):
        return f"Error: file appears to be binary and cannot be edited as text: {path}"

    try:
        original = path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return f"Error: unable to decode file with encoding '{encoding}': {path}"
    except OSError as e:
        return f"Error: failed to read file: {path}\n{e}"

    # Special case: allow empty old_str only when file is empty
    if old_str == "":
        if len(original) == 0:
            edited = new_str
            try:
                path.write_text(edited, encoding=encoding)
            except OSError as e:
                return f"Error: failed to write file: {path}\n{e}"

            delta = len(new_str)  # from 0 to len(new_str)
            summary = [
                f"Path: {path}",
                "Inserted into empty file (no search performed)",
                f"Delta size: {delta:+d} chars",
                f"New file size: {len(edited)} chars",
            ]

            # Show a small context snippet around the new content
            context_radius = 120
            snippet_end = min(len(edited), len(new_str) + context_radius)
            snippet = edited[:snippet_end]

            summary.append("")
            summary.append("Snippet around edit:")
            summary.append("" + snippet)

            return "\n".join(summary)
        else:
            return "Error: old_str empty is only allowed when the file is empty; use a non-empty old_str or a full-file write tool."

    # Find all occurrences of old_str
    matches = [m for m in re.finditer(re.escape(old_str), original)]
    if not matches:
        return "Error: old_str not found in file; no changes applied."
    if occurrence_index >= len(matches):
        return f"Error: occurrence_index {occurrence_index} out of range; found {len(matches)} occurrence(s)."

    target = matches[occurrence_index]
    start, end = target.span()

    edited = original[:start] + new_str + original[end:]

    try:
        path.write_text(edited, encoding=encoding)
    except OSError as e:
        return f"Error: failed to write file: {path}\n{e}"

    delta = len(new_str) - len(old_str)
    summary = [
        f"Path: {path}",
        f"Replaced occurrence #{occurrence_index} (chars {start}-{end})",
        f"Delta size: {delta:+d} chars",
        f"New file size: {len(edited)} chars",
    ]

    # Show a small context snippet around the edit (for verification)
    context_radius = 120
    snippet_start = max(0, start - context_radius)
    snippet_end = min(len(edited), start + len(new_str) + context_radius)
    snippet = edited[snippet_start:snippet_end]

    summary.append("")
    summary.append("Snippet around edit:")
    summary.append("" + snippet)

    return "\n".join(summary)


@tool("str_replace_editor", parse_docstring=False)
def str_replace_editor(
    file_path: str,
    old_str: str,
    new_str: str,
    occurrence_index: int = 0,
    encoding: str = "utf-8",
):
    """Compatibility alias for Sonnet 3.7 naming; delegates to str_replace_edit."""
    return str_replace_edit(
        file_path=file_path,
        old_str=old_str,
        new_str=new_str,
        occurrence_index=occurrence_index,
        encoding=encoding,
    )

@tool("str_replace_based_edit_tool", parse_docstring=False)
def str_replace_based_edit_tool(
    file_path: str,
    old_str: str,
    new_str: str,
    occurrence_index: int = 0,
    encoding: str = "utf-8",
):
    """Compatibility alias for Anthropic-style naming; delegates to str_replace_edit.

    Args mirror `str_replace_edit`.
    """
    return str_replace_edit(
        file_path=file_path,
        old_str=old_str,
        new_str=new_str,
        occurrence_index=occurrence_index,
        encoding=encoding,
    )