"""Mode switching (nebula-os-switch-side) with stub commands: what would be called, in each context."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (sets the repository root)

SWITCH = helpers.ROOT / "system_files" / "usr" / "libexec" / "nebula-os-switch-side"
UID = str(os.getuid())

# Stubs record every call in $LOG. loginctl knows two sessions of this user:
# c2 is the graphical (Gaming Mode) session, c7 a text console.
STUBS = {
    "busctl": 'echo "busctl $*" >> "$LOG"; [[ "$1" == get-property ]] && echo "s \\"${SESSION-gnome}\\""; exit 0',
    "loginctl": f'''echo "loginctl $*" >> "$LOG"
case "$1" in
    list-sessions) printf '  c2 {UID} tester seat0 1234 user tty2 no -\\n  c7 {UID} tester seat0 2345 user tty3 no -\\n  c9 4242 other seat0 3456 user tty4 no -\\n' ;;
    show-session) case "$2" in c2) echo wayland ;; c7) echo tty ;; *) echo x11 ;; esac ;;
esac''',
    "pgrep": 'exit "${STEAM_RUNNING:-1}"',
    "steam": 'echo "steam $*" >> "$LOG"',
    "gnome-session-quit": 'echo "gnome-session-quit $*" >> "$LOG"',
}


def run_switch(*args, stubs=None, **env):
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        for name, body in {**STUBS, **(stubs or {})}.items():
            path = bin_dir / name
            path.write_text("#!/usr/bin/bash\n" + body + "\n")
            path.chmod(0o755)
        log = Path(tmp) / "log"
        log.touch()
        proc = subprocess.run(["bash", str(SWITCH), *args], capture_output=True, text=True, timeout=20,
                              env={"PATH": f"{bin_dir}:/usr/bin:/bin", "LOG": str(log), **env})
        return proc, log.read_text().splitlines()


def terminated(calls):
    return [c.split()[-1] for c in calls if c.startswith("loginctl terminate-session")]


class SwitchNow(unittest.TestCase):
    def test_saves_the_mode_first(self):
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="tty", XDG_SESSION_ID="c7")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SetSession s gnome", calls[0])

    def test_text_console_closes_the_graphical_session_not_itself(self):
        # Gaming Mode hangs on a black screen; the user runs `ujust nebula-mode work now` on Ctrl+Alt+F3.
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="tty", XDG_SESSION_ID="c7")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(terminated(calls), ["c2"])

    def test_ssh_without_graphical_session_only_saves(self):
        proc, calls = run_switch("gaming", "--now", stubs={"loginctl": 'echo "loginctl $*" >> "$LOG"'})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(terminated(calls), [])
        self.assertIn("next login", proc.stdout)

    def test_gnome_logs_out_through_gnome(self):
        proc, calls = run_switch("gaming", "--now", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="GNOME",
                                 XDG_SESSION_ID="c2")
        self.assertIn("gnome-session-quit --logout --no-prompt", calls)
        self.assertEqual(terminated(calls), [])

    def test_gaming_mode_asks_steam_to_exit(self):
        # Steam's "Switch to Desktop" -> steamos-session-select -> os-session-select -> here.
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="x11", XDG_CURRENT_DESKTOP="gamescope",
                                 XDG_SESSION_ID="c2", STEAM_RUNNING="0")
        self.assertIn("steam -shutdown", calls)
        self.assertEqual(terminated(calls), [])

    def test_failed_gaming_mode_ends_its_own_session(self):
        # Bazzite's recovery after repeated failed starts runs inside the session, before Steam starts.
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="x11", XDG_CURRENT_DESKTOP="gamescope",
                                 XDG_SESSION_ID="c2")
        self.assertEqual(terminated(calls), ["c2"])


class Status(unittest.TestCase):
    def status(self, session):
        proc, _ = run_switch("status", SESSION=session)
        return proc.returncode, proc.stdout.strip()

    def test_known_sessions(self):
        self.assertEqual(self.status("gnome"), (0, "work"))
        self.assertEqual(self.status("gamescope-session-steam"), (0, "gaming"))
        self.assertEqual(self.status("gamescope-session-ogui-steam"), (0, "gaming"))

    def test_no_saved_session_is_work(self):
        # GDM falls back to the "gnome" session when the user never chose one.
        self.assertEqual(self.status(""), (0, "work"))

    def test_unknown_session_is_an_error_not_work(self):
        self.assertEqual(self.status("plasma"), (1, ""))


if __name__ == "__main__":
    unittest.main()
