import unittest

import helpers  # noqa: F401  (sets the import path)
from nebula.capabilities import Capability


class CapabilityLevels(unittest.TestCase):
    def test_full_chain_is_verified(self):
        c = Capability("x", "X", True, True, True, True, True)
        self.assertEqual(c.level(), "verified")
        self.assertEqual(c.status(), "verified working")

    def test_available_but_off(self):
        c = Capability("vrr", "VRR", hardware=True, driver=True, available=True, enabled=False)
        self.assertEqual(c.level(), "available")
        self.assertEqual(c.status(), "available, turned off")

    def test_unknown_next_level_is_not_reported_as_off(self):
        c = Capability("x", "X", driver=True)
        self.assertEqual(c.level(), "driver")
        self.assertEqual(c.status(), "driver present (available: unknown)")

    def test_hardware_false_wins(self):
        c = Capability("hdr", "HDR", hardware=False, driver=True, available=False)
        self.assertEqual(c.status(), "not supported by the hardware")

    def test_nothing_known(self):
        self.assertEqual(Capability("x", "X").status(), "unknown")

    def test_missing_driver(self):
        c = Capability("x", "X", driver=False)
        self.assertEqual(c.status(), "not available (driver missing)")

    def test_enabled_without_verification(self):
        c = Capability("p", "P", driver=True, available=True, enabled=True)
        self.assertEqual(c.status(), "enabled (not verified)")

    def test_to_dict(self):
        d = Capability("x", "X", hardware=True, evidence=["e"]).to_dict()
        self.assertEqual(d["level"], "hardware")
        self.assertEqual(d["evidence"], ["e"])


if __name__ == "__main__":
    unittest.main()
