import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakeRunner, make_gpu, ok
from nebula import gpu

VULKANINFO = """==========
VULKANINFO
==========
Devices:
========
GPU0:
	apiVersion         = 1.4.354
	vendorID           = 0x1002
	deviceID           = 0x1638
	deviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
	deviceName         = AMD Radeon Graphics (RADV RENOIR)
	driverName         = radv
	driverInfo         = Mesa 26.2.7
GPU1:
	apiVersion         = 1.4.354
	vendorID           = 0x1002
	deviceID           = 0x73ff
	deviceType         = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU
	deviceName         = AMD Radeon RX 6600M (RADV NAVI23)
	driverName         = radv
	driverInfo         = Mesa 26.2.7
"""

VAINFO = """vainfo: Driver version: Mesa Gallium driver 26.2.7 for AMD Radeon RX 6600M
      VAProfileH264Main               :	VAEntrypointVLD
      VAProfileH264Main               :	VAEntrypointEncSlice
      VAProfileHEVCMain               :	VAEntrypointVLD
      VAProfileAV1Profile0            :	VAEntrypointVLD
"""

GLXINFO = "OpenGL renderer string: AMD Radeon RX 6600M (radeonsi, navi23)\nOpenGL core profile version string: 4.6 (Core Profile) Mesa 26.2.7\n"

LSPCI = '0000:03:00.0 "VGA compatible controller" "Advanced Micro Devices, Inc. [AMD/ATI]" "Navi 23 [Radeon RX 6600/6600 XT/6600M]" -rc3 "Lenovo" "x"\n' \
        '0000:07:00.0 "VGA compatible controller" "Advanced Micro Devices, Inc. [AMD/ATI]" "Cezanne [Radeon Vega Series]" -rc5 "Lenovo" "y"\n'


def hybrid_tree(tmp: Path, dgpu_runtime="suspended"):
    make_gpu(tmp, "card1", "0000:03:00.0", "0x1002", "0x73ff", "amdgpu", runtime=dgpu_runtime,
             busy=0, vram=(16 << 20, 8 << 30), temp=50000, render="renderD128", connectors={"DP-1": "disconnected"})
    make_gpu(tmp, "card2", "0000:07:00.0", "0x1002", "0x1638", "amdgpu", busy=12,
             vram=(1 << 30, 2 << 30), temp=49000, render="renderD129", connectors={"eDP-2": "connected"}, boot_vga=1)


class Detection(unittest.TestCase):
    def test_detects_two_gpus_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            hybrid_tree(Path(tmp))
            gpus = gpu.detect_gpus(tmp, FakeRunner({("lspci",): ok(LSPCI)}))
        self.assertEqual([g.card for g in gpus], ["card1", "card2"])
        dgpu, igpu = gpus
        self.assertEqual(dgpu.vendor, "AMD")
        self.assertEqual(dgpu.driver, "amdgpu")
        self.assertEqual(dgpu.pci_slot, "0000:03:00.0")
        self.assertEqual(dgpu.name, "Navi 23 [Radeon RX 6600/6600 XT/6600M]")
        self.assertTrue(dgpu.sleeping)
        self.assertEqual(igpu.connected_outputs, ["eDP-2"])
        self.assertTrue(igpu.boot_vga)
        self.assertEqual(igpu.render_node, "renderD129")

    def test_sleeping_gpu_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            hybrid_tree(Path(tmp))
            dgpu = gpu.detect_gpus(tmp, FakeRunner(), with_names=False)[0]
            metrics = gpu.backend_for(dgpu).metrics(dgpu, tmp)
        self.assertNotIn("usage_percent", metrics)
        self.assertIn("sleeping", metrics["state"])

    def test_amd_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            hybrid_tree(Path(tmp), dgpu_runtime="active")
            dgpu = gpu.detect_gpus(tmp, FakeRunner(), with_names=False)[0]
            metrics = gpu.backend_for(dgpu).metrics(dgpu, tmp)
        self.assertEqual(metrics["usage_percent"], 0)
        self.assertEqual(metrics["temperature_c"], 50.0)
        self.assertEqual(metrics["vram_total_bytes"], 8 << 30)


class Enrichment(unittest.TestCase):
    def test_capabilities_from_probes(self):
        runner = FakeRunner({
            ("vulkaninfo",): ok(VULKANINFO),
            ("vainfo",): ok(VAINFO),
            ("glxinfo",): ok(GLXINFO),
        })
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"DISPLAY": ":0"}):
            hybrid_tree(Path(tmp), dgpu_runtime="active")
            gpus = gpu.detect_gpus(tmp, runner, with_names=False)
            gpu.enrich(gpus, tmp, runner, probe=True)
        dgpu = gpus[0]
        caps = {c.id: c for c in dgpu.capabilities}
        self.assertEqual(dgpu.kind, "discrete")
        self.assertEqual(dgpu.codename, "NAVI23")
        self.assertEqual(dgpu.architecture, "RDNA 2")
        self.assertEqual(caps["vulkan"].level(), "verified")
        self.assertEqual(caps["opengl"].level(), "verified")
        self.assertEqual(dgpu.vaapi["decode"], ["AV1", "H.264", "HEVC"])
        self.assertEqual(dgpu.vaapi["encode"], ["H.264"])
        glx_env = [env for cmd, env in runner.calls if cmd[0] == "glxinfo"]
        self.assertIn({"DRI_PRIME": "pci-0000_03_00_0"}, glx_env)

    def test_no_probe_does_not_run_tools(self):
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            hybrid_tree(Path(tmp))
            gpus = gpu.detect_gpus(tmp, runner, with_names=False)
            gpu.enrich(gpus, tmp, runner, probe=False)
        self.assertEqual([c for c in runner.calls if c[0][0] in ("vulkaninfo", "vainfo", "glxinfo")], [])
        self.assertIsNone(gpus[0].capabilities[0].available)

    def test_vulkan_missing_device(self):
        runner = FakeRunner({("vulkaninfo",): ok("GPU0:\n\tvendorID = 0x8086\n\tdeviceID = 0x9a49\n")})
        with tempfile.TemporaryDirectory() as tmp:
            hybrid_tree(Path(tmp), dgpu_runtime="active")
            gpus = gpu.detect_gpus(tmp, runner, with_names=False)
            gpu.enrich(gpus, tmp, runner, probe=True)
        self.assertFalse(gpus[0].capabilities[0].available)


class Architecture(unittest.TestCase):
    def test_amd(self):
        self.assertEqual(gpu.amd_architecture("NAVI23"), "RDNA 2")
        self.assertEqual(gpu.amd_architecture("RENOIR"), "GCN 5 (Vega)")
        self.assertEqual(gpu.amd_architecture("GFX1151"), "RDNA 3.5")
        self.assertEqual(gpu.amd_architecture("GFX1201"), "RDNA 4")
        self.assertIsNone(gpu.amd_architecture("UNKNOWN"))

    def test_intel(self):
        self.assertEqual(gpu.intel_architecture("DG2"), "Xe-HPG (Arc Alchemist)")
        self.assertEqual(gpu.intel_architecture("ADL GT2"), "Xe-LP")
        self.assertEqual(gpu.intel_architecture("BMG G21"), "Xe2")

    def test_nvidia(self):
        self.assertEqual(gpu.nvidia_architecture("NVIDIA GeForce RTX 4070"), "Ada Lovelace")
        self.assertEqual(gpu.nvidia_architecture("NVIDIA GeForce GTX 1660 Ti"), "Turing")
        self.assertEqual(gpu.nvidia_architecture("NVIDIA GeForce GTX 1080"), "Pascal")


class NvidiaBackend(unittest.TestCase):
    def test_metrics_from_nvidia_smi(self):
        g = gpu.Gpu("card0", "0000:01:00.0", "0x10de", "0x2786", "NVIDIA", driver="nvidia", runtime_status="active")
        runner = FakeRunner({("nvidia-smi",): ok("00000000:01:00.0, 37, 61, 1024, 12282, 85.5, 2520, 580.95\n")})
        m = gpu.backend_for(g).metrics(g, "/", runner)
        self.assertEqual(m["usage_percent"], 37.0)
        self.assertEqual(m["temperature_c"], 61.0)
        self.assertEqual(m["vram_used_bytes"], 1024 * 1048576)
        self.assertEqual(m["driver_version"], "580.95")

    def test_warns_on_non_nvidia_edition(self):
        g = gpu.Gpu("card0", "0000:01:00.0", "0x10de", "0x2786", "NVIDIA", driver="nouveau")
        notes = gpu.backend_for(g).notes(g, {"edition": "bazzite-dx-gnome"})
        levels = [n.level for n in notes]
        self.assertIn("warn", levels)
        self.assertTrue(any("nouveau" in n.message for n in notes))

    def test_no_driver_fails(self):
        g = gpu.Gpu("card0", None, "0x1002", "0x0000", "AMD", driver=None)
        self.assertEqual(gpu.backend_for(g).notes(g, {})[0].level, "fail")


if __name__ == "__main__":
    unittest.main()
