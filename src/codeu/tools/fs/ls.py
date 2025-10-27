from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union
from fnmatch import fnmatch


@dataclass(frozen=True)
class DirEntry:
    """Structured representation of a directory entry.

    Attributes:
        path: The entry path (absolute or relative depending on `absolute_paths`).
        name: Base name of the file or directory (without parent path).
        is_dir: Whether the entry is a directory.
    """
    path: Path
    name: str
    is_dir: bool


def ls(
    directory: Union[str, Path],
    patterns: Optional[Union[str, Sequence[str]]] = None,
    *,
    include_files: bool = True,
    include_dirs: bool = True,
    absolute_paths: bool = False,
) -> List[DirEntry]:
    """List direct children (non-recursive) of the given directory, with glob-like filtering.

    This function lists only one level of children (no recursion). If `patterns` is provided,
    glob-like patterns (e.g. "*.py", "**/*.md", "foo?", etc.) are applied to filter results.
    By default both files and directories are returned and can be controlled with `include_files`
    and `include_dirs`.

    Notes:
    - Patterns are evaluated relative to `directory` using POSIX-style paths.
    - When `absolute_paths=True`, returned paths are absolute; otherwise they are relative to `directory`.
    - Symlinks are returned as normal entries; recursion does not apply in this function.

    Args:
        directory: Target directory path (`str` or `pathlib.Path`).
        patterns: Glob-like pattern string or sequence of strings; `None` means no filtering.
            Examples:
            - Single pattern: "*.py"
            - Multiple patterns: ["*.py", "*.md"]
            - The double-star pattern is only used to match path fragments; since this function
              is non-recursive, patterns like "**/*.py" typically won't match direct children.
        include_files: Whether to include files in results.
        include_dirs: Whether to include directories in results.
        absolute_paths: Whether to return absolute paths.

    Returns:
        A list of `DirEntry` objects, each representing a matched child entry.

    Raises:
        FileNotFoundError: If `directory` does not exist.
        NotADirectoryError: If `directory` exists but is not a directory.
        ValueError: If both `include_files` and `include_dirs` are set to `False`.

    Examples:
        List all children in the current directory:
            >>> ls(".")
        List only files ending with `.py`:
            >>> ls(".", patterns="*.py", include_dirs=False)
        Match multiple extensions and return absolute paths:
            >>> ls(".", patterns=["*.py", "*.md"], absolute_paths=True)
    """
    root = Path(directory)
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    if not include_files and not include_dirs:
        raise ValueError("At least one of include_files or include_dirs must be True.")

    # Normalize patterns to a list
    pattern_list: Optional[List[str]]
    if patterns is None:
        pattern_list = None
    elif isinstance(patterns, str):
        pattern_list = [patterns]
    else:
        pattern_list = list(patterns)

    results: List[DirEntry] = []

    for entry in root.iterdir():
        is_dir = entry.is_dir()
        if (is_dir and not include_dirs) or (not is_dir and not include_files):
            continue

        rel = entry.relative_to(root)
        rel_str = rel.as_posix()

        if pattern_list is not None:
            # Match against the relative posix path
            if not any(fnmatch(rel_str, pat) for pat in pattern_list):
                continue

        path_out = entry if absolute_paths else rel
        results.append(DirEntry(path=path_out, name=entry.name, is_dir=is_dir))

    return results