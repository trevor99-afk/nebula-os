import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakeRunner, ok
from nebula import hardware, gpu


class SecureBoot(unittest.TestCase):
    def test_recognizes_enabled_and_disabled_output(self):
        self.assertIs(hardware.secure_boot(FakeRunner({("mokutil",): ok("SecureBoot enabled\n")})), True)
        self.assertIs(hardware.secure_boot(FakeRunner({("mokutil",): ok(stderr="SecureBoot disabled\n")})), False)

    def test_unknown_or_failed_probe_stays_unknown(self):
        self.assertIsNone(hardware.secure_boot(FakeRunner()))
        self.assertIsNone(hardware.secure_boot(FakeRunner({("mokutil",): ok("state unavailable\n")})))


class Report(unittest.TestCase):
    def test_missing_system_files_produce_an_incomplete_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = hardware.report(tmp, FakeRunner(), probe=False, compositor=False)
        self.assertEqual(result["schema"], "nebula.hardware/v1")
        self.assertIsNone(result["system"]["sys_vendor"])
        self.assertEqual(result["gpus"], [])
        self.assertEqual(result["displays"], [])
        self.assertTrue(any("No GPU found" in note["message"] for note in result["notes"]))


class HybridGraphics(unittest.TestCase):
    def test_missing_cardwire_does_not_run_a_command(self):
        gpus = [gpu.Gpu("card0", None, "0x1002", "0x1234", "AMD"),
                gpu.Gpu("card1", None, "0x10de", "0x5678", "NVIDIA")]
        with mock.patch.object(hardware.shutil, "which", return_value=None):
            result = hardware.hybrid_graphics(gpus, FakeRunner())
        self.assertEqual(result["gpus"], ["card0", "card1"])
        self.assertIsNone(result["cardwire_mode"])

    def test_cardwire_output_is_parsed(self):
        gpus = [gpu.Gpu("card0", None, "0x1002", "0x1234", "AMD"),
                gpu.Gpu("card1", None, "0x10de", "0x5678", "NVIDIA")]
        runner = FakeRunner({("cardwire", "get"): ok("Current Mode: Hybrid\nAvailable Modes: Hybrid, Integrated\n")})
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/cardwire"):
            result = hardware.hybrid_graphics(gpus, runner)
        self.assertEqual(result["cardwire_mode"], "Hybrid")
        self.assertEqual(result["cardwire_available_modes"], ["Hybrid", "Integrated"])


if __name__ == "__main__":
    unittest.main()
