"""Read-only Git facts about a project folder, without running git.

Running `git status` in a folder you did not create can execute commands named
in that repository's own configuration (core.fsmonitor, clean filters), for
example in a downloaded archive that contains a .git folder. So this module only
reads a few small files: which branch is checked out, whether HEAD is detached,
and the remote URLs with any user name or password removed. Working-tree status
(uncommitted changes) needs git itself and is left to a later, separately hardened
step of the Dev Hub.
"""

import configparser
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

MAX_READ = 64 * 1024


def _read_small(path: Path) -> Optional[str]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_READ:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def git_dir(folder: Path) -> Optional[Path]:
    """The repository's git directory for `folder` (handles worktrees' `.git` files)."""
    dot = folder / ".git"
    if dot.is_dir() and not dot.is_symlink():
        return dot
    text = _read_small(dot)
    if text and text.startswith("gitdir:"):
        target = Path(text[len("gitdir:"):].strip())
        target = target if target.is_absolute() else (folder / target)
        if target.is_dir():
            return target
    return None


def strip_credentials(url: str) -> str:
    """https://user:token@host/x -> https://host/x (scp-style git@host:x is kept)."""
    if "://" not in url:
        return url
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _remotes(gdir: Path) -> List[Dict[str, str]]:
    # Worktrees keep their config in the main repository ("commondir").
    common = _read_small(gdir / "commondir")
    cfg_dir = (gdir / common.strip()).resolve() if common else gdir
    text = _read_small(cfg_dir / "config")
    if not text:
        return []
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    remotes = []
    for section in parser.sections():
        match = re.fullmatch(r'remote "([^"]+)"', section)
        if match and parser.has_option(section, "url"):
            remotes.append({"name": match.group(1), "url": strip_credentials(parser.get(section, "url"))})
    return remotes


def info(folder: str) -> Dict[str, object]:
    """{"repository": bool, "branch": str|None, "detached": bool, "commit": str|None, "remotes": [...]}"""
    path = Path(folder)
    gdir = git_dir(path)
    if gdir is None:
        return {"repository": False, "branch": None, "detached": False, "commit": None, "remotes": []}
    head = (_read_small(gdir / "HEAD") or "").strip()
    branch, commit, detached = None, None, False
    if head.startswith("ref: refs/heads/"):
        branch = head[len("ref: refs/heads/"):]
    elif re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", head):
        detached, commit = True, head
    return {"repository": True, "branch": branch, "detached": detached, "commit": commit,
            "remotes": _remotes(gdir)}
