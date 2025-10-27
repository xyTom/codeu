from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union
import re


@dataclass(frozen=True)
class GrepMatch:
    """Structured representation of a text match.

    Attributes:
        file_path: Path of the file where the match occurred.
        line_number: 1-based line number containing the match.
        line_text: The original text of the matched line.
        spans: Positions of all match segments within the line as (start, end) half-open intervals, where end is exclusive.
    """
    file_path: Path
    line_number: int
    line_text: str
    spans: Tuple[Tuple[int, int], ...]


def grep(
    root: Union[str, Path],
    query: Union[str, re.Pattern[str]],
    *,
    glob: Optional[Union[str, Sequence[str]]] = None,
    case_sensitive: bool = True,
    use_regex: bool = False,
    include_binary: bool = False,
    encoding: str = "utf-8",
    max_matches: Optional[int] = None,
) -> List[GrepMatch]:
    """Search for matching text in code files, similar to the OS `grep`.

    Supports matching via plain strings or regular expressions, and allows limiting the searched files using glob patterns.
    Matching is case-sensitive by default, and can be toggled via `case_sensitive` for plain string matching.
    To avoid misreading binary files, they are excluded by default but can be included via `include_binary`.
    To improve performance and stability, `max_matches` can cap the total number of occurrences returned.

    Matching behavior:
    - When `use_regex=False` and `query` is a string, performs plain substring matching (respecting `case_sensitive`).
    - When `use_regex=True`, `query` may be a regex string or a precompiled `re.Pattern`; regex matching is used
      (the `case_sensitive` flag is ignored; callers should compile the regex with flags such as `re.IGNORECASE` as needed).
    - Returns the file path, line number, line text, and all match spans within that line for each matched line.

    File scope:
    - `glob` limits which files to search (paths are relative to `root`), e.g., "**/*.py" or ["**/*.py", "**/*.md"].
    - If `glob` is `None`, all files under `root` are searched recursively; binary files are still excluded unless
      `include_binary=True`.

    Args:
        root: The root directory to search within.
        query: The query to match. Can be a plain string or `re.Pattern[str]`.
        glob: Glob pattern(s) restricting the files to search (string or sequence of strings).
        case_sensitive: Whether plain-string matching is case-sensitive (ignored for regex matching).
        use_regex: Whether to use regular expression matching.
        include_binary: Whether to include binary files (excluded by default).
        encoding: The text decoding encoding (default "utf-8").
        max_matches: The maximum number of total match occurrences to return; `None` means no limit.

    Returns:
        A list of `GrepMatch` objects, each representing one matched line and all its match spans.

    Raises:
        FileNotFoundError: If `root` does not exist.
        NotADirectoryError: If `root` exists but is not a directory.
        re.error: If an invalid regular expression is provided when `use_regex=True` and `query` is a string.
        UnicodeDecodeError: If a file cannot be decoded with the specified `encoding`.
        ValueError: If `max_matches` is negative.

    Examples:
        Search for lines containing "TODO" (case-sensitive):
            >>> grep(".", "TODO", glob="**/*.py")
        Case-insensitive plain substring search:
            >>> grep(".", "fixme", glob=["**/*.py", "**/*.md"], case_sensitive=False)
        Use regex to find function definitions:
            >>> pattern = re.compile(r"^def\s+\w+\(", re.MULTILINE)
            >>> grep(".", pattern, glob="**/*.py", use_regex=True)
    """
    # Validate root
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    # Validate limits
    if max_matches is not None and max_matches < 0:
        raise ValueError("max_matches must be non-negative or None")

    # Normalize glob patterns to a list
    if glob is None:
        pattern_list: Optional[List[str]] = None
    elif isinstance(glob, str):
        pattern_list = [glob]
    else:
        pattern_list = list(glob)

    # Prepare regex pattern if requested
    regex: Optional[re.Pattern[str]] = None
    if use_regex:
        if isinstance(query, str):
            try:
                regex = re.compile(query)
            except re.error as e:
                # Propagate invalid regex errors
                raise e
        else:
            regex = query
    else:
        # Plain substring mode; if a Pattern is provided, use its pattern string
        if isinstance(query, re.Pattern):
            query_str: str = query.pattern
        else:
            query_str = query

    # Helper: detect binary by scanning initial bytes for NULs
    def is_probably_binary(path: Path) -> bool:
        try:
            with path.open("rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return True
        except OSError:
            # If we cannot read bytes for any reason, treat as non-binary and let text open raise if needed
            return False
        return False

    # Collect candidate files
    candidate_files: List[Path] = []
    if pattern_list is None:
        # All files recursively
        for p in root_path.rglob("*"):
            if p.is_file():
                candidate_files.append(p)
    else:
        seen: set[Path] = set()
        for pat in pattern_list:
            for p in root_path.glob(pat):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    candidate_files.append(p)

    matches: List[GrepMatch] = []
    total_occurrences = 0  # count of individual match occurrences across all lines

    for file_path in candidate_files:
        # Binary exclusion (unless include_binary=True)
        if not include_binary and is_probably_binary(file_path):
            continue

        # Read file line by line to find matches
        with file_path.open("r", encoding=encoding) as f:
            for idx, raw_line in enumerate(f, start=1):
                # Keep the original line text without the trailing newline
                line = raw_line.rstrip("\n")

                spans: List[Tuple[int, int]] = []
                if use_regex and regex is not None:
                    for m in regex.finditer(line):
                        spans.append((m.start(), m.end()))
                else:
                    if query_str == "":
                        # Empty query matches nothing
                        spans = []
                    else:
                        if case_sensitive:
                            start = 0
                            qlen = len(query_str)
                            while True:
                                pos = line.find(query_str, start)
                                if pos == -1:
                                    break
                                spans.append((pos, pos + qlen))
                                start = pos + qlen
                        else:
                            start = 0
                            qlen = len(query_str)
                            lower_line = line.lower()
                            lower_query = query_str.lower()
                            while True:
                                pos = lower_line.find(lower_query, start)
                                if pos == -1:
                                    break
                                spans.append((pos, pos + qlen))
                                start = pos + qlen

                if spans:
                    # Apply max_matches limit in terms of total occurrences
                    if max_matches is not None:
                        remaining = max_matches - total_occurrences
                        if remaining <= 0:
                            break  # stop reading this file; we'll break outer loop below
                        if len(spans) > remaining:
                            spans = spans[:remaining]

                    matches.append(
                        GrepMatch(
                            file_path=file_path,
                            line_number=idx,
                            line_text=line,
                            spans=tuple(spans),
                        )
                    )

                    if max_matches is not None:
                        total_occurrences += len(spans)
                        if total_occurrences >= max_matches:
                            break
            # If we reached the limit in this file, stop processing more files
            if max_matches is not None and total_occurrences >= max_matches:
                break

    return matches