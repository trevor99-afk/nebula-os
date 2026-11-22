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
# c2 is the graphical (Gaming Mode) session, c4 a remote graphical session
# (GNOME Remote Login), c7 a text console; c9 belongs to another user.
STUBS = {
    "busctl": 'echo "busctl $*" >> "$LOG"; [[ "$1" == get-property ]] && echo "s \\"${SESSION-gnome}\\""; exit 0',
    "loginctl": f'''echo "loginctl $*" >> "$LOG"
case "$1" in
    list-sessions)
        [[ -n "${{LOGINCTL_FAIL:-}}" ]] && exit 1
        printf '  c2 {UID} tester seat0 1234 user tty2 no -\\n  c4 {UID} tester - 4567 user - no -\\n  c7 {UID} tester seat0 2345 user tty3 no -\\n  c9 4242 other seat0 3456 user tty4 no -\\n' ;;
    show-session)
        if [[ "$4" == Remote ]]; then [[ "$2" == c4 ]] && echo yes || echo no
        else case "$2" in c2 | c4) echo wayland ;; c7) echo tty ;; *) echo x11 ;; esac; fi ;;
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
        saved = next(i for i, c in enumerate(calls) if "SetSession s gnome" in c)
        first_logout = next(i for i, c in enumerate(calls) if c.startswith("loginctl terminate-session"))
        self.assertLess(saved, first_logout)

    def test_text_console_closes_the_graphical_session_not_itself(self):
        # Gaming Mode hangs on a black screen; the user runs `ujust nebula-mode work now` on Ctrl+Alt+F3.
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="tty", XDG_SESSION_ID="c7")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(terminated(calls), ["c2"])

    def test_remote_sessions_are_left_alone(self):
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="tty", XDG_SESSION_ID="c7")
        self.assertNotIn("c4", terminated(calls))

    def test_loginctl_failure_is_reported_not_hidden(self):
        proc, calls = run_switch("work", "--now", XDG_SESSION_TYPE="tty", XDG_SESSION_ID="c7", LOGINCTL_FAIL="1")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(terminated(calls), [])
        self.assertIn("could not be listed", proc.stderr)

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


class SteamHooks(unittest.TestCase):
    """Steam's "Switch to Desktop" hook and the steamosctl shim call nebula-os-switch-side."""

    def run_hook(self, script, *args, status="work", status_exit=0):
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "switch-side"
            stub.write_text('#!/usr/bin/bash\necho "$*" >> "$LOG"\n[[ "$1" == status ]] && echo "$STATUS"\nexit "${STATUS_EXIT:-0}"\n')
            stub.chmod(0o755)
            log = Path(tmp) / "log"
            log.touch()
            proc = subprocess.run(["bash", str(helpers.ROOT / script), *args], capture_output=True, text=True,
                                  timeout=20, env={"PATH": "/usr/bin:/bin", "LOG": str(log), "STATUS": status,
                                                   "STATUS_EXIT": str(status_exit),
                                                   "NEBULA_SWITCH_SIDE": str(stub)})
            return proc, log.read_text().splitlines()

    def test_switch_to_desktop_goes_to_work_mode(self):
        hook = "system_files/usr/lib/os-session-select"
        for arg in ("plasma", "plasma-wayland-persistent", "plasma-x11-persistent"):
            self.assertEqual(self.run_hook(hook, arg)[1], ["work --now"], arg)
        self.assertEqual(self.run_hook(hook, "gamescope")[1], ["gaming --now"])

    def test_steamosctl_shim(self):
        shim = "system_files/usr/libexec/nebula-os-steamosctl"
        self.assertEqual(self.run_hook(shim, "switch-to-desktop-mode")[1], ["work --now"])
        self.assertEqual(self.run_hook(shim, "switch-to-game-mode")[1], ["gaming --now"])
        self.assertEqual(self.run_hook(shim, "set-default-login-mode", "game")[1], ["gaming"])
        self.assertEqual(self.run_hook(shim, "get-default-login-mode", status="gaming")[0].stdout.strip(), "game")
        self.assertEqual(self.run_hook(shim, "get-default-login-mode", status="work")[0].stdout.strip(), "desktop")

    def test_get_default_mode_does_not_guess_when_status_fails(self):
        shim = "system_files/usr/libexec/nebula-os-steamosctl"
        proc, calls = self.run_hook(shim, "get-default-login-mode", status_exit=1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(calls, ["status"])

    def test_unknown_steamosctl_command_is_rejected(self):
        shim = "system_files/usr/libexec/nebula-os-steamosctl"
        proc, calls = self.run_hook(shim, "unsupported-command")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not supported", proc.stderr)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()


class Chooser(unittest.TestCase):
    """The full-screen chooser session ("nebula-os") keeps its place in AccountsService."""

    def run_in_home(self, *args, **env):
        home = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", home]))
        proc, calls = run_switch(*args, HOME=home, **env)
        state = Path(home) / ".local" / "state" / "nebula-os"
        read = lambda name: (state / name).read_text().strip() if (state / name).exists() else None  # noqa: E731
        return proc, calls, read

    def test_status_reports_the_chooser(self):
        proc, _ = run_switch("status", SESSION="nebula-os")
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, "chooser"))

    def test_switch_keeps_the_chooser_and_skips_it_once(self):
        proc, calls, read = self.run_in_home("gaming", SESSION="nebula-os")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(any("SetSession" in c for c in calls), calls)
        self.assertEqual((read("next-mode"), read("last-mode")), ("gaming", "gaming"))
        self.assertIn("just this once", proc.stdout)

    def test_switch_now_inside_the_chooser_session_ends_only_the_mode(self):
        # Work Mode started by the chooser: GNOME quits, and the chooser session starts Gaming Mode.
        proc, calls, read = self.run_in_home("gaming", "--now", SESSION="nebula-os", XDG_SESSION_TYPE="wayland",
                                             XDG_CURRENT_DESKTOP="GNOME", XDG_SESSION_ID="c2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read("next-mode"), "gaming")
        self.assertIn("gnome-session-quit --logout --no-prompt", calls)
        self.assertEqual(terminated(calls), [])

    def test_without_the_chooser_nothing_is_written_to_home(self):
        proc, calls, read = self.run_in_home("work", SESSION="gamescope-session-steam")
        self.assertIn("busctl call org.freedesktop.Accounts /org/freedesktop/Accounts/User%s "
                      "org.freedesktop.Accounts.User SetSession s gnome" % UID, calls)
        self.assertIsNone(read("next-mode"))

    def test_chooser_on_and_off(self):
        proc, calls, _ = self.run_in_home("chooser", "on")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(any("SetSession s nebula-os" in c for c in calls), calls)
        home = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", home]))
        state = Path(home) / ".local" / "state" / "nebula-os"
        state.mkdir(parents=True)
        (state / "last-mode").write_text("gaming\n")
        proc, calls = run_switch("chooser", "off", HOME=home)
        self.assertTrue(any("SetSession s gamescope-session-steam" in c for c in calls), calls)

    def test_refuses_symlinked_state(self):
        home = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", home]))
        state = Path(home) / ".local" / "state" / "nebula-os"
        state.mkdir(parents=True)
        target = Path(home) / "elsewhere"
        os.symlink(target, state / "next-mode")
        proc, _ = run_switch("gaming", SESSION="nebula-os", HOME=home)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(target.exists())


class FlatpakInstallerArguments(unittest.TestCase):
    def test_unknown_option_fails_before_touching_system_state(self):
        script = helpers.ROOT / "system_files/usr/libexec/nebula-os-flatpak-setup"
        proc = subprocess.run(["bash", str(script), "--unexpected"], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Usage:", proc.stderr)
        self.assertEqual(proc.stdout, "")
