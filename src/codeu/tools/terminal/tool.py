from __future__ import annotations

from pathlib import Path
from typing import Optional
import os
import re

# LangChain's tool decorator (preferred). If unavailable, provide a no-op fallback.
try:
    from langchain.tools import tool  # type: ignore
except Exception:  # pragma: no cover
    def tool(name: str, parse_docstring: bool = False):
        def _decorator(fn):
            return fn
        return _decorator

from .bash_terminal import BashTerminal

# Module-level persistent bash terminal instance
_TERMINAL: Optional[BashTerminal] = None
_PROJECT_ROOT: Optional[Path] = None


def _get_project_root() -> Path:
    """Detect the project root by locating `pyproject.toml` upwards from this file.

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


def _get_terminal() -> BashTerminal:
    """Return the persistent BashTerminal, creating it on first use."""
    global _TERMINAL
    if _TERMINAL is None:
        _TERMINAL = BashTerminal(cwd=_get_project_root())
    return _TERMINAL


def _is_command_safe(cmd: str) -> tuple[bool, Optional[str]]:
    """Basic safety checks to prevent dangerous operations.

    Blocks blacklisted administrative/system commands, `sudo`, and dangerous `rm -rf` patterns.
    """
    blacklist = {
        "groupadd", "groupdel", "groupmod", "ifdown", "ifup", "killall", "lvremove", "mount",
        "passwd", "pkill", "pvremove", "reboot", "route", "service", "shutdown", "su", "sysctl",
        "systemctl", "umount", "useradd", "userdel", "usermod", "vgremove",
    }
    extra_block = {"mkfs", "fdisk", "iptables", "ifconfig"}

    # Block sudo
    if re.search(r"(^|\s)sudo(\s|$)", cmd):
        return False, "Use of 'sudo' is not allowed."

    # Block rm -rf / or rm -rf /*
    if re.search(r"rm\s+-rf\s+(/\*|/($|\s))", cmd):
        return False, "Dangerous removal detected (rm -rf on root)."

    # Tokenize and check base command names
    tokens = re.findall(r"[A-Za-z0-9_./-]+", cmd)
    for t in tokens:
        base = os.path.basename(t)
        if base in blacklist or base in extra_block:
            return False, f"Command '{base}' is not permitted."

    return True, None


@tool("bash", parse_docstring=False)
def bash_tool(command: str, reset_cwd: Optional[bool] = False):
    """Execute a standard bash command in a keep-alive shell, and return the output if successful or error message if failed.

    Use this tool to perform:
    - Create directories
    - Install dependencies
    - Start development server
    - Run tests and linting
    - Git operations

    Never use this tool to perform any harmful or dangerous operations.

    Use `ls`, `grep` and `tree` tools for file system operations instead of this tool.

    Args:
        command: The command to execute.
        reset_cwd: Whether to reset the current working directory to the project root directory.
    """
    # Validate command
    if not isinstance(command, str) or not command.strip():
        return "Error: command must be a non-empty string."

    safe, reason = _is_command_safe(command)
    if not safe:
        return f"Error: {reason}"

    terminal = _get_terminal()

    # Optionally reset working directory to project root
    if reset_cwd:
        root = _get_project_root()
        terminal.execute(f'cd "{str(root)}"')

    # Execute the command and capture exit code
    combined = f'{command}; echo "__EXIT_CODE:$?"'
    output = terminal.execute(combined)

    # Extract and remove the exit code marker from output
    exit_code_match = re.search(r"__EXIT_CODE:(\d+)", output)
    exit_code: Optional[int] = None
    if exit_code_match:
        exit_code = int(exit_code_match.group(1))
        # Remove the marker (in case it's at the end or standalone line)
        output = re.sub(r"\n?__EXIT_CODE:\d+\n?$", "", output).strip()

    # Determine success/failure
    if exit_code is None:
        # If we couldn't parse the exit code, assume success and return raw output
        return output

    if exit_code != 0:
        return f"Error: command failed with exit code {exit_code}\n{output}" if output else f"Error: command failed with exit code {exit_code}"

    return output