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

## Added by NebulaOS

- **Bazaar "Development & Work" section** (top of the store): Podman Desktop, Pods, BoxBuddy, DevToolbox, GNOME Builder, Meld, GitHub Desktop, Bruno, Insomnia, DBeaver, Android Studio, Godot, Blender, Arduino IDE, LibreOffice, ONLYOFFICE, Obsidian, Logseq, Thunderbird, Slack, Zoom, Teams for Linux, Signal and Telegram.
- **Dock** with Bazaar, Bazzite Portal, VS Code, Terminal and Files.
- `nebula status` and `nebula doctor` for a quick system check.

## Planned

**Nebula Dev Hub:** ready-made isolated environments (Python, web, full-stack, Android, game development, C/C++) that you can create, start, stop, delete, export and import, built on Distrobox and Podman. See [ROADMAP.md](ROADMAP.md#phase-4-development).
