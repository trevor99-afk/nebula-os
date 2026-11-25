"""Display detection: connectors, EDID, and the compositor's live state.

Sources, from most to least authoritative for *current* state:
  1. GNOME/Mutter's DisplayConfig D-Bus API (current mode, VRR and HDR state)
  2. The monitor's EDID (what the display itself advertises)
  3. /sys/class/drm connector status and mode lists
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .capabilities import Capability
from .util import Runner, read_text, run, under

EDID_HEADER = bytes.fromhex("00ffffffffffff00")

# Mutter's MetaColorMode values. Only values whose meaning is known are named;
# anything else is reported raw instead of being guessed.
MUTTER_COLOR_MODES = {0: "default (SDR)", 1: "BT.2100 (HDR)"}
MUTTER_HDR_MODE = 1

_CONNECTOR_RE = re.compile(r"^(card\d+)-(.+)$")


# --- EDID -------------------------------------------------------------------------

def _range_limits(d: bytes, edid_14: bool) -> Dict[str, object]:
    flags = d[4] if edid_14 else 0
    vmin = d[5] + (255 if (flags & 0x03) == 0x03 else 0)
    vmax = d[6] + (255 if flags & 0x02 else 0)
    hmin = d[7] + (255 if (flags & 0x0C) == 0x0C else 0)
    hmax = d[8] + (255 if flags & 0x08 else 0)
    return {
        "min_v_hz": vmin,
        "max_v_hz": vmax,
        "min_h_khz": hmin,
        "max_h_khz": hmax,
        "max_pixel_clock_mhz": d[9] * 10,
        "range_limits_only": d[10] == 0x01,
    }


def _parse_cta(block: bytes, out: Dict[str, object]) -> None:
    out["cta861"] = True
    end = block[2]
    if not 4 <= end <= 127:
        return
    pos = 4
    while pos < end:
        header = block[pos]
        tag, length = header >> 5, header & 0x1F
        if pos + 1 + length > end:  # runs past the data block area: corrupt EDID, stop here
            break
        payload = block[pos + 1:pos + 1 + length]
        if tag == 3 and length >= 3:  # vendor-specific data block
            oui = payload[0] | (payload[1] << 8) | (payload[2] << 16)
            if oui == 0x00001A:
                out["amd_freesync_block"] = True
            elif oui == 0xC45DD8:
                out["hdmi_forum_block"] = True
            elif oui == 0x000C03:
                out["hdmi"] = True
        elif tag == 7 and length >= 2:  # extended tag
            ext = payload[0]
            if ext == 0x06 and length >= 3:  # HDR static metadata
                eotf = payload[1]
                hdr: Dict[str, object] = {
                    "eotf_sdr": bool(eotf & 0x01),
                    "eotf_hdr_gamma": bool(eotf & 0x02),
                    "eotf_pq": bool(eotf & 0x04),
                    "eotf_hlg": bool(eotf & 0x08),
                }
                if length >= 4 and payload[3]:
                    hdr["max_luminance_nits"] = round(50 * 2 ** (payload[3] / 32))
                if length >= 5 and payload[4]:
                    hdr["max_frame_average_nits"] = round(50 * 2 ** (payload[4] / 32))
                if length >= 6 and "max_luminance_nits" in hdr:
                    max_nits = 50 * 2 ** (payload[3] / 32)
                    hdr["min_luminance_nits"] = round(max_nits * (payload[5] / 255) ** 2 / 100, 4)
                out["hdr_static_metadata"] = hdr
            elif ext == 0x05:  # colorimetry
                c = payload[1]
                out["colorimetry"] = {
                    "bt2020_rgb": bool(c & 0x80),
                    "bt2020_ycc": bool(c & 0x40),
                    "dci_p3": bool(payload[2] & 0x80) if length >= 3 else False,
                }
        pos += 1 + length


def _parse_displayid(block: bytes, out: Dict[str, object]) -> None:
    out["displayid"] = True
    length = block[2]
    pos, end = 5, min(5 + length, 127)
    while pos + 3 <= end:
        tag, blen = block[pos], block[pos + 2]
        if tag == 0x2B:  # DisplayID 2.x Adaptive-Sync data block
            out["displayid_adaptive_sync_block"] = True
        pos += 3 + blen


def parse_edid(data: bytes) -> Optional[Dict[str, object]]:
    """Decode the parts of an EDID NebulaOS needs. Serial numbers are skipped."""
    if len(data) < 128 or data[:8] != EDID_HEADER:
        return None
    mfg = int.from_bytes(data[8:10], "big")
    manufacturer = "".join(chr(((mfg >> shift) & 0x1F) + 64) for shift in (10, 5, 0))
    edid_14 = data[18] == 1 and data[19] >= 4
    out: Dict[str, object] = {
        "manufacturer": manufacturer,
        "product_code": f"0x{int.from_bytes(data[10:12], 'little'):04x}",
        "version": f"{data[18]}.{data[19]}",
        "digital": bool(data[20] & 0x80),
        "size_mm": [data[21] * 10, data[22] * 10] if data[21] and data[22] else None,
        "name": None,
        "native_mode": None,
        "range_limits": None,
    }
    if out["digital"] and edid_14:
        out["bits_per_color"] = {1: 6, 2: 8, 3: 10, 4: 12, 5: 14, 6: 16}.get((data[20] >> 4) & 0x07)
        out["interface"] = {1: "DVI", 2: "HDMI-a", 3: "HDMI-b", 4: "MDDI", 5: "DisplayPort"}.get(data[20] & 0x0F)
    for offset in (54, 72, 90, 108):
        d = data[offset:offset + 18]
        pixel_clock = int.from_bytes(d[0:2], "little")
        if pixel_clock:
            if out["native_mode"] is None:  # first detailed timing = preferred mode
                h_active = d[2] | ((d[4] & 0xF0) << 4)
                h_blank = d[3] | ((d[4] & 0x0F) << 8)
                v_active = d[5] | ((d[7] & 0xF0) << 4)
                v_blank = d[6] | ((d[7] & 0x0F) << 8)
                h_total, v_total = h_active + h_blank, v_active + v_blank
                refresh = pixel_clock * 10000 / (h_total * v_total) if h_total and v_total else None
                out["native_mode"] = {
                    "width": h_active,
                    "height": v_active,
                    "refresh_hz": round(refresh, 3) if refresh else None,
                }
            continue
        tag = d[3]
        if tag == 0xFC:
            out["name"] = d[5:18].split(b"\n")[0].decode("ascii", "replace").strip() or None
        elif tag == 0xFD:
            out["range_limits"] = _range_limits(d, edid_14)
    for index in range(data[126]):
        block = data[128 * (index + 1):128 * (index + 2)]
        if len(block) < 128:
            break
        if block[0] == 0x02:
            _parse_cta(block, out)
        elif block[0] == 0x70:
            _parse_displayid(block, out)
    return out


# --- Compositor state (GNOME) -------------------------------------------------------

def _variant(value: object) -> object:
    return value.get("data") if isinstance(value, dict) and "data" in value else value


def _parse_mutter_state(raw: str) -> Optional[Dict[str, Dict[str, object]]]:
    try:
        _serial, monitors, logical, _props = json.loads(raw)["data"]
        primary = set()
        scales: Dict[str, float] = {}
        for item in logical:
            _x, _y, scale, _transform, is_primary, specs = item[:6]
            for spec in specs:
                scales[spec[0]] = scale
                if is_primary:
                    primary.add(spec[0])
        state: Dict[str, Dict[str, object]] = {}
        for spec, modes, props in monitors:
            connector, vendor, product, _serial_no = spec
            mprops = {k: _variant(v) for k, v in props.items()}
            current = None
            variable_available = False
            best_refresh = 0.0
            for mode in modes:
                _id, width, height, refresh, _pref_scale, _scales, mode_props = mode[:7]
                mp = {k: _variant(v) for k, v in mode_props.items()}
                variable = mp.get("refresh-rate-mode") == "variable"
                variable_available = variable_available or variable
                best_refresh = max(best_refresh, float(refresh))
                if mp.get("is-current"):
                    current = {"width": width, "height": height, "refresh_hz": round(float(refresh), 3), "variable": variable}
            color_mode = mprops.get("color-mode")
            supported = mprops.get("supported-color-modes") or []
            state[connector] = {
                "vendor": vendor,
                "product": product,
                "display_name": mprops.get("display-name"),
                "builtin": bool(mprops.get("is-builtin")),
                "primary": connector in primary,
                "scale": scales.get(connector),
                "current_mode": current,
                "max_refresh_hz": round(best_refresh, 3) if best_refresh else None,
                "vrr_modes_available": variable_available,
                "min_refresh_hz": mprops.get("min-refresh-rate"),
                "color_mode": MUTTER_COLOR_MODES.get(color_mode, color_mode),
                "supported_color_modes": [MUTTER_COLOR_MODES.get(m, m) for m in supported],
                "hdr_mode_available": MUTTER_HDR_MODE in supported,
                "hdr_enabled": color_mode == MUTTER_HDR_MODE,
            }
        return state
    except (ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError):
        # Mutter's versioned D-Bus payload is external input. A shape change or
        # partial reply should leave compositor data unknown, not break `nebula hw`.
        return None


def mutter_state(runner: Runner = run) -> Optional[Dict[str, Dict[str, object]]]:
    """{connector: state} from Mutter's DisplayConfig, or None outside GNOME."""
    res = runner(
        ["busctl", "--user", "--json=short", "call", "org.gnome.Mutter.DisplayConfig",
         "/org/gnome/Mutter/DisplayConfig", "org.gnome.Mutter.DisplayConfig", "GetCurrentState"],
        timeout=5,
    )
    return _parse_mutter_state(res.stdout) if res.ok else None


# --- Connectors ---------------------------------------------------------------------

def connectors(root: str = "/") -> List[Dict[str, object]]:
    """Connected outputs from /sys/class/drm with their decoded EDID."""
    result: List[Dict[str, object]] = []
    base = under(root, "sys/class/drm")
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return result
    for entry in entries:
        match = _CONNECTOR_RE.match(entry.name)
        if not match or match.group(2).startswith("Writeback"):
            continue
        if read_text(entry / "status") != "connected":
            continue
        try:
            edid_bytes = (entry / "edid").read_bytes()
        except OSError:
            edid_bytes = b""
        modes = (read_text(entry / "modes") or "").split()
        result.append({
            "card": match.group(1),
            "connector": match.group(2),
            "enabled": read_text(entry / "enabled"),
            "modes": modes,
            "edid": parse_edid(edid_bytes),
        })
    return result


# --- Capabilities -----------------------------------------------------------------------

def vrr_capability(display: Dict[str, object]) -> Capability:
    cap = Capability("vrr", "Variable refresh rate (FreeSync / Adaptive-Sync / G-SYNC Compatible)")
    edid = display.get("edid") or {}
    limits = edid.get("range_limits") if isinstance(edid, dict) else None
    connector = str(display.get("connector", ""))
    if isinstance(limits, dict) and limits.get("range_limits_only") and limits["max_v_hz"] - limits["min_v_hz"] >= 10 \
            and connector.startswith(("DP", "eDP")):
        cap.hardware = True
        cap.evidence.append(f"EDID advertises an Adaptive-Sync range of {limits['min_v_hz']}-{limits['max_v_hz']} Hz")
    if isinstance(edid, dict) and edid.get("amd_freesync_block"):
        cap.hardware = True
        cap.evidence.append("EDID contains an AMD FreeSync data block")
    if isinstance(edid, dict) and edid.get("displayid_adaptive_sync_block"):
        cap.hardware = True
        cap.evidence.append("EDID contains a DisplayID Adaptive-Sync block")
    compositor = display.get("compositor")
    if isinstance(compositor, dict):
        cap.driver = True
        cap.available = bool(compositor.get("vrr_modes_available"))
        cap.evidence.append("GNOME offers variable refresh modes" if cap.available else "GNOME offers no variable refresh modes for this display")
        current = compositor.get("current_mode") or {}
        if cap.available:
            cap.enabled = bool(current.get("variable"))
            cap.evidence.append("current mode uses variable refresh" if cap.enabled else "current mode uses a fixed refresh rate")
    else:
        cap.evidence.append("compositor state not available (not a GNOME session)")
    return cap


def hdr_capability(display: Dict[str, object]) -> Capability:
    cap = Capability("hdr", "HDR (BT.2100 / PQ)")
    edid = display.get("edid")
    if isinstance(edid, dict):
        hdr = edid.get("hdr_static_metadata")
        if isinstance(hdr, dict):
            cap.hardware = bool(hdr.get("eotf_pq") or hdr.get("eotf_hlg"))
            if cap.hardware:
                curves = ", ".join(label for key, label in (("eotf_pq", "PQ"), ("eotf_hlg", "HLG")) if hdr.get(key))
                nits = hdr.get("max_luminance_nits")
                cap.evidence.append(f"EDID HDR metadata: {curves}" + (f", peak {nits} nits" if nits else ""))
            else:
                cap.evidence.append("EDID HDR block lists no PQ/HLG support")
        else:
            cap.hardware = False
            cap.evidence.append("EDID has no HDR static metadata block")
    compositor = display.get("compositor")
    if isinstance(compositor, dict):
        cap.driver = True
        cap.available = bool(compositor.get("hdr_mode_available"))
        cap.enabled = bool(compositor.get("hdr_enabled")) if cap.available else None
        cap.evidence.append(f"GNOME color modes: {compositor.get('supported_color_modes')}")
    return cap


def displays(root: str = "/", runner: Runner = run, use_compositor: bool = True) -> List[Dict[str, object]]:
    """Connected displays with EDID, compositor state and VRR/HDR capabilities."""
    compositor = mutter_state(runner) if use_compositor else None
    result = []
    for conn in connectors(root):
        display = dict(conn)
        if compositor is not None:
            display["compositor"] = compositor.get(str(conn["connector"]))
        caps = [vrr_capability(display), hdr_capability(display)]
        display["capabilities"] = [c.to_dict() for c in caps]
        result.append(display)
    return result
