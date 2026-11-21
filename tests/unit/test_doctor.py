import json
import os
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import FakeRunner, fail, make_gpu, ok, write
from nebula import doctor


def ctx(runner=None, root="/", edition="bazzite-dx-gnome"):
    return doctor.Context(root=root, runner=runner or FakeRunner(), edition=edition)


class Checks(unittest.TestCase):
    def test_selinux(self):
        self.assertEqual(doctor.check_selinux(ctx(FakeRunner({("getenforce",): ok("Enforcing\n")}))).status, "ok")
        self.assertEqual(doctor.check_selinux(ctx(FakeRunner({("getenforce",): ok("Permissive\n")}))).status, "warn")
        self.assertEqual(doctor.check_selinux(ctx(FakeRunner({("getenforce",): ok("Disabled\n")}))).status, "fail")
        self.assertEqual(doctor.check_selinux(ctx()).status, "skip")

    def test_failed_units(self):
        runner = FakeRunner({
            ("systemctl", "--failed"): ok(json.dumps([{"unit": "broken.service"}])),
            ("systemctl", "--user", "--failed"): ok("[]"),
        })
        check = doctor.check_failed_units(ctx(runner))
        self.assertEqual(check.status, "warn")
        self.assertIn("broken.service (system)", check.details)
        clean = FakeRunner({("systemctl",): ok("[]")})
        self.assertEqual(doctor.check_failed_units(ctx(clean)).status, "ok")

    def test_disk_thresholds(self):
        def statvfs(free_blocks):
            return lambda p: os.statvfs_result((4096, 4096, 1000, free_blocks, free_blocks, 0, 0, 0, 0, 255))
        self.assertEqual(doctor.check_disk(ctx(), statvfs(500)).status, "ok")
        self.assertEqual(doctor.check_disk(ctx(), statvfs(100)).status, "warn")
        self.assertEqual(doctor.check_disk(ctx(), statvfs(10)).status, "fail")

    def test_firmware(self):
        log = "amdgpu: something fine\nbluetooth hci0: Direct firmware load for intel/ibt-1.sfi failed with error -2\n"
        check = doctor.check_firmware(ctx(FakeRunner({("journalctl",): ok(log)})))
        self.assertEqual(check.status, "warn")
        self.assertEqual(len(check.details), 1)
        self.assertEqual(doctor.check_firmware(ctx(FakeRunner({("journalctl",): ok("all fine\n")}))).status, "ok")

    def test_network(self):
        offline = FakeRunner({("nmcli",): ok("none\n")})
        self.assertEqual(doctor.check_network(ctx(offline)).status, "fail")
        portal = FakeRunner({("nmcli",): ok("portal\n")})
        self.assertEqual(doctor.check_network(ctx(portal)).status, "warn")
        online = FakeRunner({("nmcli",): ok("full\n")})
        self.assertEqual(doctor.check_network(ctx(online), resolve=lambda h: None).status, "ok")

        def no_dns(host):
            raise OSError("no dns")
        self.assertEqual(doctor.check_network(ctx(online), resolve=no_dns).status, "warn")

    def test_audio(self):
        good = FakeRunner({("systemctl", "--user"): ok("active\nactive\n"), ("wpctl",): ok("id 55")})
        self.assertEqual(doctor.check_audio(ctx(good)).status, "ok")
        down = FakeRunner({("systemctl", "--user"): ok("active\ninactive\n")})
        self.assertEqual(doctor.check_audio(ctx(down)).status, "fail")
        no_sink = FakeRunner({("systemctl", "--user"): ok("active\nactive\n"), ("wpctl",): fail()})
        self.assertEqual(doctor.check_audio(ctx(no_sink)).status, "warn")

    def test_bluetooth_soft_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sys/class/bluetooth/hci0").mkdir(parents=True)
            write(root / "sys/class/rfkill/rfkill1/type", "bluetooth\n")
            write(root / "sys/class/rfkill/rfkill1/soft", "1\n")
            write(root / "sys/class/rfkill/rfkill1/hard", "0\n")
            check = doctor.check_bluetooth(ctx(root=tmp))
        self.assertEqual(check.status, "warn")
        self.assertIn("turned off", check.summary)

    def test_controllers(self):
        devices = ('I: Bus=0005\nN: Name="Xbox Wireless Controller"\nH: Handlers=event20 js0\n\n'
                   'I: Bus=0011\nN: Name="AT Translated Set 2 keyboard"\nH: Handlers=sysrq kbd event3\n')
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "proc/bus/input/devices", devices)
            self.assertEqual(doctor.controllers(tmp), ["Xbox Wireless Controller"])
            self.assertEqual(doctor.check_controllers(ctx(root=tmp)).status, "ok")

    def test_gpu_without_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = make_gpu(Path(tmp), "card0", "0000:01:00.0", "0x10de", "0x2786", "nvidia")
            os.unlink(dev / "driver")
            check = doctor.check_gpus(ctx(root=tmp))
        self.assertEqual(check.status, "fail")

    def test_flatpak_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / doctor.APP_LIST, "com.a.App   # comment\n\norg.b.App\n")
            runner = FakeRunner({
                ("flatpak", "remotes"): ok("flathub\tsystem\n"),
                ("flatpak", "list"): ok("com.a.App\n"),
                ("systemctl", "show"): ok("success\n"),
            })
            check = doctor.check_flatpak(ctx(runner, root=tmp))
        self.assertEqual(check.status, "info")
        self.assertIn("missing: org.b.App", check.details)

    def test_flathub_disabled(self):
        runner = FakeRunner({("flatpak", "remotes"): ok("flathub\tsystem,disabled\n")})
        self.assertEqual(doctor.check_flatpak(ctx(runner)).status, "fail")


class Diagnose(unittest.TestCase):
    def test_broken_check_is_contained(self):
        def boom(_ctx):
            raise RuntimeError("bad")
        results = doctor.diagnose(ctx(), checks=(boom, doctor.check_selinux))
        self.assertEqual({r.status for r in results}, {"skip"})

    def test_overall(self):
        self.assertEqual(doctor.overall([doctor.Check("a", "A", "ok", ""), doctor.Check("b", "B", "warn", "")]), "warn")
        self.assertEqual(doctor.overall([doctor.Check("a", "A", "fail", "")]), "fail")
        self.assertEqual(doctor.overall([]), "ok")


if __name__ == "__main__":
    unittest.main()
