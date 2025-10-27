from __future__ import annotations

from typing import List

# Tools decorator
try:
    from langchain.tools import tool  # type: ignore
except Exception:  # pragma: no cover
    def tool(name: str, parse_docstring: bool = False):
        def _decorator(fn):
            return fn
        return _decorator

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from .models.chat_model import init_chat_model
from .tools.terminal.tool import bash_tool
from .tools.fs.grep import grep as _grep
from .tools.fs.ls import ls as _ls
from .tools.fs.tree import tree as _tree
from .tools.editor.text_editor import str_replace_edit as text_editor_tool

HEADER = "You are CodeU Coding Agent. Use tools to act safely. Prefer ls/grep/tree for filesystem, str_replace_edit for edits. Never run dangerous commands."


@tool("grep", parse_docstring=False)
def grep_tool(
    root: str = ".",
    query: str = "",
    glob: str | List[str] | None = None,
    case_sensitive: bool = True,
    use_regex: bool = False,
    include_binary: bool = False,
    max_matches: int | None = 50,
):
    """Search text across files.

    Args: root: directory, query: text or regex, glob: patterns, case_sensitive, use_regex, include_binary, max_matches.
    Returns: formatted matches as lines "path:line: text".
    """
    try:
        matches = _grep(
            root,
            query if not use_regex else query,
            glob=glob,
            case_sensitive=case_sensitive,
            use_regex=use_regex,
            include_binary=include_binary,
            max_matches=max_matches,
        )
    except Exception as e:
        return f"Error: {e}"

    lines = [f"{m.file_path}:{m.line_number}: {m.line_text}" for m in matches]
    return "\n".join(lines) if lines else "No matches found."


@tool("ls", parse_docstring=False)
def ls_tool(
    directory: str = ".",
    patterns: str | List[str] | None = None,
    include_files: bool = True,
    include_dirs: bool = True,
    absolute_paths: bool = False,
):
    """List direct children of a directory with optional pattern filtering.

    Returns one line per entry, prefixed with [D] or [F].
    """
    try:
        entries = _ls(
            directory,
            patterns=patterns,
            include_files=include_files,
            include_dirs=include_dirs,
            absolute_paths=absolute_paths,
        )
    except Exception as e:
        return f"Error: {e}"

    def fmt(e):
        kind = "[D]" if e.is_dir else "[F]"
        return f"{kind} {e.name} — {e.path}"

    lines = [fmt(e) for e in entries]
    return "\n".join(lines) if lines else "(empty)"


@tool("tree", parse_docstring=False)
def tree_tool(
    root: str = ".",
    max_depth: int = 3,
    patterns: str | List[str] | None = None,
    include_files: bool = True,
    include_dirs: bool = True,
    absolute_paths: bool = False,
):
    """Recursive tree listing up to max_depth (1–3). Returns one line per item."""
    try:
        items = _tree(
            root,
            max_depth=max_depth,
            patterns=patterns,
            include_files=include_files,
            include_dirs=include_dirs,
            absolute_paths=absolute_paths,
        )
    except Exception as e:
        return f"Error: {e}"

    def indent(depth: int) -> str:
        return "  " * max(0, depth - 1)

    def fmt(it):
        kind = "[D]" if it.is_dir else "[F]"
        return f"{indent(it.depth)}{kind} {it.name} — {it.path}"

    lines = [fmt(it) for it in items]
    return "\n".join(lines) if lines else "(empty)"


def create_coding_agent(plugin_tools: list = [], **kwargs):
    """Create a ReAct-style coding agent.

    Args:
        plugin_tools: Additional LangChain tools to include.
        **kwargs: Extra args forwarded to agent creation (e.g., checkpointer, prompt hooks).
    Returns:
        The compiled agent executor.
    """
    return create_react_agent(
        model=init_chat_model(),
        tools=[
            bash_tool,
            grep_tool,
            ls_tool,
            text_editor_tool,
            tree_tool,
        ],
        prompt=f"{HEADER}\nAs a ReAct style coding agent, interpret user instructions and execute them using the most suitable tool.",
        name="coding_agent",
        **kwargs,
    )


# Default memory-enabled agent for multi-turn dialogues
memory = InMemorySaver()
coding_agent = create_coding_agent(checkpointer=memory)
