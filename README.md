<p align="center">
  <img src="system_files/usr/share/icons/hicolor/scalable/apps/nebula-os-logo.svg" width="128" alt="NebulaOS logo">
</p>

# NebulaOS

**One operating system. Two worlds.** A Linux distribution with a **Gaming Mode** and a **Work Mode**: you choose one every time you log in.

NebulaOS is built on [Bazzite DX](https://dev.bazzite.gg), so it keeps everything Bazzite provides (Steam, Proton, Gamescope, MangoHud, a gaming-tuned kernel, fresh graphics drivers, automatic updates and one-step rollback). On top, it adds its own tools and identity, and does not rebuild what Bazzite already does well.

> **Status:** testing. The image builds, is signed and passes 47 automated image tests. It has not yet been booted on real hardware. See [what is verified](docs/NEBULAOS_TECHNICAL_AUDIT.md#unverified-needs-a-real-boot).

## The two modes

| | NebulaOS Gaming Mode | NebulaOS Work Mode |
| --- | --- | --- |
| What it is | Steam Gaming Mode: full screen, made for controllers | GNOME desktop for coding and everyday work |
| Apps | Steam library (other launchers via **Add to Steam**) | VS Code, Docker, Podman, Distrobox, Homebrew, virtual machines, Android tools |
| App store | Steam store | **Bazaar**, with a NebulaOS *Development & Work* section |
| Switch | Steam menu › Power › **Switch to Desktop** | **Switch to Gaming Mode** in the dock |

On the login screen: select your user, click the **gear button** and pick a mode. Your last choice is remembered. `ujust nebula-mode gaming` or `ujust nebula-mode work` sets it from a terminal.

## What NebulaOS adds

- **`nebula` tool**, the foundation of the Nebula Control Center:
  - `nebula status`: live CPU, GPU, memory, storage, network, temperatures, power profile, updates and health
  - `nebula hw`: **Hardware Detection Engine.** GPUs (AMD, Intel, NVIDIA backends), architecture, Vulkan, OpenGL and video acceleration verified by real probes, hybrid graphics, and each display's mode, refresh range, **VRR** and **HDR**. Every feature is reported at five levels: hardware, driver, available, enabled, verified.
  - `nebula doctor`: **System Doctor.** 12 checks with suggested fixes; it never changes anything.
  - `nebula update check|history|apply|rollback`: updates, with confirmation before any change
  - Every command has `--json` output.
- **App bundle** from Flathub: Heroic, Bottles, OBS Studio, Vesktop, MangoJuice, RetroArch, Dolphin, PCSX2.
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
| `ujust nebula-mode gaming` / `work` | Choose the mode started at login (add `now` to switch right away) |
| `ujust nebula-info` | Version, live status and the app bundle |
| `ujust nebula-doctor` | Check the system and suggest fixes |
| `ujust nebula-hw` | Hardware and display capability report |
| `ujust nebula-install-apps` | Install the app bundle now |
| `ujust nebula-fps-overlay on` | FPS overlay preset (`off`, `status`) |
| `ujust nebula-enable-signed-updates` | Only accept updates signed with the NebulaOS key |
| `ujust nebula-switch-to-bazzite` | Go back to stock Bazzite DX |

Updates install automatically in the background (Bazzite's updater) and apply on the next restart.

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
- Steam Gaming Mode can show a black screen on some dual-GPU laptops. Work Mode always works.
- The NVIDIA edition is untested on NVIDIA hardware.

## Credits

Built with Universal Blue's [image-template](https://github.com/ublue-os/image-template) on top of [Bazzite DX](https://dev.bazzite.gg). NebulaOS is not affiliated with Bazzite or Universal Blue. Licensed under Apache-2.0.
