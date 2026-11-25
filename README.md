<p align="center">
  <img src="system_files/usr/share/icons/hicolor/scalable/apps/nebula-os-logo.svg" width="128" alt="NebulaOS logo">
</p>

# NebulaOS

**One operating system. Two worlds.** A Linux distribution with a **Gaming Mode** and a **Work Mode**. New accounts see a full-screen chooser after login; the login screen's gear menu can still start either mode directly.

NebulaOS is built on [Bazzite DX](https://dev.bazzite.gg), so it keeps everything Bazzite provides (Steam, Proton, Gamescope, MangoHud, a gaming-tuned kernel, fresh graphics drivers, automatic updates and one-step rollback). On top, it adds its own tools and identity, and does not rebuild what Bazzite already does well.

> **Status:** testing. The image builds, is signed and passes the automated image tests. It has been installed and tested in a virtual machine (GNOME Boxes), but not yet on real hardware. See [what is verified](docs/NEBULAOS_TECHNICAL_AUDIT.md#unverified-needs-a-real-boot).

## The two modes

| | NebulaOS Gaming Mode | NebulaOS Work Mode |
| --- | --- | --- |
| What it is | Steam Gaming Mode: full screen, made for controllers | GNOME desktop for coding and everyday work |
| Apps | Steam library (other launchers via **Add to Steam**) | VS Code, Docker, Podman, Distrobox, Homebrew, virtual machines, Android tools |
| App store | Steam store | **Bazaar**, with a NebulaOS *Development & Work* section |
| Switch | Steam menu › Power › **Switch to Desktop** | **Switch to Gaming Mode** in the dock |

The chooser highlights the last mode selected through the chooser and offers Gaming Mode, Work Mode, log out, restart and power off. Use a mouse, arrow keys and Enter, or a controller's D-pad/left stick and A button. Accounts that already have a saved login mode keep it; run `ujust nebula-mode chooser` to show the chooser after each login. The login screen's **gear menu** always offers the direct Gaming Mode and Work Mode sessions.

## What NebulaOS adds

- **`nebula` tool**, the foundation of the Nebula Control Center:
  - `nebula status`: live CPU, GPU, memory, storage, network, temperatures, power profile, updates and health
  - `nebula hw`: **Hardware Detection Engine.** GPUs (AMD, Intel, NVIDIA backends), architecture, Vulkan, OpenGL and video acceleration verified by real probes, hybrid graphics, and each display's mode, refresh range, **VRR** and **HDR**. Every feature is reported at five levels: hardware, driver, available, enabled, verified.
  - `nebula doctor`: **System Doctor.** 12 checks with suggested fixes; it never changes anything.
  - `nebula update check|history|apply|rollback`: update management; `apply` and `rollback` ask before changing the system
  - `--json` is available for `status`, `hw`, `doctor`, `update check` and `update history`. `apply` and `rollback` are interactive text commands.
- **App bundle** from Flathub: everyday apps (Firefox, Text Editor, Calculator, Image Viewer, Document Viewer, Flatseal, Extension Manager) plus Heroic, Bottles, OBS Studio, Vesktop, MangoJuice, RetroArch, Dolphin, PCSX2.
- **FPS overlay preset** (`ujust nebula-fps-overlay on`).
- **Identity:** name in the boot menu and Settings › About, logo, wallpapers, login mode names.
- **Signed images** with your own key, verified in CI before publication.

The planned **Nebula Control Center, Gaming Optimizer, Display Lab and Dev Hub** are on the [roadmap](docs/ROADMAP.md).

## Install

**One step, from the ISO:** NebulaOS installs directly, with Bazzite already inside (Steam, drivers, Gaming Mode, updates). Download the installer ISO from **Actions › Build disk images** (artifact `nebula-os-latest-anaconda-iso`), write it to a USB stick and boot from it. The ISO installs successfully in a virtual machine; it has not been installed on real hardware yet, so try it in GNOME Boxes first.

**Already on Bazzite?** Switch to the exact image you verified, then turn on signed updates:

```bash
curl -fsSLO https://raw.githubusercontent.com/trevor99-afk/nebula-os/main/cosign.pub
IMAGE=ghcr.io/trevor99-afk/nebula-os   # NVIDIA: ghcr.io/trevor99-afk/nebula-os-nvidia
DIGEST=$(skopeo inspect --format '{{.Digest}}' "docker://$IMAGE:latest")
cosign verify --key cosign.pub "$IMAGE@$DIGEST"
sudo bootc switch "$IMAGE@$DIGEST" && systemctl reboot
ujust nebula-enable-signed-updates                        # after the reboot, then reboot again
```

Full guide: [docs/INSTALLATION.md](docs/INSTALLATION.md).

| Edition | Image |
| --- | --- |
| AMD / Intel graphics | `ghcr.io/trevor99-afk/nebula-os` |
| NVIDIA graphics (untested on hardware) | `ghcr.io/trevor99-afk/nebula-os-nvidia` |

Channels: `:latest` (stable, branch `main`) and `:testing` (branch `dev`).

## Everyday commands

| Command | What it does |
| --- | --- |
| `ujust nebula-mode gaming` / `work` | Select that mode for the next login; while the chooser is enabled, skip it once (add `now` to switch immediately) |
| `ujust nebula-mode chooser` | Show the chooser after each login |
| `ujust nebula-mode chooser-off` | Turn off the chooser; at the next login, start the last mode selected through the chooser (Work Mode if there is no saved choice) |
| `ujust nebula-info` | Version, live status and the app bundle |
| `ujust nebula-doctor` | Check the system and suggest fixes |
| `ujust nebula-hw` | Hardware and display capability report |
| `ujust nebula-install-apps` | Install the app bundle now |
| `ujust nebula-fps-overlay on` | FPS overlay preset (`off`, `status`) |
| `ujust nebula-enable-signed-updates` | Only accept updates signed with the NebulaOS key |
| `ujust nebula-switch-to-bazzite` | Go back to stock Bazzite DX |

Updates download in the background and apply on the next restart. For the exact status, use `nebula update check` and `nebula update history`.

## Update and rollback

`nebula update apply` asks before downloading and staging the newest image. Restart to boot it. If the new deployment causes a problem, run `nebula update rollback`, confirm the previous deployment shown, and restart; the previous deployment should boot and the newer one remains available in the boot menu. If NebulaOS does not start, choose the previous deployment from the boot menu.

This recovery route is documented but the full NebulaOS update and rollback journey has not yet been exercised in a VM or on hardware. Maintainers should record the image digest and test target with the [release validation checklist](docs/RELEASE_PROCESS.md#per-release-validation-checklist).

## Documentation

[Installation](docs/INSTALLATION.md) · [Hardware compatibility](docs/HARDWARE_COMPATIBILITY.md) · [Gaming](docs/GAMING.md) · [Development](docs/DEVELOPMENT.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Architecture](docs/ARCHITECTURE.md) · [Technical audit](docs/NEBULAOS_TECHNICAL_AUDIT.md) · [Backend and Gaming Mode audit](docs/BACKEND_GAMING_AUDIT.md) · [Roadmap](docs/ROADMAP.md) · [Release process](docs/RELEASE_PROCESS.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Building it yourself

```bash
just build && just test-image   # build and test localhost/nebula-os:latest
just switch-local               # switch this computer to it
```

Settings (name, GitHub account and repository, base image) live in `image-template.env`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Known limitations

- Not yet booted on real hardware; the ISO installer is untested.
- The chooser's keyboard/controller navigation, controller permissions, small-screen layout, and in-session mode switching are unverified in a built image and on hardware.
- Steam Gaming Mode can show a black screen on some dual-GPU laptops. The Work Mode recovery path is unverified in a built image and on hardware.
- The NVIDIA edition is untested on NVIDIA hardware.

## Credits

Built with Universal Blue's [image-template](https://github.com/ublue-os/image-template) on top of [Bazzite DX](https://dev.bazzite.gg). NebulaOS is not affiliated with Bazzite or Universal Blue. Licensed under Apache-2.0.
