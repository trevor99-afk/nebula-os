import os
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import FakeRunner, ok, write
from nebula import sysinfo


class OsRelease(unittest.TestCase):
    def test_quotes_and_escapes(self):
        parsed = sysinfo.parse_os_release('NAME="NebulaOS"\nID=bazzite\n# comment\nPRETTY_NAME="Nebula \\"OS\\" \\$1"\nX=\'single\'\n')
        self.assertEqual(parsed["NAME"], "NebulaOS")
        self.assertEqual(parsed["ID"], "bazzite")
        self.assertEqual(parsed["PRETTY_NAME"], 'Nebula "OS" $1')
        self.assertEqual(parsed["X"], "single")

    def test_os_info_reads_nebula_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "usr/lib/os-release", 'NAME="NebulaOS"\nIMAGE_VERSION="latest.20261121"\n')
            write(root / "usr/share/nebula-os/image-ref", "ghcr.io/x/nebula-os:latest\n")
            write(root / "usr/share/nebula-os/build-info.json", '{"version": "latest.20261121", "git_sha": "abc"}')
            write(root / "usr/share/ublue-os/image-info.json", '{"image-name": "bazzite-dx-gnome"}')
            info = sysinfo.os_info(tmp)
        self.assertEqual(info["name"], "NebulaOS")
        self.assertEqual(info["image_ref"], "ghcr.io/x/nebula-os:latest")
        self.assertEqual(info["build"]["git_sha"], "abc")
        self.assertEqual(info["edition"], "bazzite-dx-gnome")


class Proc(unittest.TestCase):
    def test_cpu_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "proc/stat", "cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 1 1 1 1\n")
            before = sysinfo.read_cpu_times(tmp)
            write(Path(tmp) / "proc/stat", "cpu  150 0 150 750 150 0 0 0 0 0\n")
            after = sysinfo.read_cpu_times(tmp)
        self.assertEqual(before, (200, 1000))
        self.assertEqual(sysinfo.cpu_usage_percent(before, after), 50.0)
        self.assertIsNone(sysinfo.cpu_usage_percent(None, after))

    def test_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "proc/meminfo", "MemTotal: 1000 kB\nMemAvailable: 250 kB\nSwapTotal: 100 kB\nSwapFree: 40 kB\n")
            mem = sysinfo.memory(tmp)
        self.assertEqual(mem["used_bytes"], 750 * 1024)
        self.assertEqual(mem["used_percent"], 75.0)
        self.assertEqual(mem["swap_used_bytes"], 60 * 1024)

    def test_network_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = "Inter-|Receive\n face |bytes packets\n"
            write(Path(tmp) / "proc/net/dev", header + "    lo: 5 0 0 0 0 0 0 0 5 0\n  wlan0: 1000 0 0 0 0 0 0 0 500 0\n")
            before = sysinfo.read_net_counters(tmp)
            write(Path(tmp) / "proc/net/dev", header + "    lo: 9 0 0 0 0 0 0 0 9 0\n  wlan0: 3000 0 0 0 0 0 0 0 1500 0\n")
            after = sysinfo.read_net_counters(tmp)
        self.assertNotIn("lo", before)
        rates = sysinfo.net_rates(before, after, 2.0)
        self.assertEqual(rates["rx_bytes_per_s"], 1000)
        self.assertEqual(rates["tx_bytes_per_s"], 500)

    def test_uptime(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "proc/uptime", "3600.5 100.0\n")
            self.assertEqual(sysinfo.uptime_seconds(tmp), 3600.5)


class Sensors(unittest.TestCase):
    def test_prefers_k10temp_tctl(self):
        with tempfile.TemporaryDirectory() as tmp:
            hw = Path(tmp) / "sys/class/hwmon"
            write(hw / "hwmon0/name", "acpitz\n")
            write(hw / "hwmon0/temp1_input", "40000\n")
            write(hw / "hwmon5/name", "k10temp\n")
            write(hw / "hwmon5/temp1_input", "65875\n")
            write(hw / "hwmon5/temp1_label", "Tctl\n")
            self.assertEqual(sysinfo.cpu_temperature(tmp), 65.9)

    def test_no_sensors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(sysinfo.cpu_temperature(tmp))


class Storage(unittest.TestCase):
    def test_dedups_same_filesystem(self):
        fake = os.statvfs_result((4096, 4096, 1000, 400, 350, 0, 0, 0, 0, 255))
        result = sysinfo.storage(("/a", "/b"), statvfs=lambda p: fake)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["used_bytes"], 600 * 4096)
        self.assertEqual(result[0]["used_percent"], round(100 * 600 / 950, 1))

    def test_block_devices_skip_virtual(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "sys/block"
            write(base / "nvme0n1/size", "1000000\n")
            write(base / "nvme0n1/device/model", "Fast SSD\n")
            write(base / "zram0/size", "100\n")
            write(base / "loop0/size", "100\n")
            disks = sysinfo.block_devices(tmp)
        self.assertEqual([d["name"] for d in disks], ["nvme0n1"])
        self.assertEqual(disks[0]["transport"], "nvme")
        self.assertEqual(disks[0]["size_bytes"], 512_000_000)


class Power(unittest.TestCase):
    def test_power_profile(self):
        runner = FakeRunner({
            ("busctl", "--system", "get-property", "org.freedesktop.UPower.PowerProfiles"): ok('s "balanced"\n'),
            ("tuned-adm", "active"): ok("Current active profile: balanced-bazzite\n"),
        })
        self.assertEqual(sysinfo.power_profile(runner), {"profile": "balanced", "tuned_profile": "balanced-bazzite"})

    def test_power_profile_missing(self):
        self.assertEqual(sysinfo.power_profile(FakeRunner()), {"profile": None, "tuned_profile": None})


if __name__ == "__main__":
    unittest.main()
