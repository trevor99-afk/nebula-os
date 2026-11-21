"""The `nebula` command: status, hardware report, System Doctor and updates.

Every subcommand accepts --json and prints machine-readable output; the
future Nebula Control Center uses the same data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional

from . import __version__, doctor, gpu as gpu_mod, hardware, sysinfo, updates
from .util import human_bytes, human_duration, run

_STYLE = {"ok": ("✔", "32"), "info": ("ℹ", "36"), "warn": ("⚠", "33"), "fail": ("✖", "31"), "skip": ("–", "90")}
_SHORT_LABELS = {"vulkan": "Vulkan", "opengl": "OpenGL", "vaapi": "Video accel.", "gpu-power": "Power mgmt",
                 "vrr": "VRR", "hdr": "HDR"}


def _use_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _badge(status: str) -> str:
    symbol, code = _STYLE.get(status, ("?", "0"))
    return f"\033[{code}m{symbol}\033[0m" if _use_color() else symbol


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _use_color() else text


def _row(label: str, value: str) -> None:
    print(f"  {label:<16} {value}")


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.0f}%"


def _temp(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.0f} °C"


# --- status ------------------------------------------------------------------------------------

def collect_status(sample_seconds: float = 0.5) -> Dict[str, object]:
    os_info = sysinfo.os_info()
    sampled = sysinfo.sample(seconds=sample_seconds)
    gpus = gpu_mod.detect_gpus()
    for g in gpus:
        g.metrics = gpu_mod.backend_for(g).metrics(g)
    update_state = updates.summary(updates.deployments())
    return {
        "schema": "nebula.status/v1",
        "time": int(time.time()),
        "os": os_info,
        "uptime_seconds": sysinfo.uptime_seconds(),
        "cpu": {**sysinfo.cpu_model(), "usage_percent": sampled["cpu_percent"], "temperature_c": sysinfo.cpu_temperature()},
        "memory": sysinfo.memory(),
        "storage": sysinfo.storage(),
        "network": sampled["network"],
        "gpus": [{"card": g.card, "vendor": g.vendor, "name": g.name, "driver": g.driver,
                  "sleeping": g.sleeping, "metrics": g.metrics} for g in gpus],
        "power": sysinfo.power_profile(),
        "updates": {k: update_state.get(k) for k in ("state", "message")},
        "health": doctor.quick_health(doctor.Context(edition=os_info.get("edition"))),
    }


def print_status(data: Dict[str, object]) -> None:
    os_info = data["os"]
    build = os_info.get("build") or {}
    version = build.get("version") or os_info.get("image_version") or os_info.get("version") or ""
    print(_bold(f"{os_info.get('pretty_name') or 'Linux'}") + f"  {version}  (edition: {os_info.get('edition') or 'n/a'})")
    _row("Uptime", human_duration(data["uptime_seconds"]))
    cpu = data["cpu"]
    _row("CPU", f"{cpu.get('model') or 'n/a'}  {_pct(cpu.get('usage_percent'))}  {_temp(cpu.get('temperature_c'))}".rstrip())
    mem = data["memory"] or {}
    _row("Memory", f"{human_bytes(mem.get('used_bytes'))} / {human_bytes(mem.get('total_bytes'))} ({_pct(mem.get('used_percent'))})")
    for st in data["storage"]:
        _row(f"Disk {st['path']}", f"{human_bytes(st['used_bytes'])} / {human_bytes(st['total_bytes'])} ({_pct(st['used_percent'])})")
    net = data["network"]
    _row("Network", f"down {human_bytes(net['rx_bytes_per_s'])}/s  up {human_bytes(net['tx_bytes_per_s'])}/s")
    for g in data["gpus"]:
        m = g["metrics"]
        label = f"{g['name'] or g['vendor']} ({g['driver'] or 'no driver'})"
        if g["sleeping"]:
            value = f"{label}  sleeping"
        else:
            vram = ""
            if m.get("vram_total_bytes"):
                vram = f"  VRAM {human_bytes(m.get('vram_used_bytes'))}/{human_bytes(m.get('vram_total_bytes'))}"
            value = f"{label}  {_pct(m.get('usage_percent'))}  {_temp(m.get('temperature_c'))}{vram}"
        _row(f"GPU {g['card']}", value)
    power = data["power"]
    tuned = f" (tuned: {power['tuned_profile']})" if power.get("tuned_profile") else ""
    _row("Power profile", f"{power.get('profile') or 'n/a'}{tuned}")
    _row("Updates", str(data["updates"]["message"]))
    health = data["health"]
    text = "all good" if health["status"] == "ok" else "; ".join(health["problems"]) + "  (run: nebula doctor)"
    _row("Health", f"{_badge(health['status'])} {text}")


# --- hw ----------------------------------------------------------------------------------------

def print_hardware(data: Dict[str, object]) -> None:
    system = data["system"]
    print(_bold("System"))
    _row("Machine", " ".join(v for v in (system.get("sys_vendor"), system.get("product_version") or system.get("product_name")) if v) or "n/a")
    _row("Kernel", str(data.get("kernel") or "n/a"))
    sb = data.get("secure_boot")
    _row("Secure Boot", "n/a" if sb is None else ("on" if sb else "off"))
    cpu = data["cpu"]
    _row("CPU", f"{cpu.get('model') or 'n/a'} ({cpu.get('cores') or '?'} cores / {cpu.get('threads') or '?'} threads) {_temp(cpu.get('temperature_c'))}")
    mem = data.get("memory") or {}
    _row("Memory", human_bytes(mem.get("total_bytes")))
    for disk in data["storage_devices"]:
        _row(f"Disk {disk['name']}", f"{disk.get('model') or ''} {human_bytes(disk['size_bytes'])} ({disk.get('transport') or 'unknown'})".strip())

    for g in data["gpus"]:
        print()
        title = g.get("name") or f"{g['vendor']} {g.get('device_id')}"
        print(_bold(f"GPU {g['card']}: {title}"))
        _row("Vendor / arch", f"{g['vendor']} / {g.get('architecture') or 'unknown'}" + (f" ({g['codename']})" if g.get("codename") else ""))
        _row("Type", f"{g.get('kind') or 'unknown'}" + ("  [boot display]" if g.get("boot_vga") else ""))
        _row("Kernel driver", g.get("driver") or "none")
        vk = g.get("vulkan") or {}
        if vk:
            _row("Vulkan driver", f"{vk.get('driver')} {vk.get('driver_info') or ''} (API {vk.get('api_version')})")
        _row("Outputs in use", ", ".join(g.get("connected_outputs") or []) or "none")
        _row("State", "sleeping (not woken for monitoring)" if g.get("sleeping") else "active")
        for cap in g.get("capabilities", []):
            evidence = f" — {cap['evidence'][0]}" if cap["evidence"] else ""
            _row(_SHORT_LABELS.get(cap["id"], cap["id"]), f"{cap['status']}{evidence}")

    for d in data["displays"]:
        print()
        edid = d.get("edid") or {}
        comp = d.get("compositor") or {}
        name = comp.get("display_name") or edid.get("name") or d["connector"]
        print(_bold(f"Display {d['connector']}: {name}"))
        native = edid.get("native_mode") or {}
        if native:
            _row("Native mode", f"{native.get('width')}x{native.get('height')} @ {native.get('refresh_hz')} Hz")
        cur = comp.get("current_mode") or {}
        if cur:
            _row("Current mode", f"{cur['width']}x{cur['height']} @ {cur['refresh_hz']} Hz ({'variable' if cur.get('variable') else 'fixed'} refresh)")
        if edid.get("bits_per_color"):
            _row("Color depth", f"{edid['bits_per_color']} bits per color")
        limits = edid.get("range_limits") or {}
        if limits:
            _row("Refresh range", f"{limits['min_v_hz']}-{limits['max_v_hz']} Hz")
        for cap in d.get("capabilities", []):
            _row(cap["id"].upper(), f"{cap['status']}" + (f" — {'; '.join(cap['evidence'][:2])}" if cap["evidence"] else ""))

    hybrid = data.get("hybrid_graphics")
    if hybrid:
        print()
        print(_bold("Hybrid graphics"))
        _row("GPUs", ", ".join(hybrid["gpus"]))
        _row("Driving screens", ", ".join(hybrid["display_gpus"]) or "none")
        if hybrid.get("cardwire_mode"):
            modes = hybrid.get("cardwire_available_modes")
            _row("CardWire mode", str(hybrid["cardwire_mode"]) + (f" (available: {', '.join(modes)})" if modes else ""))

    stack = data["gaming_stack"]
    print()
    print(_bold("Gaming stack (from Bazzite)"))
    for key, label in (("steam", "Steam"), ("gamescope", "Gamescope"), ("mangohud", "MangoHud"), ("vkbasalt", "vkBasalt"), ("gamemode", "GameMode")):
        value = stack.get(key)
        _row(label, "n/a" if value is None else ("installed" if value is True else ("not installed" if value is False else str(value))))

    if data["notes"]:
        print()
        print(_bold("Notes"))
        for note in data["notes"]:
            subject = f"[{note['subject']}] " if note.get("subject") else ""
            print(f"  {_badge(note['level'])} {subject}{note['message']}")


# --- doctor --------------------------------------------------------------------------------------

def print_doctor(results: List[doctor.Check]) -> None:
    for c in results:
        print(f"{_badge(c.status)} {_bold(c.title)}: {c.summary}")
        if c.status in ("fail", "warn"):
            for line in c.details[:6]:
                print(f"      {line}")
        if c.fix and c.status in ("fail", "warn", "info"):
            print(f"      → {c.fix}")
    status = doctor.overall(results)
    print()
    print({"ok": "Everything looks good.", "warn": "Some things need attention.", "fail": "Problems found."}[status])


def write_report(path: str, results: List[doctor.Check], include_logs: bool) -> None:
    data = {
        "schema": "nebula.doctor-report/v1",
        "created": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "os": sysinfo.os_info(),
        "hardware": hardware.report(probe=False, compositor=False),
        "checks": [c.to_dict() for c in results],
    }
    if include_logs:
        res = run(["journalctl", "-b", "-p", "err", "-n", "200", "--no-pager", "-o", "short-iso"], timeout=20)
        data["error_log"] = res.stdout.splitlines()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"Report written to {path}.")
    if include_logs:
        print("It contains this boot's error log, which can include names of devices, networks and users. "
              "Read it before sharing it.")


# --- main ----------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser = argparse.ArgumentParser(prog="nebula", description="NebulaOS system tools.")
    parser.add_argument("--version", action="version", version=f"nebula {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", parents=[common], help="live system overview")
    hw = sub.add_parser("hw", parents=[common], help="hardware and capability report")
    hw.add_argument("--no-probe", action="store_true", help="skip Vulkan/OpenGL/VA-API probes (they wake sleeping GPUs)")
    doc = sub.add_parser("doctor", parents=[common], help="diagnose common problems (changes nothing)")
    doc.add_argument("--report", metavar="FILE", help="also write a JSON report to FILE")
    doc.add_argument("--include-logs", action="store_true", help="add this boot's error log to the report")
    upd = sub.add_parser("update", help="check for and manage system updates")
    upd_sub = upd.add_subparsers(dest="action", required=True)
    upd_sub.add_parser("check", parents=[common], help="ask the registry whether a newer image exists")
    upd_sub.add_parser("history", parents=[common], help="list deployments (current, staged, previous)")
    apply_p = upd_sub.add_parser("apply", help="download and stage the newest image (asks first)")
    apply_p.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    rb = upd_sub.add_parser("rollback", help="boot the previous deployment next time (asks first)")
    rb.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    return parser


def _dump(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        data = collect_status()
        _dump(data) if args.json else print_status(data)
        return 0
    if args.command == "hw":
        data = hardware.report(probe=not args.no_probe)
        _dump(data) if args.json else print_hardware(data)
        return 0
    if args.command == "doctor":
        ctx = doctor.Context(edition=sysinfo.os_info().get("edition"))
        results = doctor.diagnose(ctx)
        if args.json:
            _dump({"schema": "nebula.doctor/v1", "status": doctor.overall(results), "checks": [c.to_dict() for c in results]})
        else:
            print_doctor(results)
        if args.report:
            write_report(args.report, results, args.include_logs)
        return 1 if doctor.overall(results) == "fail" else 0
    if args.command == "update":
        info = updates.deployments()
        if args.action == "check":
            result = updates.check_remote(info)
            _dump(result) if args.json else print(f"{result['message']}" + (f"\n  image: {result['image']}" if result.get("image") else ""))
            return 0 if result["state"] in ("up-to-date", "available", "staged") else 1
        if args.action == "history":
            deps = (info or {}).get("deployments", [])
            if args.json:
                _dump(deps)
            else:
                if not deps:
                    print("No deployments found (rpm-ostree is not available here).")
                for d in deps:
                    tags = [t for t, on in (("current", d["booted"]), ("staged", d["staged"]), ("pinned", d["pinned"])) if on]
                    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(d["timestamp"])) if d.get("timestamp") else "?"
                    print(f"{'*' if d['booted'] else ' '} {d.get('version') or '?':<22} {when}  {d.get('image') or d.get('image_ref')}"
                          f"  [{d.get('verification')}]" + (f"  ({', '.join(tags)})" if tags else ""))
            return 0
        if args.action == "apply":
            return updates.apply(assume_yes=args.yes)
        if args.action == "rollback":
            return updates.rollback(info, assume_yes=args.yes)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
