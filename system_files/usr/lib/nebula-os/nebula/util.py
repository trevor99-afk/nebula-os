"""Shared helpers: safe file reads and subprocess calls.

Commands run without a shell, with a timeout, the C locale and no stdin, and
never raise for a missing tool or a timeout: callers get a CommandResult with
a non-zero return code instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

NOT_INSTALLED = 127
TIMED_OUT = 124


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# Signature of run(); tests pass fakes with the same shape.
Runner = Callable[..., CommandResult]


def _command_env(extra: Optional[dict] = None) -> dict:
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    env.pop("LANGUAGE", None)
    if extra:
        env.update(extra)
    return env


def run(cmd: Sequence[str], timeout: float = 10.0, env: Optional[dict] = None) -> CommandResult:
    """Run a command and capture its output (no shell, no stdin).
    `env` adds variables on top of the current environment."""
    if not cmd:
        raise ValueError("empty command")
    if shutil.which(cmd[0]) is None:
        return CommandResult(NOT_INSTALLED, "", f"{cmd[0]}: not installed")
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_command_env(env),
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(TIMED_OUT, "", f"{cmd[0]}: timed out after {timeout:g}s")
    except OSError as exc:
        return CommandResult(126, "", f"{cmd[0]}: {exc}")
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def run_interactive(cmd: Sequence[str]) -> int:
    """Run a command attached to the terminal, so it can show progress and
    authentication prompts (polkit). Returns the exit code."""
    if shutil.which(cmd[0]) is None:
        print(f"{cmd[0]} is not installed.", file=sys.stderr)
        return NOT_INSTALLED
    return subprocess.run(list(cmd), check=False).returncode


def under(root: str | os.PathLike, path: str) -> Path:
    """Place an absolute path below `root`. Tests use this to point the
    readers at a fake /proc and /sys."""
    return Path(root) / path.lstrip("/")


def read_text(path: str | os.PathLike) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def read_int(path: str | os.PathLike) -> Optional[int]:
    text = read_text(path)
    if not text:
        return None
    try:
        return int(text.split()[0])
    except ValueError:
        return None


def human_bytes(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"  # pragma: no cover


def human_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "n/a"
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
