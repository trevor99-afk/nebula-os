"""Pinned Bazzite base: the lock lookup in build.yml and the daily updater in update-base.yml."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers

ROOT = helpers.ROOT
BUILD = (ROOT / ".github/workflows/build.yml").read_text()
UPDATE = (ROOT / ".github/workflows/update-base.yml").read_text()
OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64


def lookup_awk():
    return re.search(r"pinned=\$\(awk (.*) base-images\.lock\)", BUILD).group(1)


def resolve_script():
    block = UPDATE.split("- name: Resolve and verify the newest :stable digests", 1)[1]
    run = block.split("run: |", 1)[1].split("\n      - name:", 1)[0]
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in run.splitlines())


class LockLookup(unittest.TestCase):
    def lookup(self, base_image, lock_text):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "base-images.lock").write_text(lock_text)
            cmd = f'BASE_IMAGE={base_image}; repo="${{BASE_IMAGE%:*}}"; awk {lookup_awk()} base-images.lock'
            return subprocess.run(["bash", "-c", cmd], cwd=tmp, capture_output=True, text=True).stdout.strip()

    def test_resolves_the_pinned_digest(self):
        lock = f"# comment\nghcr.io/ublue-os/bazzite-dx-gnome@{OLD}\nghcr.io/ublue-os/bazzite-dx-nvidia-gnome@{NEW}\n"
        self.assertEqual(self.lookup("ghcr.io/ublue-os/bazzite-dx-gnome:stable", lock), f"ghcr.io/ublue-os/bazzite-dx-gnome@{OLD}")
        self.assertEqual(self.lookup("ghcr.io/ublue-os/bazzite-dx-nvidia-gnome:stable", lock),
                         f"ghcr.io/ublue-os/bazzite-dx-nvidia-gnome@{NEW}")

    def test_rejects_tags_and_missing_entries(self):
        self.assertEqual(self.lookup("ghcr.io/ublue-os/bazzite-dx-gnome:stable", "ghcr.io/ublue-os/bazzite-dx-gnome:stable\n"), "")
        self.assertEqual(self.lookup("ghcr.io/ublue-os/bazzite-dx-gnome:stable", f"ghcr.io/ublue-os/other@{OLD}\n"), "")

    def test_the_real_lock_covers_every_build(self):
        for base in re.findall(r"base_image:\s*(\S+)", BUILD):
            self.assertRegex(self.lookup(base, (ROOT / "base-images.lock").read_text()), r"@sha256:[0-9a-f]{64}$")


class DailyUpdater(unittest.TestCase):
    def run_updater(self, cosign_ok):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "bin").mkdir()
            (tmp / "keys").mkdir()
            (tmp / "keys/ublue-os.pub").write_text("key")
            (tmp / "base-images.lock").write_text(f"# header\nghcr.io/ublue-os/bazzite-dx-gnome@{OLD}\n")
            (tmp / "bin/skopeo").write_text(f"#!/bin/bash\necho {NEW}\n")
            (tmp / "bin/cosign").write_text(f"#!/bin/bash\necho \"cosign $*\" >> {tmp}/cosign.log\nexit {0 if cosign_ok else 1}\n")
            for f in ("skopeo", "cosign"):
                (tmp / "bin" / f).chmod(0o755)
            out = tmp / "out"
            proc = subprocess.run(["bash", "-e", "-c", resolve_script()], cwd=tmp, capture_output=True, text=True,
                                  env={"PATH": f"{tmp}/bin:/usr/bin:/bin", "GITHUB_OUTPUT": str(out)})
            return proc, (tmp / "base-images.lock").read_text(), out.read_text() if out.exists() else "", \
                (tmp / "cosign.log").read_text() if (tmp / "cosign.log").exists() else ""

    def test_verified_new_digest_updates_the_lock(self):
        proc, lock, out, cosign = self.run_updater(cosign_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"ghcr.io/ublue-os/bazzite-dx-gnome@{NEW}", lock)
        self.assertIn("changed=true", out)
        self.assertIn(f"--key keys/ublue-os.pub ghcr.io/ublue-os/bazzite-dx-gnome@{NEW}", cosign)

    def test_unverified_new_digest_changes_nothing(self):
        proc, lock, out, _ = self.run_updater(cosign_ok=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(f"ghcr.io/ublue-os/bazzite-dx-gnome@{OLD}", lock)
        self.assertNotIn("changed=true", out)

    def test_validation_build_is_started_for_the_pull_request(self):
        self.assertIn('gh workflow run build.yml --ref "$branch"', UPDATE)
        self.assertIn("actions: write", UPDATE)


if __name__ == "__main__":
    unittest.main()
