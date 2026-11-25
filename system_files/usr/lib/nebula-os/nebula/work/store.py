"""Storage for Nebula Work: XDG locations, versioned JSON documents, locked atomic writes.

Every document is a JSON object with a "schema" field (for example
"nebula.work-project/v1"). Writes go to a temporary file in the same folder and
replace the target atomically; a per-folder lock (flock) keeps the Work Hub and
the CLI from losing each other's changes. Symbolic links are never followed for
writing, and a document that cannot be read is moved aside (never deleted) so the
rest keeps working.
"""

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Iterator, Optional

_XDG = {
    "config": ("XDG_CONFIG_HOME", ".config"),
    "data": ("XDG_DATA_HOME", ".local/share"),
    "cache": ("XDG_CACHE_HOME", ".cache"),
    "state": ("XDG_STATE_HOME", ".local/state"),
}


class StoreError(Exception):
    """A document could not be read or written safely."""


class CorruptDocument(StoreError):
    """A document was unreadable and has been moved aside to `moved_to`."""

    def __init__(self, path: Path, moved_to: Optional[Path], reason: str):
        super().__init__(f"{path}: {reason}")
        self.path, self.moved_to, self.reason = path, moved_to, reason


def xdg_dir(kind: str) -> Path:
    """~/.config/nebula-os/work, ~/.local/share/nebula-os/work, … (XDG variables respected)."""
    env, default = _XDG[kind]
    base = os.environ.get(env, "")
    if not os.path.isabs(base):  # the XDG spec says to ignore relative values
        base = os.path.join(os.path.expanduser("~"), default)
    return Path(base) / "nebula-os" / "work"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise StoreError(f"{path} is a symbolic link; refusing to use it")
    return path


@contextmanager
def locked(directory: Path) -> Iterator[None]:
    """Exclusive lock for a read-modify-write in `directory`."""
    ensure_dir(directory)
    fd = os.open(directory / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _quarantine(path: Path, reason: str) -> CorruptDocument:
    target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
    try:
        os.replace(path, target)
    except OSError:
        target = None
    return CorruptDocument(path, target, reason)


def read_document(path: Path, schema: str,
                  migrate: Optional[Callable[[Dict[str, object]], Optional[Dict[str, object]]]] = None
                  ) -> Optional[Dict[str, object]]:
    """The document at `path`, or None if it does not exist.

    `migrate` may turn an older schema into the current one (return None if it
    cannot). Unreadable documents raise CorruptDocument after being moved aside.
    """
    if path.is_symlink():
        raise StoreError(f"{path} is a symbolic link; refusing to read it")
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as err:
        raise StoreError(f"{path}: {err.strerror or err}") from err
    try:
        data = json.loads(raw)
    except ValueError:
        raise _quarantine(path, "not valid JSON") from None
    if not isinstance(data, dict):
        raise _quarantine(path, "not a JSON object")
    if data.get("schema") != schema:
        migrated = migrate(data) if migrate else None
        if not isinstance(migrated, dict) or migrated.get("schema") != schema:
            raise _quarantine(path, f"unknown schema {data.get('schema')!r}")
        data = migrated
    return data


def write_document(path: Path, data: Dict[str, object]) -> None:
    """Write `data` as JSON to `path` atomically (owner-only permissions)."""
    ensure_dir(path.parent)
    if path.is_symlink():
        raise StoreError(f"{path} is a symbolic link; refusing to overwrite it")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
