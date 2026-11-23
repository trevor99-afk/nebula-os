"""nebula-os-flatpak-setup installs only from the real Flathub (red-team hypothesis R04)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers

SCRIPT = helpers.ROOT / "system_files" / "usr" / "libexec" / "nebula-os-flatpak-setup"


def run_setup(remote_url):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "bin").mkdir()
        log = tmp / "calls"
        flatpak = tmp / "bin" / "flatpak"
        flatpak.write_text(f'#!/usr/bin/bash\necho "flatpak $*" >> "{log}"\n'
                           f'case "$1" in remotes) printf "flathub\\t{remote_url}\\n" ;; info) exit 1 ;; esac\nexit 0\n')
        flatpak.chmod(0o755)
        (tmp / "list").write_text("org.example.App\n")
        script = SCRIPT.read_text().replace("if [[ $EUID -ne 0 ]]; then", "if false; then")
        script = script.replace("LIST=/usr/share/nebula-os/flatpaks.list", f"LIST={tmp}/list")
        script = script.replace("STATE_DIR=/var/lib/nebula-os", f"STATE_DIR={tmp}/state")
        (tmp / "setup.sh").write_text(script)
        proc = subprocess.run(["bash", str(tmp / "setup.sh")], capture_output=True, text=True, timeout=30,
                              env={"PATH": f"{tmp}/bin:/usr/bin:/bin"})
        return proc, log.read_text() if log.exists() else ""


class FlathubRemote(unittest.TestCase):
    def test_real_flathub_installs(self):
        proc, calls = run_setup("https://dl.flathub.org/repo/")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("install", calls)

    def test_fake_flathub_is_refused(self):
        proc, calls = run_setup("https://evil.example/repo/")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("flatpak install", calls)
        self.assertIn("not installing anything", proc.stderr)


if __name__ == "__main__":
    unittest.main()
