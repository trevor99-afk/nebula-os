import json
import random
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import FakeRunner, make_edid, ok, write
from nebula import display


def mutter_json(color_mode=0, supported=(0,), current_variable=False, vrr_modes=True):
    def v(t, d):
        return {"type": t, "data": d}
    modes = [["2560x1440@143.998", 2560, 1440, 143.998, 1.0, [1.0],
              {"is-current": v("b", not current_variable), "refresh-rate-mode": v("s", "fixed")}]]
    if vrr_modes:
        modes.append(["2560x1440@143.998+vrr", 2560, 1440, 143.998, 1.0, [1.0],
                      {"is-current": v("b", current_variable), "refresh-rate-mode": v("s", "variable")}])
    monitor = [["DP-1", "NEB", "0x1234", "0x00000000"], modes,
               {"display-name": v("s", "Nebula 27"), "is-builtin": v("b", False),
                "color-mode": v("u", color_mode), "supported-color-modes": v("au", list(supported)),
                "min-refresh-rate": v("i", 48)}]
    logical = [[0, 0, 1.0, 0, True, [["DP-1", "NEB", "0x1234", "0x00000000"]], {}]]
    return json.dumps({"type": "...", "data": [1, [monitor], logical, {}]})


class ParseEdid(unittest.TestCase):
    def test_basic_fields(self):
        e = display.parse_edid(make_edid())
        self.assertEqual(e["manufacturer"], "NEB")
        self.assertEqual(e["name"], "NEBULA TEST")
        self.assertEqual(e["version"], "1.4")
        self.assertEqual(e["bits_per_color"], 10)
        self.assertEqual(e["interface"], "DisplayPort")
        self.assertEqual((e["native_mode"]["width"], e["native_mode"]["height"]), (2560, 1440))
        self.assertAlmostEqual(e["native_mode"]["refresh_hz"], 144.0, delta=0.1)
        self.assertEqual(e["range_limits"]["min_v_hz"], 48)
        self.assertEqual(e["range_limits"]["max_v_hz"], 144)
        self.assertTrue(e["range_limits"]["range_limits_only"])

    def test_hdr_and_freesync_extension(self):
        e = display.parse_edid(make_edid(hdr=True, freesync=True))
        hdr = e["hdr_static_metadata"]
        self.assertTrue(hdr["eotf_pq"])
        self.assertTrue(hdr["eotf_hlg"])
        self.assertAlmostEqual(hdr["max_luminance_nits"], 603, delta=2)
        self.assertTrue(e["amd_freesync_block"])
        self.assertTrue(e["colorimetry"]["bt2020_rgb"])
        self.assertTrue(e["colorimetry"]["dci_p3"])

    def test_rejects_garbage(self):
        self.assertIsNone(display.parse_edid(b""))
        self.assertIsNone(display.parse_edid(b"\x00" * 128))

    def test_data_block_running_past_its_area_is_ignored(self):
        edid = bytearray(make_edid(hdr=True))
        cta = edid[128:]
        cta[2], cta[126] = 127, (3 << 5) | 31  # vendor block at the last byte claiming 31 bytes
        e = display.parse_edid(bytes(edid[:128]) + bytes(cta))
        self.assertTrue(e["hdr_static_metadata"]["eotf_pq"])  # blocks before the corrupt one still count

    def test_random_extension_blocks_never_raise(self):
        rng = random.Random(20261121)
        base = bytearray(make_edid()[:128])
        base[126] = 1
        for i in range(3000):
            block = bytearray(rng.getrandbits(8) for _ in range(128))
            block[0] = 0x02 if i % 3 else 0x70  # CTA-861 or DisplayID
            if i % 2:
                block[2] = 127  # data blocks reach the end of the block, where truncation bites
            self.assertIsNotNone(display.parse_edid(bytes(base) + bytes(block)))


class Capabilities(unittest.TestCase):
    def test_vrr_available_but_off(self):
        d = {"connector": "DP-1", "edid": display.parse_edid(make_edid()),
             "compositor": {"vrr_modes_available": True, "current_mode": {"variable": False}}}
        c = display.vrr_capability(d)
        self.assertTrue(c.hardware)
        self.assertEqual(c.status(), "available, turned off")

    def test_vrr_not_claimed_for_fixed_range_hdmi(self):
        d = {"connector": "HDMI-A-1", "edid": display.parse_edid(make_edid(range_only=False))}
        self.assertIsNone(display.vrr_capability(d).hardware)

    def test_hdr_evidence_names_the_curves(self):
        c = display.hdr_capability({"edid": display.parse_edid(make_edid(hdr=True))})
        self.assertRegex(c.evidence[0], r"^EDID HDR metadata: PQ, HLG, peak \d+ nits$")

    def test_hdr_missing_from_edid(self):
        c = display.hdr_capability({"edid": display.parse_edid(make_edid())})
        self.assertFalse(c.hardware)

    def test_hdr_enabled(self):
        d = {"edid": display.parse_edid(make_edid(hdr=True)),
             "compositor": {"hdr_mode_available": True, "hdr_enabled": True, "supported_color_modes": []}}
        c = display.hdr_capability(d)
        self.assertEqual(c.level(), "enabled")


class Compositor(unittest.TestCase):
    def test_mutter_state(self):
        runner = FakeRunner({("busctl", "--user"): ok(mutter_json(color_mode=1, supported=(0, 1)))})
        state = display.mutter_state(runner)["DP-1"]
        self.assertEqual(state["display_name"], "Nebula 27")
        self.assertTrue(state["vrr_modes_available"])
        self.assertFalse(state["current_mode"]["variable"])
        self.assertTrue(state["hdr_mode_available"])
        self.assertTrue(state["hdr_enabled"])
        self.assertTrue(state["primary"])

    def test_unknown_color_mode_is_reported_raw(self):
        runner = FakeRunner({("busctl", "--user"): ok(mutter_json(supported=(0, 2)))})
        state = display.mutter_state(runner)["DP-1"]
        self.assertEqual(state["supported_color_modes"], ["default (SDR)", 2])
        self.assertFalse(state["hdr_mode_available"])

    def test_not_gnome(self):
        self.assertIsNone(display.mutter_state(FakeRunner()))

    def test_malformed_nested_state_is_unknown(self):
        malformed = (
            json.dumps({"data": [1, [], [[0]], {}]}),
            json.dumps({"data": [1, [[[
                "DP-1", "NEB", "0x1234", "0x00000000"
            ], [["mode", 1920, 1080, "not-a-refresh-rate", 1.0, [1.0], {}]], {}]], [], {}]}),
        )
        for raw in malformed:
            state = display.mutter_state(FakeRunner({("busctl", "--user"): ok(raw)}))
            self.assertIsNone(state, raw)


class Connectors(unittest.TestCase):
    def test_connected_outputs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            drm = Path(tmp) / "sys" / "class" / "drm"
            write(drm / "card0-DP-1" / "status", "connected\n")
            (drm / "card0-DP-1" / "edid").write_bytes(make_edid())
            write(drm / "card0-DP-1" / "modes", "2560x1440\n1920x1080\n")
            write(drm / "card0-HDMI-A-1" / "status", "disconnected\n")
            write(drm / "card0-Writeback-1" / "status", "connected\n")
            result = display.displays(tmp, FakeRunner(), use_compositor=False)
        self.assertEqual([d["connector"] for d in result], ["DP-1"])
        self.assertEqual(result[0]["modes"][0], "2560x1440")
        self.assertEqual({c["id"] for c in result[0]["capabilities"]}, {"vrr", "hdr"})


if __name__ == "__main__":
    unittest.main()
