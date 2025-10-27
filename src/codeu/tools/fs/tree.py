from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union
from fnmatch import fnmatch


@dataclass(frozen=True)
class TreeEntry:
    """Structured representation of a tree traversal entry.

    Attributes:
        path: The item path (absolute or relative depending on `absolute_paths`).
        name: Base name of the file or directory (without parent path).
        is_dir: Whether the entry is a directory.
        depth: The item's depth relative to the root (root is 0).
    """
    path: Path
    name: str
    is_dir: bool
    depth: int


def tree(
    root: Union[str, Path],
    *,
    max_depth: int = 3,
    patterns: Optional[Union[str, Sequence[str]]] = None,
    include_files: bool = True,
    include_dirs: bool = True,
    absolute_paths: bool = False,
) -> List[TreeEntry]:
    """Recursively list descendant files and directories (tree-style), supporting max depth and glob-like filtering.

    This function performs a depth-first traversal starting at `root` and returns structured information for each matched
    file or directory. The maximum recursion depth can be controlled via `max_depth` (root depth is 0). To avoid excessive
    traversal in large repositories, `max_depth` must be in the range [1, 3]. Glob-like filtering via `patterns` follows
    the same rules as `ls`, but since this function is recursive, patterns like "**/*.py" are effective.

    Args:
        root: Target root directory path (`str` or `pathlib.Path`).
        max_depth: Maximum recursion depth (root is 0). Valid range is 1–3. If set to 1, only direct children of root are traversed.
        patterns: Glob-like pattern string or sequence of strings; `None` means no filtering.
        include_files: Whether to include files in results.
        include_dirs: Whether to include directories in results.
        absolute_paths: Whether to return absolute paths.

    Returns:
        A list of `TreeEntry` items in traversal order, each with depth information.

    Raises:
        FileNotFoundError: When `root` does not exist.
        NotADirectoryError: When `root` exists but is not a directory.
        ValueError: When `max_depth` is not in [1, 3], or both `include_files` and `include_dirs` are `False`.

    Examples:
        List two levels (including both files and directories):
            >>> tree(".", max_depth=2)
        Only list directories, with maximum depth 3:
            >>> tree(".", max_depth=3, include_files=False, include_dirs=True)
        Recursively match all Python files and return absolute paths:
            >>> tree(".", max_depth=3, patterns="**/*.py", absolute_paths=True)
    """
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    if not (1 <= max_depth <= 3):
        raise ValueError("max_depth must be in the range [1, 3]")
    if not include_files and not include_dirs:
        raise ValueError("At least one of include_files or include_dirs must be True.")

    # Normalize patterns to a list
    if patterns is None:
        pattern_list: Optional[List[str]] = None
    elif isinstance(patterns, str):
        pattern_list = [patterns]
    else:
        pattern_list = list(patterns)

    results: List[TreeEntry] = []

    def should_include(rel_posix: str, is_dir: bool) -> bool:
        if (is_dir and not include_dirs) or (not is_dir and not include_files):
            return False
        if pattern_list is None:
            return True
        # Match relative POSIX-style path against any pattern
        return any(fnmatch(rel_posix, pat) for pat in pattern_list)

    def dfs(current: Path, current_depth: int) -> None:
        # Traverse children only if we haven't exceeded max_depth
        if current_depth >= max_depth:
            return
        try:
            for entry in current.iterdir():
                is_dir = entry.is_dir()
                rel = entry.relative_to(root_path)
                rel_str = rel.as_posix()

                if should_include(rel_str, is_dir):
                    out_path = entry if absolute_paths else rel
                    results.append(
                        TreeEntry(
                            path=out_path,
                            name=entry.name,
                            is_dir=is_dir,
                            depth=len(rel.parts),  # depth relative to root; direct children are 1
                        )
                    )

                # Continue traversal into directories regardless of include_dirs, to reach nested files
                if is_dir:
                    dfs(entry, len(rel.parts))
        except PermissionError:
            # Skip directories without permission
            return

    # Start DFS from root (depth 0)
    dfs(root_path, 0)

    return results