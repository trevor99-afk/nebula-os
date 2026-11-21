"""Live system information from /proc, /sys and standard services.

Every reader takes a `root` (default "/") so tests can point it at a fake
filesystem, and returns None for anything it cannot read.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .util import Runner, read_int, read_text, run, under

NEBULA_SHARE = "usr/share/nebula-os"


# --- OS identity -----------------------------------------------------------

def parse_os_release(text: str) -> Dict[str, str]:
    """Parse os-release(5) shell-style KEY=value lines."""
    result: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote, value = value[0], value[1:-1]
            if quote == '"':
                out, i = [], 0
                while i < len(value):
                    if value[i] == "\\" and i + 1 < len(value) and value[i + 1] in '"\\$`':
                        out.append(value[i + 1])
                        i += 2
                    else:
                        out.append(value[i])
                        i += 1
                value = "".join(out)
        result[key.strip()] = value
    return result


def os_info(root: str = "/") -> Dict[str, Optional[str]]:
    release: Dict[str, str] = {}
    for rel in ("etc/os-release", "usr/lib/os-release"):
        text = read_text(under(root, rel))
        if text:
            release = parse_os_release(text)
            break
    info: Dict[str, Optional[str]] = {
        "name": release.get("NAME"),
        "pretty_name": release.get("PRETTY_NAME"),
        "version": release.get("VERSION"),
        "version_id": release.get("VERSION_ID"),
        "id": release.get("ID"),
        "variant_id": release.get("VARIANT_ID"),
        "image_version": release.get("IMAGE_VERSION"),
        "image_ref": read_text(under(root, f"{NEBULA_SHARE}/image-ref")),
        "base_image": read_text(under(root, f"{NEBULA_SHARE}/base-image")),
        "edition": None,
    }
    build = read_text(under(root, f"{NEBULA_SHARE}/build-info.json"))
    if build:
        try:
            info["build"] = json.loads(build)
        except ValueError:
            pass
    image_info = read_text(under(root, "usr/share/ublue-os/image-info.json"))
    if image_info:
        try:
            info["edition"] = json.loads(image_info).get("image-name")
        except ValueError:
            pass
    info["kernel"] = os.uname().release if root == "/" else None
    return info


def uptime_seconds(root: str = "/") -> Optional[float]:
    text = read_text(under(root, "proc/uptime"))
    try:
        return float(text.split()[0]) if text else None
    except (ValueError, IndexError):
        return None


# --- CPU --------------------------------------------------------------------

def read_cpu_times(root: str = "/") -> Optional[Tuple[int, int]]:
    """Return (busy, total) jiffies from the aggregate line of /proc/stat."""
    text = read_text(under(root, "proc/stat"))
    if not text:
        return None
    first = text.splitlines()[0].split()
    if not first or first[0] != "cpu":
        return None
    try:
        values = [int(v) for v in first[1:9]]  # user..steal (guest is already in user)
    except ValueError:
        return None
    values += [0] * (8 - len(values))
    idle = values[3] + values[4]  # idle + iowait
    total = sum(values)
    return total - idle, total


def cpu_usage_percent(before: Optional[Tuple[int, int]], after: Optional[Tuple[int, int]]) -> Optional[float]:
    if not before or not after:
        return None
    busy, total = after[0] - before[0], after[1] - before[1]
    if total <= 0:
        return None
    return round(100.0 * busy / total, 1)


def cpu_model(root: str = "/") -> Dict[str, Optional[object]]:
    text = read_text(under(root, "proc/cpuinfo")) or ""
    model = vendor = None
    threads = 0
    cores = set()
    physical = core = None
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "processor":
            threads += 1
        elif key == "model name" and model is None:
            model = value
        elif key == "vendor_id" and vendor is None:
            vendor = value
        elif key == "physical id":
            physical = value
        elif key == "core id":
            core = value
            cores.add((physical, core))
    return {
        "model": model,
        "vendor": {"AuthenticAMD": "AMD", "GenuineIntel": "Intel"}.get(vendor or "", vendor),
        "threads": threads or None,
        "cores": len(cores) or None,
    }


# --- Memory -----------------------------------------------------------------

def memory(root: str = "/") -> Optional[Dict[str, Optional[float]]]:
    text = read_text(under(root, "proc/meminfo"))
    if not text:
        return None
    values: Dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key.strip()] = int(parts[0]) * 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    used = total - available
    swap_total = values.get("SwapTotal", 0)
    swap_used = swap_total - values.get("SwapFree", 0) if swap_total else 0
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "used_percent": round(100.0 * used / total, 1),
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
    }


# --- Storage ----------------------------------------------------------------

# On an image-based system "/" is a read-only composefs/overlay; the real disk
# shows up under /sysroot and /var.
STORAGE_PATHS = ("/sysroot", "/var", "/var/home")


def storage(paths: Sequence[str] = STORAGE_PATHS, statvfs: Callable = os.statvfs) -> List[Dict[str, object]]:
    """Usage of the filesystems behind `paths`, one entry per filesystem."""
    result: List[Dict[str, object]] = []
    seen = set()
    for path in paths:
        try:
            st = statvfs(path)
        except OSError:
            continue
        if not st.f_blocks:
            continue
        # btrfs subvolumes report different st_dev values; identical block
        # counts identify the same filesystem.
        key = (st.f_blocks, st.f_frsize, st.f_bfree)
        if key in seen:
            continue
        seen.add(key)
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        usable = used + avail
        result.append({
            "path": path,
            "total_bytes": total,
            "used_bytes": used,
            "available_bytes": avail,
            "used_percent": round(100.0 * used / usable, 1) if usable else None,
        })
    return result


def block_devices(root: str = "/") -> List[Dict[str, object]]:
    """Physical disks from /sys/block (skips loop, zram, ram and device-mapper)."""
    disks: List[Dict[str, object]] = []
    base = under(root, "sys/block")
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return disks
    for entry in entries:
        name = entry.name
        if name.startswith(("loop", "zram", "ram", "dm-", "sr", "fd", "md")):
            continue
        sectors = read_int(entry / "size")
        if not sectors:
            continue
        model = read_text(entry / "device" / "model") or read_text(entry / "device" / "name")
        transport = "nvme" if name.startswith("nvme") else ("mmc" if name.startswith("mmcblk") else None)
        if transport is None:
            real = os.path.realpath(entry)
            transport = "usb" if "/usb" in real else ("sata/sas" if name.startswith("sd") else None)
        disks.append({
            "name": name,
            "model": model,
            "size_bytes": sectors * 512,
            "rotational": read_int(entry / "queue" / "rotational") == 1,
            "removable": read_int(entry / "removable") == 1,
            "transport": transport,
        })
    return disks


# --- Network ----------------------------------------------------------------

def read_net_counters(root: str = "/") -> Dict[str, Tuple[int, int]]:
    """{interface: (rx_bytes, tx_bytes)} from /proc/net/dev, without loopback."""
    text = read_text(under(root, "proc/net/dev"))
    counters: Dict[str, Tuple[int, int]] = {}
    if not text:
        return counters
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        name = name.strip()
        fields = rest.split()
        if not name or name == "lo" or len(fields) < 9:
            continue
        try:
            counters[name] = (int(fields[0]), int(fields[8]))
        except ValueError:
            continue
    return counters


def net_rates(before: Dict[str, Tuple[int, int]], after: Dict[str, Tuple[int, int]], seconds: float) -> Dict[str, object]:
    rx = tx = 0.0
    per_iface = {}
    for name, (rx1, tx1) in after.items():
        if name not in before or seconds <= 0:
            continue
        rx0, tx0 = before[name]
        d_rx, d_tx = max(rx1 - rx0, 0) / seconds, max(tx1 - tx0, 0) / seconds
        per_iface[name] = {"rx_bytes_per_s": round(d_rx), "tx_bytes_per_s": round(d_tx)}
        rx += d_rx
        tx += d_tx
    return {"rx_bytes_per_s": round(rx), "tx_bytes_per_s": round(tx), "interfaces": per_iface}


# --- Temperatures -------------------------------------------------------------

# hwmon driver name -> preferred sensor labels (first match wins)
CPU_SENSORS = (
    ("k10temp", ("Tctl", "Tdie")),
    ("zenpower", ("Tdie", "Tctl")),
    ("coretemp", ("Package id 0",)),
    ("cpu_thermal", ()),
)


def _hwmon_temps(hwmon: Path) -> List[Tuple[Optional[str], float]]:
    temps = []
    for inp in sorted(hwmon.glob("temp*_input")):
        value = read_int(inp)
        if value is None:
            continue
        label = read_text(inp.with_name(inp.name.replace("_input", "_label")))
        temps.append((label, value / 1000.0))
    return temps


def cpu_temperature(root: str = "/") -> Optional[float]:
    base = under(root, "sys/class/hwmon")
    try:
        hwmons = sorted(base.iterdir())
    except OSError:
        return None
    by_name = {}
    for hw in hwmons:
        name = read_text(hw / "name")
        if name:
            by_name.setdefault(name, hw)
    for name, labels in CPU_SENSORS:
        hw = by_name.get(name)
        if hw is None:
            continue
        temps = _hwmon_temps(hw)
        for wanted in labels:
            for label, value in temps:
                if label == wanted:
                    return round(value, 1)
        if temps:
            return round(temps[0][1], 1)
    return None


# --- Power profile -----------------------------------------------------------

_PPD_SERVICES = (
    ("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles"),
    ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles"),
)


def power_profile(runner: Runner = run) -> Dict[str, Optional[str]]:
    """Active power profile (power-profiles-daemon API, served by tuned-ppd on
    Bazzite) and the underlying tuned profile."""
    profile = None
    for service, path in _PPD_SERVICES:
        res = runner(["busctl", "--system", "get-property", service, path, service, "ActiveProfile"], timeout=3)
        if res.ok and res.stdout.startswith("s "):
            profile = res.stdout.split(" ", 1)[1].strip().strip('"')
            break
    tuned = None
    res = runner(["tuned-adm", "active"], timeout=3)
    if res.ok and ":" in res.stdout:
        tuned = res.stdout.split(":", 1)[1].strip() or None
    return {"profile": profile, "tuned_profile": tuned}


# --- Sampling ------------------------------------------------------------------

def sample(root: str = "/", seconds: float = 0.5, sleep: Callable[[float], None] = time.sleep) -> Dict[str, object]:
    """Measure CPU usage and network throughput over `seconds`."""
    cpu0, net0 = read_cpu_times(root), read_net_counters(root)
    start = time.monotonic()
    sleep(seconds)
    elapsed = max(time.monotonic() - start, seconds) if sleep is time.sleep else seconds
    cpu1, net1 = read_cpu_times(root), read_net_counters(root)
    return {"cpu_percent": cpu_usage_percent(cpu0, cpu1), "network": net_rates(net0, net1, elapsed)}
