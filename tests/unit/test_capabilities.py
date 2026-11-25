import unittest

import helpers  # noqa: F401  (sets the import path)
from nebula.capabilities import Capability, Note


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

    def test_failed_verification_is_distinct_from_unknown(self):
        c = Capability("p", "P", driver=True, available=True, enabled=True, verified=False)
        self.assertEqual(c.level(), "enabled")
        self.assertEqual(c.status(), "enabled, verification failed")

    def test_hardware_capable_without_a_driver(self):
        c = Capability("hdr", "HDR", hardware=True, driver=False)
        self.assertEqual(c.status(), "hardware capable, no working driver")

    def test_to_dict(self):
        d = Capability("x", "X", hardware=True, evidence=["e"]).to_dict()
        self.assertEqual(d["level"], "hardware")
        self.assertEqual(d["evidence"], ["e"])

    def test_to_dict_does_not_share_evidence_list(self):
        c = Capability("x", "X", evidence=["source"])
        c.to_dict()["evidence"].append("mutated")
        self.assertEqual(c.evidence, ["source"])


class Notes(unittest.TestCase):
    def test_optional_subject_is_kept_in_the_json_shape(self):
        self.assertEqual(Note("warn", "Check the GPU").to_dict(),
                         {"level": "warn", "subject": None, "message": "Check the GPU"})


if __name__ == "__main__":
    unittest.main()
