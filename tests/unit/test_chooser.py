"""Start-up mode chooser: saved choices, Gaming Mode support, and the session wrapper."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import make_gpu
from nebula import modes

START = helpers.ROOT / "system_files" / "usr" / "libexec" / "nebula-os-start"


class SavedChoices(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.home]))
        os.environ.pop("XDG_STATE_HOME", None)

    def test_last_mode_round_trip(self):
        self.assertIsNone(modes.last_mode(self.home))
        modes.save_last_mode("gaming", self.home)
        self.assertEqual(modes.last_mode(self.home), "gaming")
        with self.assertRaises(ValueError):
            modes.save_last_mode("party", self.home)

    def test_next_mode_applies_once(self):
        path = modes.state_dir(self.home) / "next-mode"
        path.parent.mkdir(parents=True)
        path.write_text("work\n")
        self.assertEqual(modes.take_next_mode(self.home), "work")
        self.assertIsNone(modes.take_next_mode(self.home))

    def test_garbage_is_ignored(self):
        path = modes.state_dir(self.home) / "last-mode"
        path.parent.mkdir(parents=True)
        path.write_text("rm -rf /\n")
        self.assertIsNone(modes.last_mode(self.home))


class GamingSupport(unittest.TestCase):
    def check(self, *drivers):
        with tempfile.TemporaryDirectory() as tmp:
            for i, driver in enumerate(drivers):
                make_gpu(Path(tmp), f"card{i}", f"0000:0{i}:00.0", "0x1002", "0x73ff", driver)
            return modes.gaming_support(tmp)

    def test_real_gpus(self):
        for driver in ("amdgpu", "i915", "xe", "nvidia"):
            self.assertTrue(self.check(driver)[0], driver)

    def test_virtual_machine_display_only(self):
        # GNOME Boxes: QXL only, so gamescope fails with "Failed to initialize Vulkan".
        supported, reason = self.check("qxl")
        self.assertFalse(supported)
        self.assertIn("virtual", reason)

    def test_laptop_with_virtual_and_real(self):
        self.assertTrue(self.check("simpledrm", "amdgpu")[0])

    def test_unknown_driver_is_not_locked_out(self):
        self.assertTrue(self.check("futuregpu")[0])

    def test_no_gpu(self):
        self.assertFalse(self.check()[0])


# --- The session wrapper, with stand-ins for cage and the two sessions ---------------------------

FAKE_CAGE = r'''#!/usr/bin/bash
# fake cage: records the call, then answers with the next line of $CHOICES.
echo "cage $*" >> "$LOG"
echo "env GDK_DEBUG=${GDK_DEBUG:-} GSK_RENDERER=${GSK_RENDERER:-}" >> "$LOG"
result=""; message=""
while [[ $# -gt 0 ]]; do
    case "$1" in --result) result=$2; shift ;; --message) message=$2; shift ;; esac
    shift
done
[[ -n "$message" ]] && echo "message: $message" >> "$LOG"
choice=$(head -n 1 "$CHOICES"); sed -i 1d "$CHOICES"
[[ "$choice" == "<crash>" ]] && exit 1
printf '%s\n' "$choice" > "$result"
'''

FAKE_SESSION = r'''#!/usr/bin/bash
echo "{name} XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP XDG_SESSION_DESKTOP=$XDG_SESSION_DESKTOP" >> "$LOG"
action=${{{var}:-exit}}
case "$action" in
    fail) exit 1 ;;
    switch-to-*) mkdir -p "$HOME/.local/state/nebula-os"; echo "${{action#switch-to-}}" > "$HOME/.local/state/nebula-os/next-mode"; export {var}=exit ;;
esac
exit 0
'''


def run_start(choices, state=None, **env):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bins, sessions, home = tmp / "bin", tmp / "sessions", tmp / "home"
        for d in (bins, sessions, home):
            d.mkdir()
        scripts = {
            "cage": FAKE_CAGE,
            "fake-gaming": FAKE_SESSION.format(name="gaming", var="GAMING_ACTION"),
            "fake-gnome": FAKE_SESSION.format(name="gnome", var="GNOME_ACTION"),
            "systemctl": '#!/usr/bin/bash\necho "systemctl $*" >> "$LOG"\n',
        }
        for name, body in scripts.items():
            (bins / name).write_text(body)
            (bins / name).chmod(0o755)
        (sessions / "gamescope-session-steam.desktop").write_text(
            "[Desktop Entry]\nName=NebulaOS Gaming Mode\nExec=fake-gaming\nDesktopNames=gamescope\n")
        (sessions / "gnome.desktop").write_text(
            "[Desktop Entry]\nName=NebulaOS Work Mode\nExec=fake-gnome\nDesktopNames=GNOME;\n")
        for name, value in (state or {}).items():
            path = home / ".local" / "state" / "nebula-os" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value + "\n")
        (tmp / "choices").write_text("".join(c + "\n" for c in choices))
        log = tmp / "log"
        log.touch()
        proc = subprocess.run(["bash", str(START)], capture_output=True, text=True, timeout=30, env={
            "PATH": f"{bins}:/usr/bin:/bin", "HOME": str(home), "LOG": str(log), "CHOICES": str(tmp / "choices"),
            "XDG_RUNTIME_DIR": str(tmp), "NEBULA_SESSIONS_DIR": str(sessions), "NEBULA_CHOOSER": "chooser",
            **env})
        left = (home / ".local" / "state" / "nebula-os" / "next-mode").exists()
        return proc, log.read_text().splitlines(), left


def started(calls):
    return [c.split()[0] for c in calls if c.startswith(("gaming ", "gnome "))]


class SessionWrapper(unittest.TestCase):
    def test_work_mode_gets_gnome_variables(self):
        proc, calls, _ = run_start(["work"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("gnome XDG_CURRENT_DESKTOP=GNOME XDG_SESSION_DESKTOP=gnome", calls)
        self.assertEqual(sum(c.startswith("cage ") for c in calls), 1)

    def test_chooser_runs_without_portals_and_in_software(self):
        proc, calls, _ = run_start(["logout"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(started(calls), [])
        self.assertTrue(calls[0].startswith("cage -d -- chooser --result "), calls)
        self.assertEqual(calls[1], "env GDK_DEBUG=no-portals GSK_RENDERER=cairo")

    def test_one_time_choice_skips_the_chooser(self):
        proc, calls, left = run_start([], state={"next-mode": "gaming"}, NEBULA_QUICK_FAIL="0")
        self.assertEqual(started(calls), ["gaming"])
        self.assertFalse(any(c.startswith("cage ") for c in calls))
        self.assertFalse(left, "the one-time choice must be used up")

    def test_gaming_mode_that_cannot_start_returns_to_the_chooser(self):
        # As in a VM without a usable GPU: gamescope stops at once.
        proc, calls, _ = run_start(["gaming", "work"], GAMING_ACTION="fail")
        self.assertEqual(started(calls), ["gaming", "gnome"])
        self.assertTrue(any(c.startswith("message: Gaming Mode could not start") for c in calls), calls)

    def test_switch_inside_a_mode_starts_the_other_without_login(self):
        # Steam's "Switch to Desktop" in Gaming Mode: next-mode=work, then Steam exits.
        proc, calls, left = run_start(["gaming"], GAMING_ACTION="switch-to-work", NEBULA_QUICK_FAIL="0")
        self.assertEqual(started(calls), ["gaming", "gnome"])
        self.assertEqual(sum(c.startswith("cage ") for c in calls), 1)
        self.assertTrue(any("unset-environment" in c for c in calls), "the old mode's variables are cleared")
        self.assertFalse(left)

    def test_broken_chooser_falls_back_to_work_mode(self):
        proc, calls, _ = run_start(["<crash>"])
        self.assertEqual(started(calls), ["gnome"])
        self.assertIn("starting Work Mode", proc.stderr)

    def test_normal_logout_ends_the_session(self):
        proc, calls, _ = run_start(["work", "gaming"])
        self.assertEqual(started(calls), ["gnome"])
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
