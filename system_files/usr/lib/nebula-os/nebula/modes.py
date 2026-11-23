"""NebulaOS start-up mode chooser: saved choices and whether Gaming Mode can run.

The full-screen chooser (/usr/libexec/nebula-os-chooser) and the session wrapper
(/usr/libexec/nebula-os-start) use this module. It only reads sysfs and small
state files in the user's home, so it never wakes a sleeping GPU.

State files (per user, in ~/.local/state/nebula-os/):
  last-mode   the mode chosen last time; the chooser highlights it
  next-mode   a one-time choice made elsewhere (the dock launcher, Steam's
              "Switch to Desktop", `ujust nebula-mode gaming now`); the next
              login starts that mode without asking, then the file is removed
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from .gpu import Gpu, detect_gpus

MODES = ("gaming", "work")

# Kernel drivers of virtual or firmware display devices. Gamescope needs a real
# GPU with Vulkan; on these it stops at "Failed to initialize Vulkan" (seen in a
# GNOME Boxes VM with QXL, where only the llvmpipe software renderer exists).
VIRTUAL_DRIVERS = {
    "qxl", "virtio-pci", "virtio_gpu", "virtio-gpu", "bochs", "bochs-drm", "cirrus", "cirrus-qemu",
    "vmwgfx", "vboxvideo", "hyperv_drm", "simpledrm", "efifb", "vesafb", "ast", "mgag200",
}
# Drivers with a Vulkan driver that gamescope runs on.
GAMING_DRIVERS = {"amdgpu", "i915", "xe", "nvidia", "nouveau"}


def state_dir(home: Optional[str] = None) -> Path:
    base = os.environ.get("XDG_STATE_HOME") if home is None else None
    if base:
        return Path(base) / "nebula-os"
    return Path(home or os.path.expanduser("~")) / ".local" / "state" / "nebula-os"


def _read_mode(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value if value in MODES else None


def _write_mode(path: Path, mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise OSError(f"{path} is a symbolic link")
    # A random, exclusively created temporary file, then an atomic rename: a symlink planted at a
    # predictable "*.tmp" name can no longer redirect the write (red-team finding R02-1).
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(mode + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def last_mode(home: Optional[str] = None) -> Optional[str]:
    return _read_mode(state_dir(home) / "last-mode")


def save_last_mode(mode: str, home: Optional[str] = None) -> None:
    _write_mode(state_dir(home) / "last-mode", mode)


def take_next_mode(home: Optional[str] = None) -> Optional[str]:
    """Return the one-time mode request and remove it, so it applies to one login only."""
    path = state_dir(home) / "next-mode"
    mode = _read_mode(path)
    try:
        path.unlink()
    except OSError:
        pass
    return mode


def gaming_support(root: str = "/", gpus: Optional[List[Gpu]] = None) -> Tuple[bool, str]:
    """(supported, reason). "Supported" means a GPU with a gamescope-capable driver exists.

    Unknown drivers count as supported, so a new driver never locks anyone out of
    Gaming Mode; the chooser only warns when every display device is virtual.
    """
    if gpus is None:
        gpus = detect_gpus(root, with_names=False)
    drivers = [g.driver for g in gpus if g.driver]
    if any(d in GAMING_DRIVERS for d in drivers):
        return True, ""
    if drivers and all(d in VIRTUAL_DRIVERS for d in drivers):
        return False, ("This computer has no graphics card that Gaming Mode can use "
                       "(only a virtual or basic display adapter, as in a virtual machine).")
    if not drivers:
        return False, "No graphics card with a working driver was found."
    return True, ""
