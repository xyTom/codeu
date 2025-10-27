import os
import re

import pexpect


class BashTerminal:
    """A keep-alive terminal for executing bash commands."""

    def __init__(self, cwd=None):
        """
        Initialize BashTerminal

        Args:
            cwd: Initial working directory, defaults to current directory
        """
        self.cwd = cwd or os.getcwd()

        # Start bash shell in interactive mode, without reading user/system rc files to avoid prompt overrides
        self.prompt = "BASH_TERMINAL_PROMPT> "
        self.done_marker = "__BASH_TERMINAL_DONE__"
        self.shell = pexpect.spawn(
            "/bin/bash",
            ["--noprofile", "--norc", "-i"],
            encoding="utf-8",
            echo=False,
            env={**os.environ, "PS1": self.prompt},
        )

        # Ensure prompt is set and ready (escape as regex for pexpect)
        self.shell.sendline(f'PS1="{self.prompt}"')
        self.shell.expect(re.escape(self.prompt), timeout=10)
        # Disable continuation prompt to avoid stray '> ' in buffers
        self.shell.sendline('PS2=""')
        self.shell.expect_exact(self.prompt, timeout=5)

        # Change to specified directory
        if cwd:
            self.execute(f'cd "{self.cwd}"')

    def execute(self, command):
        """
        Execute bash command and return output

        Args:
            command: Command to execute

        Returns:
            Command output result (string)
        """
        # Drain any stray prompts/output to keep buffer clean
        try:
            while True:
                self.shell.expect_exact(self.prompt, timeout=0.05)
        except pexpect.TIMEOUT:
            pass

        # Send command wrapped to capture stderr as well, followed by a unique done marker
        wrapped = f"( {command} ) 2>&1; printf '\n{self.done_marker}\n'"
        self.shell.sendline(wrapped)

        # Wait for the done marker and capture output up to it
        self.shell.expect(re.escape(self.done_marker), timeout=60)
        output = self.shell.before
        # After marker, bash will print the prompt; consume it to keep buffer clean
        self.shell.expect_exact(self.prompt, timeout=10)

        # Remove our prompt occurrences if any slipped into buffer
        output = output.replace(self.prompt, "")

        # Clean output: remove command echo and any trailing blank lines
        lines = output.split("\n")
        if lines and lines[0].strip() == command.strip():
            lines = lines[1:]
        while lines and lines[-1].strip() == "":
            lines.pop()

        result = "\n".join([line.rstrip() for line in lines]).strip()
        # Remove terminal control characters
        result = re.sub(r"\x1b\[[0-9;]*m", "", result)
        return result

    def getcwd(self):
        """
        Get current working directory

        Returns:
            Absolute path of current working directory
        """
        result = self.execute("pwd")
        return result.strip()

    def close(self):
        """Close shell session"""
        if self.shell.isalive():
            self.shell.sendline("exit")
            self.shell.close()

    def __del__(self):
        """Destructor, ensure shell is closed"""
        self.close()

    def __enter__(self):
        """Support with statement"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support with statement"""
        self.close()