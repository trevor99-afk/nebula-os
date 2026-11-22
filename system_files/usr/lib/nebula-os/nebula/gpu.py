"""GPU detection and the per-vendor backends.

Every backend (AMD, Intel, NVIDIA, generic) implements the same interface:
  metrics(gpu, root, runner)        live usage, temperature, VRAM, power, clock
  power_capability(gpu, root)       what the driver exposes for power management
  notes(gpu, context)               compatibility observations

A GPU that is runtime-suspended (common for the dedicated GPU of a laptop) is
never woken up just to read metrics. The Vulkan, OpenGL and VA-API probes do
wake GPUs, so they only run for the explicit hardware report.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .capabilities import Capability, Note
from .util import Runner, read_int, read_text, run, under

VENDORS = {
    "0x1002": "AMD",
    "0x8086": "Intel",
    "0x10de": "NVIDIA",
    "0x1af4": "Virtio",
    "0x1234": "QEMU",
    "0x15ad": "VMware",
    "0x80ee": "VirtualBox",
}

CARD_RE = re.compile(r"^card\d+$")

# Vulkan ICD manifests by vendor (Mesa and NVIDIA file names).
VULKAN_ICDS = {
    "AMD": ("radeon_icd",),
    "Intel": ("intel_icd", "intel_hasvk_icd"),
    "NVIDIA": ("nvidia_icd", "nouveau_icd"),
}

# VA-API user-space drivers by vendor.
VAAPI_DRIVERS = {
    "AMD": ("radeonsi_drv_video.so",),
    "Intel": ("iHD_drv_video.so", "i965_drv_video.so"),
    "NVIDIA": ("nvidia_drv_video.so", "nouveau_drv_video.so"),
}

# RADV / ANV code names -> architecture.
AMD_CODENAMES = {
    **dict.fromkeys(("TAHITI", "PITCAIRN", "VERDE", "OLAND", "HAINAN"), "GCN 1"),
    **dict.fromkeys(("BONAIRE", "HAWAII", "KAVERI", "KABINI", "MULLINS"), "GCN 2"),
    **dict.fromkeys(("TONGA", "ICELAND", "FIJI", "CARRIZO", "STONEY"), "GCN 3"),
    **dict.fromkeys(("POLARIS10", "POLARIS11", "POLARIS12", "VEGAM"), "GCN 4 (Polaris)"),
    **dict.fromkeys(("VEGA10", "VEGA12", "VEGA20", "RAVEN", "RAVEN2", "RENOIR"), "GCN 5 (Vega)"),
    **dict.fromkeys(("NAVI10", "NAVI12", "NAVI14"), "RDNA 1"),
    **dict.fromkeys(("NAVI21", "NAVI22", "NAVI23", "NAVI24", "VANGOGH", "REMBRANDT", "RAPHAEL", "MENDOCINO", "RAPHAEL_MENDOCINO"), "RDNA 2"),
    **dict.fromkeys(("NAVI31", "NAVI32", "NAVI33", "PHOENIX"), "RDNA 3"),
    **dict.fromkeys(("NAVI44", "NAVI48"), "RDNA 4"),
}
INTEL_CODENAMES = {
    **dict.fromkeys(("IVB", "BYT", "HSW"), "Gen7"),
    **dict.fromkeys(("BDW", "CHV"), "Gen8"),
    **dict.fromkeys(("SKL", "BXT", "KBL", "GLK", "CFL", "WHL", "CML", "AML"), "Gen9"),
    **dict.fromkeys(("ICL", "EHL", "JSL"), "Gen11"),
    **dict.fromkeys(("TGL", "RKL", "ADL", "ADL-S", "ADL-P", "ADL-N", "RPL", "RPL-S", "RPL-P", "DG1"), "Xe-LP"),
    **dict.fromkeys(("DG2", "ACM"), "Xe-HPG (Arc Alchemist)"),
    **dict.fromkeys(("MTL", "ARL"), "Xe-LPG"),
    **dict.fromkeys(("LNL", "BMG"), "Xe2"),
    **dict.fromkeys(("PTL",), "Xe3"),
}


def amd_architecture(codename: Optional[str]) -> Optional[str]:
    if not codename:
        return None
    if codename in AMD_CODENAMES:
        return AMD_CODENAMES[codename]
    match = re.match(r"GFX(\d{3,4})", codename)
    if match:
        gfx = int(match.group(1))
        for low, high, arch in ((1010, 1029, "RDNA 1"), (1030, 1099, "RDNA 2"), (1100, 1149, "RDNA 3"),
                                (1150, 1199, "RDNA 3.5"), (1200, 1299, "RDNA 4")):
            if low <= gfx <= high:
                return arch
    return None


def intel_architecture(codename: Optional[str]) -> Optional[str]:
    if not codename:
        return None
    key = codename.split()[0]
    return INTEL_CODENAMES.get(key) or INTEL_CODENAMES.get(key.split("-")[0])


def nvidia_architecture(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    for pattern, arch in (
        (r"RTX\s*50\d\d", "Blackwell"), (r"RTX\s*40\d\d", "Ada Lovelace"), (r"RTX\s*30\d\d", "Ampere"),
        (r"RTX\s*20\d\d|GTX\s*16\d\d", "Turing"), (r"GTX\s*10\d\d", "Pascal"), (r"GTX\s*9\d\d", "Maxwell"),
    ):
        if re.search(pattern, name, re.IGNORECASE):
            return arch
    return None


@dataclass
class Gpu:
    card: str
    pci_slot: Optional[str]
    vendor_id: Optional[str]
    device_id: Optional[str]
    vendor: str
    name: Optional[str] = None
    driver: Optional[str] = None
    boot_vga: Optional[bool] = None
    runtime_status: Optional[str] = None
    connectors: List[str] = field(default_factory=list)
    connected_outputs: List[str] = field(default_factory=list)
    render_node: Optional[str] = None
    kind: Optional[str] = None
    codename: Optional[str] = None
    architecture: Optional[str] = None
    vulkan: Optional[Dict[str, object]] = None
    opengl: Optional[Dict[str, object]] = None
    vaapi: Optional[Dict[str, object]] = None
    metrics: Dict[str, object] = field(default_factory=dict)
    capabilities: List[Capability] = field(default_factory=list)

    @property
    def sleeping(self) -> bool:
        return self.runtime_status == "suspended"

    @property
    def device_path(self) -> str:
        return f"/sys/class/drm/{self.card}/device"

    def to_dict(self) -> Dict[str, object]:
        data = {k: v for k, v in self.__dict__.items() if k != "capabilities"}
        data["sleeping"] = self.sleeping
        data["capabilities"] = [c.to_dict() for c in self.capabilities]
        return data


# --- Backends ------------------------------------------------------------------------------

def _first_hwmon(device: Path) -> Optional[Path]:
    hwmons = sorted((device / "hwmon").glob("hwmon*")) if (device / "hwmon").is_dir() else []
    return hwmons[0] if hwmons else None


class GpuBackend:
    vendor = "generic"

    def metrics(self, gpu: Gpu, root: str = "/", runner: Runner = run) -> Dict[str, object]:
        if gpu.sleeping:
            return {"state": "sleeping (powered down, not woken for monitoring)"}
        device = under(root, gpu.device_path)
        result: Dict[str, object] = {"state": "active"}
        hwmon = _first_hwmon(device)
        if hwmon is not None:
            temp = read_int(hwmon / "temp1_input")
            result["temperature_c"] = round(temp / 1000, 1) if temp is not None else None
        return result

    def power_capability(self, gpu: Gpu, root: str = "/") -> Optional[Capability]:
        return None

    def notes(self, gpu: Gpu, context: Dict[str, object]) -> List[Note]:
        notes: List[Note] = []
        if not gpu.driver:
            notes.append(Note("fail", "No kernel driver is bound to this GPU.", gpu.card))
        return notes


class AmdBackend(GpuBackend):
    vendor = "AMD"

    def metrics(self, gpu: Gpu, root: str = "/", runner: Runner = run) -> Dict[str, object]:
        result = super().metrics(gpu, root, runner)
        if gpu.sleeping:
            return result
        device = under(root, gpu.device_path)
        result["usage_percent"] = read_int(device / "gpu_busy_percent")
        result["vram_used_bytes"] = read_int(device / "mem_info_vram_used")
        result["vram_total_bytes"] = read_int(device / "mem_info_vram_total")
        hwmon = _first_hwmon(device)
        if hwmon is not None:
            power = read_int(hwmon / "power1_average")
            if power is None:
                power = read_int(hwmon / "power1_input")
            watts = round(power / 1_000_000, 1) if power is not None else None
            # On an APU (only APUs have the northbridge voltage sensor vddnb), power1 is
            # the power of the whole processor package (PPT), not of the GPU alone.
            if read_text(hwmon / "in1_label") == "vddnb":
                result["power_w"] = None
                result["package_power_w"] = watts
            else:
                result["power_w"] = watts
        sclk = read_text(device / "pp_dpm_sclk")
        if sclk:
            current = next((line for line in sclk.splitlines() if line.rstrip().endswith("*")), None)
            match = re.search(r"(\d+)\s*Mhz", current or "", re.IGNORECASE)
            result["clock_mhz"] = int(match.group(1)) if match else None
        return result

    def power_capability(self, gpu: Gpu, root: str = "/") -> Optional[Capability]:
        device = under(root, gpu.device_path)
        cap = Capability("gpu-power", "GPU power management (amdgpu)")
        level = read_text(device / "power_dpm_force_performance_level")
        cap.driver = gpu.driver == "amdgpu"
        cap.available = level is not None
        if level is not None:
            cap.enabled = True
            cap.evidence.append(f"performance level: {level}")
        if (device / "pp_power_profile_mode").exists():
            cap.evidence.append("power profiles exposed (pp_power_profile_mode)")
        return cap

    def notes(self, gpu: Gpu, context: Dict[str, object]) -> List[Note]:
        notes = super().notes(gpu, context)
        if gpu.driver == "radeon":
            notes.append(Note("warn", "This older GPU uses the legacy radeon driver: no Vulkan, so most modern games and Proton will not run on it.", gpu.card))
        return notes


class IntelBackend(GpuBackend):
    vendor = "Intel"

    def metrics(self, gpu: Gpu, root: str = "/", runner: Runner = run) -> Dict[str, object]:
        result = super().metrics(gpu, root, runner)
        if gpu.sleeping:
            return result
        card = under(root, f"/sys/class/drm/{gpu.card}")
        freq = read_int(card / "gt_cur_freq_mhz")  # i915
        if freq is None:
            freq = read_int(under(root, gpu.device_path) / "tile0" / "gt0" / "freq0" / "cur_freq")  # xe
        result["clock_mhz"] = freq
        result["usage_percent"] = None  # i915/xe expose busyness only through perf events
        return result

    def power_capability(self, gpu: Gpu, root: str = "/") -> Optional[Capability]:
        card = under(root, f"/sys/class/drm/{gpu.card}")
        cap = Capability("gpu-power", "GPU power management (Intel)")
        cap.driver = gpu.driver in ("i915", "xe")
        rc6 = read_int(card / "power" / "rc6_enable")
        if rc6 is not None:
            cap.available = True
            cap.enabled = rc6 > 0
            cap.evidence.append(f"RC6 power saving: {'on' if rc6 else 'off'}")
        return cap


class NvidiaBackend(GpuBackend):
    vendor = "NVIDIA"
    QUERY = "pci.bus_id,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw,clocks.gr,driver_version"

    def metrics(self, gpu: Gpu, root: str = "/", runner: Runner = run) -> Dict[str, object]:
        if gpu.driver != "nvidia":
            return super().metrics(gpu, root, runner)
        if gpu.sleeping:
            return {"state": "sleeping (powered down, not woken for monitoring)"}
        res = runner(["nvidia-smi", f"--query-gpu={self.QUERY}", "--format=csv,noheader,nounits"], timeout=8)
        result: Dict[str, object] = {"state": "active"}
        if not res.ok:
            result["error"] = (res.stderr or "nvidia-smi failed").strip()
            return result
        for line in res.stdout.splitlines():
            fields = [f.strip() for f in line.split(",")]
            if len(fields) < 8:
                continue
            bus = fields[0].lower()[-12:]
            if gpu.pci_slot and bus != gpu.pci_slot.lower()[-12:]:
                continue

            def num(value: str) -> Optional[float]:
                try:
                    return float(value)
                except ValueError:
                    return None

            result.update({
                "usage_percent": num(fields[1]),
                "temperature_c": num(fields[2]),
                "vram_used_bytes": int(num(fields[3]) * 1048576) if num(fields[3]) is not None else None,
                "vram_total_bytes": int(num(fields[4]) * 1048576) if num(fields[4]) is not None else None,
                "power_w": num(fields[5]),
                "clock_mhz": num(fields[6]),
                "driver_version": fields[7],
            })
            break
        return result

    def notes(self, gpu: Gpu, context: Dict[str, object]) -> List[Note]:
        notes = super().notes(gpu, context)
        edition = str(context.get("edition") or "")
        if "nvidia" not in edition:
            notes.append(Note("warn", "This NebulaOS edition has no NVIDIA driver. Use the NVIDIA edition "
                              "(image name ending in -nvidia) for gaming on this GPU.", gpu.card))
        if gpu.driver == "nouveau":
            notes.append(Note("info", "The open-source nouveau driver is in use; gaming performance and features are limited.", gpu.card))
        if gpu.architecture in ("Pascal", "Maxwell"):
            notes.append(Note("info", f"{gpu.architecture} GPUs are not supported by NVIDIA's open kernel modules; "
                              "check that your NVIDIA image still supports this generation.", gpu.card))
        modeset = context.get("nvidia_drm_modeset")
        if gpu.driver == "nvidia" and modeset is False:
            notes.append(Note("warn", "nvidia-drm modeset is off, which Wayland sessions and Gamescope need.", gpu.card))
        return notes


BACKENDS: Dict[str, GpuBackend] = {"AMD": AmdBackend(), "Intel": IntelBackend(), "NVIDIA": NvidiaBackend()}


def backend_for(gpu: Gpu) -> GpuBackend:
    return BACKENDS.get(gpu.vendor, GpuBackend())


# --- Detection -------------------------------------------------------------------------------

PCI_IDS = ("usr/share/hwdata/pci.ids", "usr/share/misc/pci.ids")


def _hex_id(value: Optional[str]) -> str:
    return (value or "").lower().removeprefix("0x")


def pci_ids_names(ids: List[Tuple[Optional[str], Optional[str]]], root: str = "/") -> Dict[Tuple[str, str], str]:
    """{(vendor, device): name} for PCI IDs such as ("0x1002", "0x73ff"), from the PCI ID
    database, where `lspci` gets its names too. Only a file is read: `lspci` reads every
    device's configuration space, and that wakes a GPU sleeping in D3cold."""
    wanted = {(_hex_id(v), _hex_id(d)) for v, d in ids if v and d}
    path = next((p for p in (under(root, f) for f in PCI_IDS) if p.is_file()), None)
    names: Dict[Tuple[str, str], str] = {}
    if not wanted or path is None:
        return names
    vendor = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("C "):  # device classes follow the vendor list
                break
            if not line.startswith("\t"):
                vendor = line[:4].lower()
            elif vendor and not line.startswith("\t\t") and (vendor, line[1:5].lower()) in wanted:
                names[(vendor, line[1:5].lower())] = line[5:].strip()
                if len(names) == len(wanted):
                    break
    return names


def detect_gpus(root: str = "/", runner: Runner = run, with_names: bool = True) -> List[Gpu]:
    drm = under(root, "sys/class/drm")
    try:
        entries = sorted(p.name for p in drm.iterdir())
    except OSError:
        return []
    gpus: List[Gpu] = []
    for card in (e for e in entries if CARD_RE.match(e)):
        device = drm / card / "device"
        vendor_id = read_text(device / "vendor")
        driver_link = device / "driver"
        driver = os.path.basename(os.readlink(driver_link)) if driver_link.is_symlink() else None
        slot = Path(os.path.realpath(device)).name if device.exists() else None
        conns = [e[len(card) + 1:] for e in entries if e.startswith(card + "-") and "Writeback" not in e]
        connected = [c for c in conns if read_text(drm / f"{card}-{c}" / "status") == "connected"]
        render = None
        if (device / "drm").is_dir():
            render = next((p.name for p in sorted((device / "drm").glob("renderD*"))), None)
        boot_vga = read_int(device / "boot_vga")
        gpus.append(Gpu(
            card=card,
            pci_slot=slot,
            vendor_id=vendor_id,
            device_id=read_text(device / "device"),
            vendor=VENDORS.get(vendor_id or "", vendor_id or "unknown"),
            driver=driver,
            boot_vga=None if boot_vga is None else boot_vga == 1,
            runtime_status=read_text(device / "power" / "runtime_status"),
            connectors=conns,
            connected_outputs=connected,
            render_node=render,
        ))
    if with_names:
        names = pci_ids_names([(g.vendor_id, g.device_id) for g in gpus], root)
        for g in gpus:
            g.name = names.get((_hex_id(g.vendor_id), _hex_id(g.device_id)))
    return gpus


# --- Probes (may wake GPUs) --------------------------------------------------------------------

def vulkan_devices(runner: Runner = run) -> Optional[List[Dict[str, str]]]:
    """Physical devices from `vulkaninfo --summary`, or None if it cannot run."""
    res = runner(["vulkaninfo", "--summary"], timeout=20)
    if not res.ok:
        return None
    devices: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    for line in res.stdout.splitlines():
        if re.match(r"^GPU\d+:", line.strip()):
            current = {}
            devices.append(current)
            continue
        if current is not None and "=" in line:
            key, _, value = line.partition("=")
            current[key.strip()] = value.strip()
    return devices


def opengl_info(gpu: Gpu, runner: Runner = run) -> Optional[Dict[str, object]]:
    """OpenGL renderer and version for one GPU via `glxinfo -B` (needs a display)."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) or not gpu.pci_slot:
        return None
    if gpu.driver == "nvidia":
        env = {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia"}
    else:
        env = {"DRI_PRIME": "pci-" + re.sub(r"[:.]", "_", gpu.pci_slot)}
    res = runner(["glxinfo", "-B"], timeout=20, env=env)
    if not res.ok:
        return {"ok": False, "error": (res.stderr or "glxinfo failed").strip()[:200]}
    info: Dict[str, object] = {"ok": True}
    for line in res.stdout.splitlines():
        key, _, value = line.partition(":")
        key = key.strip()
        if key == "OpenGL renderer string":
            info["renderer"] = value.strip()
        elif key == "OpenGL core profile version string":
            info["core_version"] = value.strip()
        elif key == "OpenGL version string":
            info["version"] = value.strip()
    return info


_VA_CODECS = (("H264", "H.264"), ("HEVC", "HEVC"), ("AV1", "AV1"), ("VP9", "VP9"), ("VP8", "VP8"),
              ("MPEG2", "MPEG-2"), ("VC1", "VC-1"), ("JPEG", "JPEG"))


def vaapi_info(gpu: Gpu, runner: Runner = run) -> Optional[Dict[str, object]]:
    if not gpu.render_node:
        return None
    res = runner(["vainfo", "--display", "drm", "--device", f"/dev/dri/{gpu.render_node}"], timeout=15)
    if res.returncode == 127:
        return None
    text = res.stdout + "\n" + res.stderr
    decode, encode = set(), set()
    driver = None
    for line in text.splitlines():
        if "Driver version:" in line:
            driver = line.split("Driver version:", 1)[1].strip()
        match = re.search(r"VAProfile(\w+)\s*:\s*VAEntrypoint(\w+)", line)
        if match:
            profile, entry = match.groups()
            codec = next((label for key, label in _VA_CODECS if profile.upper().startswith(key)), None)
            if codec:
                (decode if entry == "VLD" else encode if entry.startswith("Enc") else set()).add(codec)
    return {"ok": res.ok and bool(decode or encode), "driver": driver,
            "decode": sorted(decode), "encode": sorted(encode)}


def _codename(device_name: str) -> Optional[str]:
    match = re.search(r"\((?:RADV\s+)?([A-Z0-9_\- ]+?)\)\s*$", device_name or "")
    return match.group(1).strip() if match else None


def _icd_present(vendor: str, icd_dir: Path) -> Optional[bool]:
    prefixes = VULKAN_ICDS.get(vendor)
    if not prefixes or not icd_dir.is_dir():
        return None
    return any(p.name.startswith(prefixes) for p in icd_dir.iterdir())


def _vaapi_driver_present(vendor: str, root: str) -> Optional[bool]:
    names = VAAPI_DRIVERS.get(vendor)
    if not names:
        return None
    dirs = [under(root, d) for d in ("usr/lib64/dri", "usr/lib/x86_64-linux-gnu/dri", "usr/lib/dri", "usr/lib64/dri-nonfree", "usr/lib64/dri-freeworld")]
    return any((d / n).exists() for d in dirs for n in names)


def enrich(gpus: List[Gpu], root: str = "/", runner: Runner = run, probe: bool = True) -> None:
    """Fill in metrics, probes, architecture and capabilities for each GPU."""
    vk = vulkan_devices(runner) if probe else None
    icd_dir = under(root, "usr/share/vulkan/icd.d")
    used: set = set()  # each Vulkan device belongs to one GPU, even with two identical cards
    for gpu in gpus:
        backend = backend_for(gpu)
        gpu.metrics = backend.metrics(gpu, root, runner)

        match = None
        if vk is not None:
            for index, dev in enumerate(vk):
                if index not in used and dev.get("vendorID", "").lower() == (gpu.vendor_id or "").lower() and \
                        dev.get("deviceID", "").lower() == (gpu.device_id or "").lower():
                    match = dev
                    used.add(index)
                    break
        if match:
            gpu.vulkan = {
                "device_name": match.get("deviceName"),
                "driver": match.get("driverName"),
                "driver_info": match.get("driverInfo"),
                "api_version": match.get("apiVersion"),
                "device_type": match.get("deviceType"),
            }
            device_type = match.get("deviceType", "")
            gpu.kind = "integrated" if "INTEGRATED" in device_type else "discrete" if "DISCRETE" in device_type else None
            gpu.codename = _codename(match.get("deviceName", ""))
            if gpu.name is None:
                gpu.name = match.get("deviceName")
        if gpu.vendor == "AMD":
            gpu.architecture = amd_architecture(gpu.codename)
        elif gpu.vendor == "Intel":
            gpu.architecture = intel_architecture(gpu.codename)
        elif gpu.vendor == "NVIDIA":
            gpu.architecture = nvidia_architecture((gpu.vulkan or {}).get("device_name") or gpu.name)

        vulkan = Capability("vulkan", "Vulkan")
        vulkan.driver = _icd_present(gpu.vendor, icd_dir)
        if vk is None:
            vulkan.evidence.append("vulkaninfo not run" if not probe else "vulkaninfo unavailable or failed")
        elif match:
            vulkan.hardware = vulkan.available = vulkan.enabled = vulkan.verified = True
            vulkan.evidence.append(f"vulkaninfo enumerated the device: {match.get('driverName')} {match.get('driverInfo', '')}".strip())
        else:
            vulkan.available = False
            vulkan.evidence.append("vulkaninfo ran but did not list this GPU")
        gpu.capabilities.append(vulkan)

        opengl = Capability("opengl", "OpenGL")
        opengl.driver = bool(gpu.driver) or None
        if probe:
            gpu.opengl = opengl_info(gpu, runner)
        if gpu.opengl is None:
            opengl.evidence.append("not probed (needs a graphical session)" if probe else "not probed")
        elif gpu.opengl.get("ok") and gpu.opengl.get("renderer"):
            opengl.hardware = opengl.available = opengl.enabled = opengl.verified = True
            opengl.evidence.append(f"glxinfo rendered on: {gpu.opengl['renderer']}")
        else:
            opengl.available = False
            opengl.evidence.append(f"glxinfo failed: {gpu.opengl.get('error', 'no renderer')}")
        gpu.capabilities.append(opengl)

        vaapi = Capability("vaapi", "Hardware video acceleration (VA-API)")
        vaapi.driver = _vaapi_driver_present(gpu.vendor, root)
        if probe:
            gpu.vaapi = vaapi_info(gpu, runner)
        if gpu.vaapi is None:
            vaapi.evidence.append("not probed")
        elif gpu.vaapi.get("ok"):
            vaapi.hardware = vaapi.available = vaapi.enabled = vaapi.verified = True
            vaapi.evidence.append(f"decode: {', '.join(gpu.vaapi['decode']) or 'none'}; encode: {', '.join(gpu.vaapi['encode']) or 'none'}")
        else:
            vaapi.available = False
            vaapi.evidence.append("vainfo found no usable profiles")
        gpu.capabilities.append(vaapi)

        power = backend.power_capability(gpu, root)
        if power is not None:
            gpu.capabilities.append(power)
