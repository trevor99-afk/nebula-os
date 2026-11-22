"""Nebula System Doctor: diagnose common problems and suggest fixes.

The doctor only reads. It never runs a fix itself: every problem comes with a
suggested command or setting for the user to apply.
"""

from __future__ import annotations

import json
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import gpu as gpu_mod
from . import sysinfo, updates
from .util import Runner, read_int, read_text, run, under

ORDER = {"fail": 0, "warn": 1, "info": 2, "ok": 3, "skip": 4}
APP_LIST = "usr/share/nebula-os/flatpaks.list"


@dataclass
class Check:
    id: str
    title: str
    status: str
    summary: str
    details: List[str] = field(default_factory=list)
    fix: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


@dataclass
class Context:
    root: str = "/"
    runner: Runner = run
    edition: Optional[str] = None


# --- Individual checks -------------------------------------------------------------------

def check_selinux(ctx: Context) -> Check:
    res = ctx.runner(["getenforce"], timeout=5)
    if not res.ok:
        return Check("selinux", "SELinux", "skip", "getenforce is not available.")
    mode = res.stdout.strip()
    if mode == "Enforcing":
        return Check("selinux", "SELinux", "ok", "Enforcing.")
    if mode == "Permissive":
        return Check("selinux", "SELinux", "warn", "Permissive: security policy violations are only logged.",
                     fix="Remove the enforcing=0 kernel argument (rpm-ostree kargs) and restart.")
    return Check("selinux", "SELinux", "fail", f"SELinux is {mode or 'off'}.",
                 fix="NebulaOS expects SELinux to be enforcing; check `rpm-ostree kargs` for selinux=0.")


def _failed_units(ctx: Context, user: bool) -> Optional[List[str]]:
    cmd = ["systemctl"] + (["--user"] if user else []) + ["--failed", "--output=json", "--no-pager"]
    res = ctx.runner(cmd, timeout=10)
    if not res.ok:
        return None
    try:
        return [u.get("unit", "?") for u in json.loads(res.stdout or "[]")]
    except ValueError:
        return None


def check_failed_units(ctx: Context) -> Check:
    system, user = _failed_units(ctx, False), _failed_units(ctx, True)
    if system is None and user is None:
        return Check("services", "Services", "skip", "systemd is not running here.")
    failed = [f"{u} (system)" for u in system or []] + [f"{u} (user)" for u in user or []]
    if not failed:
        return Check("services", "Services", "ok", "No failed services.")
    first = (system or user or ["<unit>"])[0]
    return Check("services", "Services", "warn", f"{len(failed)} failed service(s).", failed,
                 fix=f"See why with `journalctl -b -u {first}`" + (" (add --user for user services)" if not system else "") +
                 ". After fixing, `systemctl reset-failed` clears the list.")


def check_disk(ctx: Context, statvfs: Optional[Callable] = None) -> Check:
    entries = sysinfo.storage(statvfs=statvfs) if statvfs else sysinfo.storage()
    if not entries:
        return Check("disk", "Disk space", "skip", "No filesystems to check.")
    worst = max(entries, key=lambda e: e["used_percent"] or 0)
    pct = worst["used_percent"] or 0
    details = [f"{e['path']}: {e['used_percent']}% used" for e in entries]
    fix = ("Free space with `flatpak uninstall --unused` and `rpm-ostree cleanup -m`; review "
           "`podman system df` before pruning containers.")
    if pct >= 95:
        return Check("disk", "Disk space", "fail", f"{worst['path']} is {pct}% full. Updates may fail.", details, fix)
    if pct >= 85:
        return Check("disk", "Disk space", "warn", f"{worst['path']} is {pct}% full.", details, fix)
    return Check("disk", "Disk space", "ok", f"Most used: {worst['path']} at {pct}%.", details)


def check_gpus(ctx: Context) -> Check:
    gpus = gpu_mod.detect_gpus(ctx.root, ctx.runner, with_names=False)
    if not gpus:
        return Check("gpu", "Graphics drivers", "warn", "No GPU found.")
    details = [f"{g.card}: {g.vendor} {g.device_id} driver={g.driver or 'none'}" for g in gpus]
    notes = []
    for g in gpus:
        notes += gpu_mod.backend_for(g).notes(g, {"edition": ctx.edition})
    fails = [n for n in notes if n.level == "fail"]
    warns = [n for n in notes if n.level == "warn"]
    if fails:
        return Check("gpu", "Graphics drivers", "fail", fails[0].message, details + [n.message for n in notes],
                     fix="Run `nebula hw` for details; a GPU without a driver may need a different NebulaOS edition.")
    if warns:
        return Check("gpu", "Graphics drivers", "warn", warns[0].message, details + [n.message for n in notes],
                     fix="Run `nebula hw` for the full compatibility report.")
    return Check("gpu", "Graphics drivers", "ok", ", ".join(f"{g.card}: {g.driver}" for g in gpus), details)


_FIRMWARE_RE = re.compile(r"(direct firmware load .* failed|firmware: failed|failed to load firmware|"
                          r"firmware .*(missing|not found)|unable to load .*firmware)", re.IGNORECASE)


def check_firmware(ctx: Context) -> Check:
    res = ctx.runner(["journalctl", "-k", "-b", "-p", "warning", "-o", "cat", "--no-pager"], timeout=15)
    if not res.ok:
        return Check("firmware", "Firmware", "skip", "The kernel log could not be read.")
    hits = [line.strip() for line in res.stdout.splitlines() if _FIRMWARE_RE.search(line)]
    if not hits:
        return Check("firmware", "Firmware", "ok", "No firmware loading errors in this boot.")
    return Check("firmware", "Firmware", "warn", f"{len(hits)} firmware loading error(s) in this boot.", hits[:8],
                 fix="Usually fixed by the next NebulaOS update (firmware comes with the image). "
                     "Report the device if it persists.")


def check_updates(ctx: Context) -> Check:
    info = updates.deployments(ctx.runner)
    if info is None:
        return Check("updates", "Updates", "skip", "rpm-ostree is not available here.")
    state = updates.summary(info)
    booted = state.get("booted") or {}
    details = [f"booted: {booted.get('version')} ({booted.get('verification')}) {booted.get('image')}"]
    timer = ctx.runner(["systemctl", "is-enabled", "uupd.timer"], timeout=5)
    auto = timer.stdout.strip() == "enabled"
    details.append("automatic updates (uupd.timer): " + ("on" if auto else timer.stdout.strip() or "unknown"))
    if booted.get("verification") == "unverified":
        return Check("updates", "Updates", "warn", "Updates are not signature-checked.", details,
                     fix="Run `ujust nebula-enable-signed-updates`, then restart.")
    if not auto:
        return Check("updates", "Updates", "warn", "Automatic updates are off.", details,
                     fix="sudo systemctl enable --now uupd.timer")
    age_days = (time.time() - (booted.get("timestamp") or time.time())) / 86400
    if state["state"] == "staged":
        return Check("updates", "Updates", "info", state["message"], details)
    if age_days > 30:
        return Check("updates", "Updates", "warn", f"The running image is {int(age_days)} days old.", details,
                     fix="Run `nebula update check`, then `ujust update`.")
    return Check("updates", "Updates", "ok", "Signed, automatic updates are on.", details)


def check_network(ctx: Context, resolve: Callable[[str], object] = None) -> Check:
    res = ctx.runner(["nmcli", "networking", "connectivity"], timeout=8)
    if not res.ok:
        return Check("network", "Network", "skip", "NetworkManager is not available here.")
    state = res.stdout.strip()
    if state == "none":
        return Check("network", "Network", "fail", "No network connection.",
                     fix="Connect to Wi-Fi or Ethernet from the top-right system menu.")
    if state in ("portal", "limited"):
        return Check("network", "Network", "warn", f"Connectivity is {state} (a login page or no internet access).",
                     fix="Open a browser to complete the network's login page.")
    resolve = resolve or (lambda host: socket.getaddrinfo(host, 443))
    previous = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(4)
        resolve("ghcr.io")
    except OSError:
        return Check("network", "Network", "warn", "Connected, but the update server's name (ghcr.io) does not resolve.",
                     fix="Check DNS settings in Settings › Network.")
    finally:
        socket.setdefaulttimeout(previous)
    return Check("network", "Network", "ok", f"Connectivity: {state}; DNS works.")


def check_audio(ctx: Context) -> Check:
    res = ctx.runner(["systemctl", "--user", "is-active", "pipewire.service", "wireplumber.service"], timeout=5)
    states = res.stdout.split()
    if not states:
        return Check("audio", "Audio", "skip", "No user session here.")
    if any(s != "active" for s in states):
        return Check("audio", "Audio", "fail", "The audio services are not running.", [f"pipewire/wireplumber: {' '.join(states)}"],
                     fix="systemctl --user restart pipewire wireplumber")
    sink = ctx.runner(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], timeout=5)
    if not sink.ok:
        return Check("audio", "Audio", "warn", "Audio is running but there is no default output device.",
                     fix="Pick an output in Settings › Sound.")
    return Check("audio", "Audio", "ok", "PipeWire is running with a default output.")


def check_bluetooth(ctx: Context) -> Check:
    base = under(ctx.root, "sys/class/bluetooth")
    # Adapters are hciN; the kernel also adds an hciN:HANDLE entry for each connected device.
    adapters = sorted(p.name for p in base.iterdir() if re.fullmatch(r"hci\d+", p.name)) if base.is_dir() else []
    if not adapters:
        return Check("bluetooth", "Bluetooth", "info", "No Bluetooth adapter found.")
    blocked = []
    rfkill = under(ctx.root, "sys/class/rfkill")
    for entry in sorted(rfkill.iterdir()) if rfkill.is_dir() else []:
        if read_text(entry / "type") == "bluetooth":
            if read_int(entry / "hard") == 1:
                blocked.append("hardware switch")
            elif read_int(entry / "soft") == 1:
                blocked.append("turned off")
    if blocked:
        return Check("bluetooth", "Bluetooth", "warn", f"Bluetooth is blocked ({blocked[0]}).", adapters,
                     fix="Turn Bluetooth on in the system menu (or the laptop's wireless switch).")
    service = ctx.runner(["systemctl", "is-active", "bluetooth.service"], timeout=5)
    if service.stdout.strip() != "active":
        return Check("bluetooth", "Bluetooth", "fail", "The Bluetooth service is not running.", adapters,
                     fix="sudo systemctl restart bluetooth")
    return Check("bluetooth", "Bluetooth", "ok", f"Adapter {', '.join(adapters)} ready.")


def controllers(root: str = "/") -> List[str]:
    """Names of connected game controllers (input devices with a joystick handler)."""
    text = read_text(under(root, "proc/bus/input/devices")) or ""
    names = []
    for block in text.split("\n\n"):
        name = re.search(r'^N: Name="(.*)"', block, re.MULTILINE)
        handlers = re.search(r"^H: Handlers=(.*)$", block, re.MULTILINE)
        if name and handlers and re.search(r"\bjs\d+\b", handlers.group(1)):
            names.append(name.group(1))
    return names


def check_controllers(ctx: Context) -> Check:
    found = controllers(ctx.root)
    if found:
        return Check("controllers", "Game controllers", "ok", f"{len(found)} connected.", found)
    return Check("controllers", "Game controllers", "info", "No controller connected.",
                 fix="Bluetooth pads pair in Settings › Bluetooth; USB pads work when plugged in.")


def check_flatpak(ctx: Context) -> Check:
    res = ctx.runner(["flatpak", "remotes", "--columns=name,options"], timeout=10)
    if not res.ok:
        return Check("apps", "Apps (Flatpak)", "skip", "flatpak is not available here.")
    remotes = {line.split()[0]: line for line in res.stdout.splitlines() if line.strip()}
    if "flathub" not in remotes or "disabled" in remotes["flathub"]:
        return Check("apps", "Apps (Flatpak)", "fail", "Flathub is missing or disabled, so apps cannot be installed.",
                     fix="flatpak remote-add --if-not-exists --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo")
    wanted = []
    for line in (read_text(under(ctx.root, APP_LIST)) or "").splitlines():
        app = line.split("#", 1)[0].strip()
        if app:
            wanted.append(app)
    installed = ctx.runner(["flatpak", "list", "--app", "--columns=application"], timeout=15)
    have = set(installed.stdout.split()) if installed.ok else set()
    missing = [a for a in wanted if a not in have]
    setup = ctx.runner(["systemctl", "show", "nebula-os-flatpak-setup.service", "-p", "Result", "-p", "ActiveState"],
                       timeout=5)
    state = {}
    if setup.ok:
        for line in setup.stdout.splitlines():
            key, _, value = line.partition("=")
            state[key.strip()] = value.strip()
    details = [f"bundle apps installed: {len(wanted) - len(missing)}/{len(wanted)}"] + [f"missing: {a}" for a in missing]
    if state.get("Result", "") not in ("success", ""):
        return Check("apps", "Apps (Flatpak)", "warn", "The app bundle installer reported an error.", details,
                     fix="See `journalctl -b -u nebula-os-flatpak-setup`, then run `ujust nebula-install-apps`.")
    if not wanted:
        return Check("apps", "Apps (Flatpak)", "ok", "Flathub is enabled.")
    if missing and state.get("ActiveState") in ("activating", "reloading"):
        # First boot: the bundle is still downloading, so missing apps are not "removed on purpose".
        return Check("apps", "Apps (Flatpak)", "info",
                     f"The app bundle is being installed now; {len(missing)} app(s) still to come.", details,
                     fix="Nothing to do. Follow it with `journalctl -b -u nebula-os-flatpak-setup -f`.")
    if missing:
        return Check("apps", "Apps (Flatpak)", "info", f"{len(missing)} bundle app(s) not installed (maybe removed on purpose).",
                     details, fix="`ujust nebula-install-apps` installs them.")
    return Check("apps", "Apps (Flatpak)", "ok", "Flathub is enabled and the app bundle is installed.", details)


def check_boot(ctx: Context) -> Check:
    res = ctx.runner(["systemd-analyze"], timeout=10)
    if not res.ok:
        return Check("boot", "Boot", "skip", "Boot timing is not available (still booting or no systemd).")
    line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
    total = re.search(r"=\s*([\d.]+(?:min [\d.]+)?s)", line)
    return Check("boot", "Boot", "info", f"Startup took {total.group(1) if total else 'n/a'}.", [line])


CHECKS = (check_selinux, check_failed_units, check_disk, check_gpus, check_firmware, check_updates,
          check_network, check_audio, check_bluetooth, check_controllers, check_flatpak, check_boot)


def diagnose(ctx: Context, checks=CHECKS) -> List[Check]:
    results = []
    for fn in checks:
        try:
            results.append(fn(ctx))
        except Exception as exc:  # a broken check must never stop the others
            name = fn.__name__.replace("check_", "")
            results.append(Check(name, name.title(), "skip", f"Check failed to run: {exc}"))
    return sorted(results, key=lambda c: ORDER.get(c.status, 9))


def overall(results: List[Check]) -> str:
    for status in ("fail", "warn"):
        if any(c.status == status for c in results):
            return status
    return "ok"


def quick_health(ctx: Context) -> Dict[str, object]:
    """A fast subset for status dashboards."""
    results = diagnose(ctx, (check_selinux, check_failed_units, check_disk))
    problems = [c.summary for c in results if c.status in ("fail", "warn")]
    return {"status": overall(results), "problems": problems}
