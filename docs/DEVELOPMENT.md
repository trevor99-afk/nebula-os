# Development and work on NebulaOS

Choose **NebulaOS Work Mode** on the login screen for the GNOME desktop.

## Available today (inherited from Bazzite DX)

| Tool | Notes |
| --- | --- |
| Visual Studio Code | System package, updated with the image. If you installed it with Homebrew before, remove that copy: `brew uninstall --cask visual-studio-code-linux`. |
| Docker CE (with Compose and Buildx), Podman | Administrators are added to the `docker` group on first boot; log out and in once. Or run `ujust dx-group`. |
| Distrobox, BoxBuddy | Any Linux distribution as a container, with your home folder shared: `distrobox create -i ubuntu:24.04 -n dev && distrobox enter dev` |
| Homebrew | Command-line tools without changing the system: `brew install gh node` |
| virt-manager, QEMU and libvirt | Virtual machines (`libvirt` group added on first boot) |
| Android tools, flatpak-builder, gdb, bpftrace, sysprof | See `rpm -qa` for the full list |

The immutable system stays clean: put toolchains in containers (Distrobox, Docker, Podman) or Homebrew, not in the OS image.

## Testing the mode chooser

Run the chooser and session-wrapper unit tests from the repository root:

```bash
python3 -I -m unittest discover -s tests/unit -p 'test_chooser.py'
```

These tests use stand-in Cage, session and `systemctl` commands. They cover saved choices, GPU warnings, the wrapper's desktop environment handoff, one-time switches and the quick-failure fallback. They do not start GTK, a real user D-Bus, logind, portals, evdev devices or Bazzite's recovery hooks.

For an interactive check of this checkout, first build its container image with `just build`, then create and boot a disposable VM with `just build-vm` and `just run-vm`. `build-vm` uses the locally built image when available; `run-vm` boots the generated qcow2. To try files from a worktree without rebuilding the image, make the checkout available inside the VM, then enable bootc's temporary writable `/usr` overlay and install the changed files:

```bash
sudo bootc usr-overlay
sudo install -Dm0755 system_files/usr/libexec/nebula-os-start /usr/libexec/nebula-os-start
sudo install -Dm0755 system_files/usr/libexec/nebula-os-chooser /usr/libexec/nebula-os-chooser
sudo install -Dm0644 system_files/usr/lib/nebula-os/nebula/modes.py /usr/lib/nebula-os/nebula/modes.py
```

Log out to GDM and sign in again to exercise the chooser. Check direct session selection from the GDM gear menu, keyboard and controller navigation, Work/Gaming switches, and the quick-failure path. The `/usr` overlay is temporary and is discarded on reboot; see the [bootc command reference](https://bootc.dev/bootc/man/bootc.8.html).

The current `tests/vm/ci-boot.sh` stops at the GDM login screen because its qcow2 has no user account. A follow-up CI design is to provision a disposable non-privileged account only in a throwaway VM disk artifact, then use QMP to sign in and check for the chooser. Keep that account and its generated credential out of the published image and repository. The CI chooser check is design-only; the current automated VM test does not log in.

## Added by NebulaOS

- **Bazaar "Development & Work" section** (top of the store): Podman Desktop, Pods, BoxBuddy, DevToolbox, GNOME Builder, Meld, GitHub Desktop, Bruno, Insomnia, DBeaver, Android Studio, Godot, Blender, Arduino IDE, LibreOffice, ONLYOFFICE, Obsidian, Logseq, Thunderbird, Slack, Zoom, Teams for Linux, Signal and Telegram.
- **Dock** with Bazaar, Bazzite Portal, VS Code, Terminal and Files.
- `nebula status` and `nebula doctor` for a quick system check.

## Planned

**Nebula Dev Hub:** ready-made isolated environments (Python, web, full-stack, Android, game development, C/C++) that you can create, start, stop, delete, export and import, built on Distrobox and Podman. See [ROADMAP.md](ROADMAP.md#phase-4-development).
