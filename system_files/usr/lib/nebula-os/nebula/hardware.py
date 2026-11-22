"""Nebula Hardware Detection Engine: the full hardware and capability report.

Combines CPU, memory, storage, GPUs (with vendor backends), displays and the
gaming stack that Bazzite already ships (Gamescope, MangoHud, vkBasalt, Steam,
CardWire), then adds compatibility notes. It only reads; it never changes
drivers or settings.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Dict, List, Optional

from . import display as display_mod
from . import gpu as gpu_mod
from . import sysinfo
from .capabilities import Note
from .util import Runner, read_text, run, under

_DMI_FIELDS = ("sys_vendor", "product_name", "product_version", "board_name", "bios_version")


def dmi(root: str = "/") -> Dict[str, Optional[str]]:
    """Machine identity from DMI. Serial numbers and UUIDs are not read."""
    base = under(root, "sys/class/dmi/id")
    return {name: read_text(base / name) for name in _DMI_FIELDS}


def secure_boot(runner: Runner = run) -> Optional[bool]:
    res = runner(["mokutil", "--sb-state"], timeout=5)
    text = (res.stdout + res.stderr).lower()
    if "secureboot enabled" in text:
        return True
    if "secureboot disabled" in text or "not supported" in text:
        return False
    return None


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _version(runner: Runner, cmd: List[str], pattern: str) -> Optional[str]:
    """First version number matching `pattern` in the tool's output."""
    res = runner(cmd, timeout=5)
    text = _ANSI_RE.sub("", res.stdout + "\n" + res.stderr)
    match = re.search(pattern, text)
    return match.group(1) if match else None


def gaming_stack(root: str = "/", runner: Runner = run) -> Dict[str, object]:
    """What the base image provides for gaming (inherited from Bazzite)."""
    layers = under(root, "usr/share/vulkan/implicit_layer.d")
    layer_names = {p.name for p in layers.iterdir()} if layers.is_dir() else set()
    stack: Dict[str, object] = {
        "steam": bool(shutil.which("steam")) if root == "/" else None,
        "gamescope": (_version(runner, ["gamescope", "--version"], r"gamescope version (\S+)") or True)
        if shutil.which("gamescope") else False,
        "mangohud": any(n.lower().startswith("mangohud") for n in layer_names),
        "vkbasalt": any(n.lower().startswith("vkbasalt") for n in layer_names),
        "gamemode": bool(shutil.which("gamemoderun")) if root == "/" else None,
    }
    return stack


def hybrid_graphics(gpus: List[gpu_mod.Gpu], runner: Runner = run) -> Optional[Dict[str, object]]:
    if len(gpus) < 2:
        return None
    info: Dict[str, object] = {
        "gpus": [g.card for g in gpus],
        "display_gpus": [g.card for g in gpus if g.connected_outputs],
        "cardwire_mode": None,
    }
    if shutil.which("cardwire"):
        res = runner(["cardwire", "get"], timeout=5)
        if res.ok:
            current = re.search(r"Current Mode:\s*(.+)", res.stdout)
            available = re.search(r"Available Mode[s]?:\s*(.+)", res.stdout)
            info["cardwire_mode"] = current.group(1).strip() if current else (res.stdout.strip()[:80] or None)
            info["cardwire_available_modes"] = [m.strip() for m in available.group(1).split(",")] if available else None
    return info


def _nvidia_modeset(root: str) -> Optional[bool]:
    value = read_text(under(root, "sys/module/nvidia_drm/parameters/modeset"))
    return None if value is None else value.upper().startswith("Y")


def report(root: str = "/", runner: Runner = run, probe: bool = True, compositor: bool = True) -> Dict[str, object]:
    os_info = sysinfo.os_info(root)
    gpus = gpu_mod.detect_gpus(root, runner)
    gpu_mod.enrich(gpus, root, runner, probe=probe)
    displays = display_mod.displays(root, runner, use_compositor=compositor)
    context = {"edition": os_info.get("edition"), "nvidia_drm_modeset": _nvidia_modeset(root)}

    notes: List[Note] = []
    if not gpus:
        notes.append(Note("warn", "No GPU found under /sys/class/drm."))
    for g in gpus:
        notes.extend(gpu_mod.backend_for(g).notes(g, context))
        vulkan = next((c for c in g.capabilities if c.id == "vulkan"), None)
        if vulkan is not None and vulkan.available is False:
            notes.append(Note("warn", "Vulkan is not available on this GPU, so Proton/DXVK games will not run on it.", g.card))
    hybrid = hybrid_graphics(gpus, runner)
    if hybrid:
        notes.append(Note("info", f"{len(gpus)} GPUs detected (hybrid or multi-GPU). Bazzite's CardWire manages which GPU "
                          "games use; Steam Gaming Mode can show a black screen on some dual-GPU machines, in which case "
                          "use Work Mode.", "gpus"))
    for d in displays:
        caps = {c["id"]: c for c in d.get("capabilities", [])}
        name = d.get("connector")
        vrr = caps.get("vrr", {})
        if vrr.get("available") and vrr.get("enabled") is False:
            notes.append(Note("info", "Variable refresh rate is available but turned off. Turn it on in "
                              "Settings › Displays › Refresh Rate (choose the Variable option).", str(name)))
        hdr = caps.get("hdr", {})
        if hdr.get("hardware") and hdr.get("available") and not hdr.get("enabled"):
            notes.append(Note("info", "This display supports HDR but it is off. Turn it on in Settings › Displays.", str(name)))
        if hdr.get("hardware") and hdr.get("available") is False:
            notes.append(Note("info", "The display advertises HDR, but the desktop does not offer an HDR mode for it.", str(name)))
    sb = secure_boot(runner)
    if sb and any(g.vendor == "NVIDIA" and g.driver == "nvidia" for g in gpus):
        notes.append(Note("info", "Secure Boot is on: the NVIDIA module needs the Universal Blue key enrolled "
                          "(ujust enroll-secure-boot-key)."))

    return {
        "schema": "nebula.hardware/v1",
        "system": dmi(root),
        "os": os_info,
        "kernel": os.uname().release if root == "/" else None,
        "secure_boot": sb,
        "cpu": {**sysinfo.cpu_model(root), "temperature_c": sysinfo.cpu_temperature(root)},
        "memory": sysinfo.memory(root),
        "storage_devices": sysinfo.block_devices(root),
        "gpus": [g.to_dict() for g in gpus],
        "hybrid_graphics": hybrid,
        "displays": displays,
        "gaming_stack": gaming_stack(root, runner),
        "notes": [n.to_dict() for n in notes],
    }
