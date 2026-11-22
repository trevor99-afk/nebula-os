"""Test helpers: import path, fake command runner, fake /sys trees, synthetic EDID."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "nebula-os"))

from nebula.util import CommandResult  # noqa: E402


class FakeRunner:
    """Returns canned CommandResults for commands that start with a given prefix."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def __call__(self, cmd, timeout=10.0, env=None):
        self.calls.append((tuple(cmd), env))
        best = None
        for prefix, result in self.responses.items():
            if tuple(cmd[:len(prefix)]) == prefix and (best is None or len(prefix) > len(best[0])):
                best = (prefix, result)
        return best[1] if best else CommandResult(127, "", f"{cmd[0]}: not faked")


def ok(stdout="", stderr=""):
    return CommandResult(0, stdout, stderr)


def fail(code=1, stderr="failed"):
    return CommandResult(code, "", stderr)


def write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def make_gpu(root: Path, card: str, slot: str, vendor: str, device: str, driver: str,
             runtime="active", busy=None, vram=None, temp=None, render="renderD128", connectors=None, boot_vga=0):
    """Create a fake DRM card the way the kernel lays it out in sysfs."""
    dev = root / "sys" / "devices" / "pci0000:00" / slot
    for name, value in (("vendor", vendor), ("device", device), ("boot_vga", str(boot_vga))):
        write(dev / name, value + "\n")
    write(dev / "power" / "runtime_status", runtime + "\n")
    if busy is not None:
        write(dev / "gpu_busy_percent", f"{busy}\n")
    if vram is not None:
        write(dev / "mem_info_vram_used", f"{vram[0]}\n")
        write(dev / "mem_info_vram_total", f"{vram[1]}\n")
    if temp is not None:
        write(dev / "hwmon" / "hwmon9" / "temp1_input", f"{temp}\n")
    (dev / "drm" / render).mkdir(parents=True, exist_ok=True)
    drivers = root / "sys" / "bus" / "pci" / "drivers" / driver
    drivers.mkdir(parents=True, exist_ok=True)
    if not (dev / "driver").exists():
        os.symlink(drivers, dev / "driver")
    drm = root / "sys" / "class" / "drm"
    card_dir = drm / card
    card_dir.mkdir(parents=True, exist_ok=True)
    if not (card_dir / "device").exists():
        os.symlink(dev, card_dir / "device")
    for name, status in (connectors or {}).items():
        write(drm / f"{card}-{name}" / "status", status + "\n")
    return dev


def make_edid(name="NEBULA TEST", width=2560, height=1440, refresh=144.0, vmin=48, vmax=144,
              range_only=True, hdr=False, freesync=False, interface=5, bpc_code=3) -> bytes:
    """Build a small but valid EDID 1.4 (plus optional CTA-861 extension)."""
    b = bytearray(128)
    b[0:8] = bytes.fromhex("00ffffffffffff00")
    b[8:10] = ((14 << 10) | (5 << 5) | 2).to_bytes(2, "big")  # "NEB"
    b[10:12] = (0x1234).to_bytes(2, "little")
    b[18], b[19] = 1, 4
    b[20] = 0x80 | (bpc_code << 4) | interface
    b[21], b[22] = 60, 34
    h_blank, v_blank = 160, 62
    pclk = round(refresh * (width + h_blank) * (height + v_blank) / 10000)
    d = bytearray(18)
    d[0:2] = pclk.to_bytes(2, "little")
    d[2], d[3], d[4] = width & 0xFF, h_blank & 0xFF, ((width >> 8) << 4) | (h_blank >> 8)
    d[5], d[6], d[7] = height & 0xFF, v_blank & 0xFF, ((height >> 8) << 4) | (v_blank >> 8)
    b[54:72] = d
    r = bytearray(18)
    r[3], r[5], r[6], r[7], r[8], r[9], r[10] = 0xFD, vmin, vmax, 30, 230, 60, 0x01 if range_only else 0x00
    b[72:90] = r
    n = bytearray(18)
    n[3] = 0xFC
    n[5:18] = (name.encode()[:12] + b"\n").ljust(13, b" ")
    b[90:108] = n
    filler = bytearray(18)
    filler[3] = 0x10
    b[108:126] = filler
    ext = b""
    if hdr or freesync:
        b[126] = 1
        e = bytearray(128)
        e[0], e[1] = 0x02, 3
        blocks = bytearray()
        if freesync:
            payload = bytes([0x1A, 0x00, 0x00, 0x01, 0x01, vmin, vmax, 0x00])
            blocks += bytes([(3 << 5) | len(payload)]) + payload
        if hdr:
            payload = bytes([0x06, 0x0D, 0x01, 115, 100, 50])  # SDR+PQ+HLG, ~603 nits peak
            blocks += bytes([(7 << 5) | len(payload)]) + payload
            colorimetry = bytes([0x05, 0xC0, 0x80])
            blocks += bytes([(7 << 5) | len(colorimetry)]) + colorimetry
        e[2] = 4 + len(blocks)
        e[4:4 + len(blocks)] = blocks
        ext = bytes(e)
    b[127] = (-sum(b[:127])) & 0xFF
    return bytes(b) + ext
